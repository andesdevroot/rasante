"""Tests de hechos y selección de límites condicionales (T1.6).

D16: el motor elige **cuál** límite aplica según cómo sea el proyecto, evaluando hechos que el
corpus define. Si no puede clasificarlo, **lo dice** en vez de elegir en silencio.

El caso real es la OGUC, y no es un booleano:

    2.6.4  Conjunto Armónico si cumple ALGUNA de estas condiciones:
           1.a) terreno >= 5 veces la superficie predial mínima del PRC
           1.c) ...
    2.6.5  1.a) o 1.b)  ->  exceder el cus hasta un 50%
           1.c)         ->  exceder el cus hasta un 30%

**La excepción sustituye al base, no se le suma.** Si ligan los dos y gana el más restrictivo, el
+50 % nunca aplicaría y el 2.6.5 sería letra muerta. Esto corrige el enunciado original de la tarea.

**Y el fallback nunca es el permisivo.** Si falta el dato para clasificar, sale `P`, jamás el +50 %:
aplicar la excepción a un proyecto que no califica es aprobar algo que la norma no permite.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from rasante.corpus.cargador import cargar_reglas
from rasante.dominio.factibilidad import verificar
from rasante.dominio.modelos import (
    Cita,
    CodigoHallazgo,
    CodigoVeredicto,
    ErrorDominio,
    EstadoParametro,
    EstadoRevision,
    Limite,
    Parametro,
    Procedencia,
    Proyecto,
    TipoLimite,
    Vigencia,
    Zona,
)
from rasante.dominio.motor import clasificar, evaluar
from rasante.dominio.reglas import Hecho, Reglas

RAIZ = Path(__file__).resolve().parents[1]
REGLAS: Reglas = cargar_reglas(RAIZ / "corpus")

CITA_PRC = Cita(norma_id="prc:nunoa", articulo="Z-4", texto="Ordenanza local Z-4")
CITA_2_6_5 = Cita(norma_id="oguc", articulo="2.6.5", texto="excepción del Conjunto Armónico")


def procedencia() -> Procedencia:
    return Procedencia(
        url_fuente="https://www.nunoa.cl/ordenanza.pdf",
        hash_fuente="sha256:" + "0" * 64,
        consolidado_por="Texto refundido, junio 2025",
        extraido="2026-09-26",
        estado=EstadoRevision.REVISADO,
    )


def limite(valor: str, tipo: TipoLimite = TipoLimite.BASE, cuando: tuple[str, ...] = ()) -> Limite:
    return Limite(
        tipo=tipo,
        valor=Decimal(valor),
        unidad="adimensional",
        cita=CITA_2_6_5 if tipo is TipoLimite.EXCEPCION else CITA_PRC,
        cuando=frozenset(cuando),
    )


def parametro(
    id_: str, *limites: Limite, calificador: str | None = None
) -> Parametro:
    return Parametro(
        id=id_,
        limites=limites,
        estado=EstadoParametro.APLICABLE,
        cita=CITA_PRC,
        calificador=calificador,
    )


def zona(
    *parametros: Parametro,
    superficie_predial_minima: str | None = "1000",
) -> Zona:
    """Zona con el `cus` del 2.6.5 y, si se pide, la superficie predial mínima del PRC."""
    todos = list(parametros)
    if superficie_predial_minima is not None:
        todos.append(
            Parametro(
                id="superficie_predial_minima",
                limites=(
                    Limite(TipoLimite.BASE, Decimal(superficie_predial_minima), "m2", CITA_PRC),
                ),
                estado=EstadoParametro.APLICABLE,
                cita=CITA_PRC,
            )
        )
    return Zona(
        codigo="Z-4",
        nombre="Z-4",
        comuna="Ñuñoa",
        parametros={p.clave: p for p in todos},
        vigencia=Vigencia(),
        procedencia=procedencia(),
    )


CUS_CON_EXCEPCION = parametro(
    "cus",
    limite("4"),
    limite("6", TipoLimite.EXCEPCION, ("dimension_a",)),
)


def proyecto(**campos: object) -> Proyecto:
    base: dict[str, object] = {
        "superficie_predio_m2": Decimal("1000"),
        "numero_viviendas": 10,
        "superficie_edificada_m2": Decimal("4500"),
    }
    base.update(campos)
    return Proyecto(**base)  # type: ignore[arg-type]


def cus_de(p: Proyecto, z: Zona) -> CodigoVeredicto:
    return next(v for v in evaluar(p, z, REGLAS) if v.clave == "cus").codigo


# --- el corpus define los hechos ---


def test_el_corpus_trae_el_hecho_del_264() -> None:
    assert "dimension_a" in REGLAS.hechos
    hecho = REGLAS.hechos["dimension_a"]
    assert "superficie_predial_minima" in hecho.expresion
    assert hecho.cita.articulo == "2.6.4"


def test_el_corpus_trae_la_excepcion_del_265() -> None:
    """El +50 % debe estar en el corpus, no hardcodeado."""
    assert (RAIZ / "corpus" / "oguc" / "2.6.5.yaml").is_file()


# --- clasificar ---


def test_clasificar_dice_que_hechos_se_cumplen() -> None:
    """Un predio de 6.000 m² con predial mínima de 1.000 cumple 1.a) (>= 5 veces)."""
    z = zona(CUS_CON_EXCEPCION)
    clasificacion = clasificar(proyecto(superficie_predio_m2=Decimal("6000")), z, REGLAS)
    assert clasificacion.hechos["dimension_a"] is True


def test_clasificar_dice_que_hechos_no_se_cumplen() -> None:
    z = zona(CUS_CON_EXCEPCION)
    clasificacion = clasificar(proyecto(superficie_predio_m2=Decimal("3000")), z, REGLAS)
    assert clasificacion.hechos["dimension_a"] is False


def test_clasificar_da_none_si_falta_el_dato() -> None:
    """Tercer estado: no se sabe. Distinto de `False`.

    El predio debe cumplir el segundo conjunto (>= 5.000 m²); si no, `and` da `False` sin importar
    que falte el otro dato, y eso es correcto: `X and False` es `False` con X conocido o no.
    """
    clasificacion = clasificar(
        proyecto(superficie_predio_m2=Decimal("6000")),
        zona(CUS_CON_EXCEPCION, superficie_predial_minima=None),
        REGLAS,
    )
    assert clasificacion.hechos["dimension_a"] is None


# --- selección del límite ---


def test_sin_cumplir_la_condicion_aplica_el_base() -> None:
    """3.000 m² no llega a 5 veces 1.000: no hay excepción, el cus máximo es 4.

    13.500 m² sobre 3.000 son cus 4,5 -> excede el base de 4.
    """
    z = zona(CUS_CON_EXCEPCION)
    p = proyecto(superficie_predio_m2=Decimal("3000"), superficie_edificada_m2=Decimal("13500"))
    assert cus_de(p, z) is CodigoVeredicto.NO_CUMPLE


def test_cumpliendo_la_condicion_aplica_la_excepcion() -> None:
    """6.000 m² sí llega a 5 veces 1.000: la excepción sustituye al base y el cus máximo es 6.

    4.500 m² sobre 1.000 son cus 4,5 -> cumple contra 6.
    """
    z = zona(CUS_CON_EXCEPCION)
    assert cus_de(proyecto(superficie_predio_m2=Decimal("6000")), z) is CodigoVeredicto.CUMPLE


def test_la_excepcion_sustituye_al_base_y_no_se_suma() -> None:
    """Criterio de aceptación: si los dos ligaran y ganara el más restrictivo,
    el 2.6.5 no serviría."""
    z = zona(CUS_CON_EXCEPCION)
    veredicto = next(
        v for v in evaluar(proyecto(superficie_predio_m2=Decimal("6000")), z, REGLAS)
        if v.clave == "cus"
    )
    assert veredicto.valor_norma == Decimal("6"), "debía regir la excepción, no el base"


def test_el_veredicto_conserva_la_cita_de_la_excepcion() -> None:
    """No basta con acertar el número: hay que poder citar de dónde sale."""
    z = zona(CUS_CON_EXCEPCION)
    veredicto = next(
        v for v in evaluar(proyecto(superficie_predio_m2=Decimal("6000")), z, REGLAS)
        if v.clave == "cus"
    )
    assert veredicto.cita.articulo == "2.6.5"


def test_el_veredicto_cita_el_base_cuando_no_hay_excepcion() -> None:
    z = zona(CUS_CON_EXCEPCION)
    p = proyecto(superficie_predio_m2=Decimal("3000"), superficie_edificada_m2=Decimal("13500"))
    veredicto = next(v for v in evaluar(p, z, REGLAS) if v.clave == "cus")
    assert veredicto.cita.articulo == "Z-4"


def test_entre_varias_excepciones_aplicables_manda_la_mas_restrictiva() -> None:
    """Si dos excepciones se cumplen a la vez, la prudencia manda: la más exigente.

    Hechos sintéticos: el corpus real solo tiene uno plenamente expresable hoy.
    """
    cita = Cita(norma_id="oguc", articulo="2.6.4", texto="condición de prueba")
    sinteticas = Reglas(
        derivaciones=REGLAS.derivaciones,
        hechos=MappingProxyType(
            {
                "hecho_uno": Hecho("hecho_uno", "superficie_predio_m2 >= 1000", cita),
                "hecho_dos": Hecho("hecho_dos", "superficie_predio_m2 >= 1000", cita),
            }
        ),
    )
    dos = parametro(
        "cus",
        limite("4"),
        limite("6", TipoLimite.EXCEPCION, ("hecho_uno",)),
        limite("5", TipoLimite.EXCEPCION, ("hecho_dos",)),
    )
    veredicto = next(
        v
        for v in evaluar(proyecto(superficie_predio_m2=Decimal("6000")), zona(dos), sinteticas)
        if v.clave == "cus"
    )
    assert veredicto.valor_norma == Decimal("5")


# --- EL INVARIANTE: indeterminado nunca cae al permisivo ---


def test_sin_poder_clasificar_da_pendiente() -> None:
    """Criterio de aceptación: falta la superficie predial mínima -> `P`, no el +50 %."""
    z = zona(CUS_CON_EXCEPCION, superficie_predial_minima=None)
    assert cus_de(proyecto(superficie_predio_m2=Decimal("6000")), z) is CodigoVeredicto.PENDIENTE


def test_sin_poder_clasificar_no_se_aplica_la_excepcion() -> None:
    z = zona(CUS_CON_EXCEPCION, superficie_predial_minima=None)
    veredicto = next(
        v for v in evaluar(proyecto(superficie_predio_m2=Decimal("6000")), z, REGLAS)
        if v.clave == "cus"
    )
    assert veredicto.valor_norma is None, "no se puede afirmar cuál límite rige"


def test_sin_poder_clasificar_se_emite_hallazgo() -> None:
    """Que el motor dé `P` no basta: el revisor tiene que saber **por qué**."""
    z = zona(CUS_CON_EXCEPCION, superficie_predial_minima=None)
    hallazgos = verificar(proyecto(superficie_predio_m2=Decimal("6000")), z, REGLAS)
    assert CodigoHallazgo.CLASIFICACION_INDETERMINADA in {h.codigo for h in hallazgos}


def test_el_hallazgo_dice_que_dato_falta() -> None:
    z = zona(CUS_CON_EXCEPCION, superficie_predial_minima=None)
    hallazgo = next(
        h for h in verificar(proyecto(superficie_predio_m2=Decimal("6000")), z, REGLAS)
        if h.codigo is CodigoHallazgo.CLASIFICACION_INDETERMINADA
    )
    assert "dimension_a" in hallazgo.mensaje
    assert "cus" in hallazgo.parametros


def test_clasificar_no_emite_hallazgo_cuando_todo_se_sabe() -> None:
    z = zona(CUS_CON_EXCEPCION)
    hallazgos = verificar(proyecto(superficie_predio_m2=Decimal("6000")), z, REGLAS)
    assert CodigoHallazgo.CLASIFICACION_INDETERMINADA not in {h.codigo for h in hallazgos}


# --- el modelo ---


def test_un_parametro_sin_limites_no_se_puede_construir() -> None:
    with pytest.raises(ErrorDominio):
        parametro("cus")


def test_un_limite_de_excepcion_sin_condiciones_no_se_puede_construir() -> None:
    """Una excepción sin `cuando` aplicaría siempre y anularía al base."""
    with pytest.raises(ErrorDominio):
        limite("6", TipoLimite.EXCEPCION, ())


def test_un_limite_base_con_condiciones_no_se_puede_construir() -> None:
    """Un base con condición no es un base."""
    with pytest.raises(ErrorDominio):
        limite("4", TipoLimite.BASE, ("dimension_c",))


def test_clasificar_no_muta_nada() -> None:
    z = zona(CUS_CON_EXCEPCION)
    p = proyecto(superficie_predio_m2=Decimal("6000"))
    antes = (len(z.parametros), len(p.clasificaciones))
    clasificar(p, z, REGLAS)
    assert (len(z.parametros), len(p.clasificaciones)) == antes
