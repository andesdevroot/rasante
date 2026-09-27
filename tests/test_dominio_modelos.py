"""Tests de los modelos de dominio (T1.1).

El dominio es la capa pura (D2): solo stdlib. Estos tests fijan los tres invariantes que sostienen
todo el proyecto:

1. **Sin cita no hay veredicto.** Un `Veredicto` sin respaldo normativo es un error de construcción.
2. **Decimal, nunca float** (D6). Un float reintroduce el error binario en el informe firmado.
3. **La clave de parámetro es compuesta.** Con variantes de `cos` y `densidad`, una clave por `id`
   produce claves duplicadas y el parser descarta una en silencio (A3).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from rasante.dominio.modelos import (
    LEYENDA,
    Cita,
    CodigoVeredicto,
    ErrorDominio,
    EstadoParametro,
    EstadoRevision,
    Limite,
    Parametro,
    Procedencia,
    Proyecto,
    TipoLimite,
    Veredicto,
    Vigencia,
    Zona,
    clave_compuesta,
)

RAIZ = Path(__file__).resolve().parents[1]
CORPUS_DDU = RAIZ / "corpus" / "ddu" / "514.yaml"


CITA_POR_DEFECTO = Cita(norma_id="oguc", articulo="1.1.2", texto="definiciones")


def par(
    id: str,  # noqa: A002 - se llama `id` para que los tests se lean como el modelo
    valor: object = None,
    *,
    calificador: str | None = None,
    unidad: str = "adimensional",
    estado: EstadoParametro = EstadoParametro.APLICABLE,
    cita: Cita | None = None,
) -> Parametro:
    """Un parámetro con un solo límite base, para no repetir el envoltorio en cada test."""
    usada = cita or CITA_POR_DEFECTO
    if valor is None:
        limites: tuple[Limite, ...] = ()
    else:
        limites = (Limite(TipoLimite.BASE, valor, unidad, usada),)  # type: ignore[arg-type]
    return Parametro(id=id, limites=limites, estado=estado, cita=usada, calificador=calificador)


def cita() -> Cita:
    return Cita(norma_id="oguc", articulo="2.1.23", texto="3,50 m por el número de pisos")


def procedencia() -> Procedencia:
    return Procedencia(
        url_fuente="https://www.nunoa.cl/ordenanza.pdf",
        hash_fuente="sha256:" + "0" * 64,
        consolidado_por="Texto refundido, junio 2025",
        extraido="2026-09-26", revisado_por="Revisor de prueba",
    )


# --- 1. Sin cita no hay veredicto ---


def test_veredicto_sin_cita_no_se_puede_construir() -> None:
    with pytest.raises(TypeError):
        Veredicto(parametro_id="altura_maxima", codigo=CodigoVeredicto.PENDIENTE)  # type: ignore[call-arg]


def test_veredicto_con_cita_none_levanta_error() -> None:
    with pytest.raises(ErrorDominio, match="cita"):
        Veredicto(
            parametro_id="altura_maxima",
            codigo=CodigoVeredicto.PENDIENTE,
            cita=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("campo", ["norma_id", "articulo", "texto"])
def test_una_cita_incompleta_levanta_error(campo: str) -> None:
    campos = {"norma_id": "oguc", "articulo": "1.1.2", "texto": "definiciones"}
    campos[campo] = "   "
    with pytest.raises(ErrorDominio, match=campo):
        Cita(**campos)


def test_un_veredicto_valido_se_construye() -> None:
    v = Veredicto(
        parametro_id="altura_maxima", codigo=CodigoVeredicto.CUMPLE, cita=cita(), valor_norma=None
    )
    assert v.codigo is CodigoVeredicto.CUMPLE
    assert v.calificador is None


# --- 2. Decimal, nunca float ---


def test_decimal_se_preserva_sin_perdida() -> None:
    valor = Decimal("3.6")
    p = par(
        id="cus", valor=valor, unidad="adimensional", estado=EstadoParametro.APLICABLE, cita=cita()
    )
    base = p.base
    assert base is not None
    assert base.valor == valor
    base = p.base
    assert base is not None
    assert str(base.valor) == "3.6", (
        "el roundtrip no debe reintroducir notación científica"
    )


def test_decimal_distingue_la_coma_de_la_ordenanza() -> None:
    """`0,6` de la ordenanza no es lo mismo que `6`. Con float se perdería."""
    assert Decimal("0.6") != Decimal("6")
    assert str(Decimal("3.50")) == "3.50", "los ceros finales importan en una cita normativa"


@pytest.mark.parametrize("malo", [0.6, 3.5, 1])
def test_un_parametro_rechaza_valores_que_no_son_decimal(malo: object) -> None:
    with pytest.raises(ErrorDominio, match="Decimal"):
        par(
            id="cos",
            valor=malo,
            unidad="adimensional",
            estado=EstadoParametro.APLICABLE,
            cita=cita(),
        )


def test_un_proyecto_rechaza_float() -> None:
    with pytest.raises(ErrorDominio, match="Decimal"):
        Proyecto(superficie_predio_m2=500.0, numero_viviendas=10)  # type: ignore[arg-type]


# --- 3. Clave compuesta (A3) ---


def test_clave_sin_calificador_es_el_id() -> None:
    p = par(
        id="cus", valor=Decimal("3.6"), unidad="adimensional", estado=EstadoParametro.APLICABLE,
        cita=cita(),
    )
    assert p.clave == "cus"


def test_clave_compuesta_es_la_unica_definicion() -> None:
    """`Parametro`, `Veredicto` y el cargador del corpus deben coincidir, o las reglas se pisan."""
    assert clave_compuesta("cus") == "cus"
    assert clave_compuesta("cos", "primer_piso") == "cos.primer_piso"
    assert clave_compuesta("densidad", "bruta") == "densidad.bruta"


def test_un_parametro_rechaza_un_id_que_ya_trae_el_calificador() -> None:
    """Bug real de T1.2: pasar la clave compuesta como `id` producía `densidad.bruta.bruta`."""
    with pytest.raises(ErrorDominio, match="calificador"):
        par(
            id="densidad.bruta",
            valor=Decimal("50"),
            unidad="hab/ha",
            estado=EstadoParametro.APLICABLE,
            cita=cita(),
            calificador="bruta",
        )


def test_clave_con_calificador_es_compuesta() -> None:
    p = par(
        id="cos", valor=Decimal("0.6"), unidad="adimensional", estado=EstadoParametro.APLICABLE,
        cita=cita(), calificador="primer_piso",
    )
    assert p.clave == "cos.primer_piso"


def test_dos_variantes_del_mismo_parametro_conviven_en_una_zona() -> None:
    """El caso real de Ñuñoa: cos `0,6` de primer piso y `0,4` de pisos superiores."""
    primer_piso = par(
        id="cos", valor=Decimal("0.6"), unidad="adimensional", estado=EstadoParametro.APLICABLE,
        cita=cita(), calificador="primer_piso",
    )
    superiores = par(
        id="cos", valor=Decimal("0.4"), unidad="adimensional", estado=EstadoParametro.APLICABLE,
        cita=cita(), calificador="pisos_superiores",
    )
    zona = Zona(
        codigo="Z-4", nombre="Z-4", comuna="Ñuñoa",
        parametros={primer_piso.clave: primer_piso, superiores.clave: superiores},
        vigencia=Vigencia(), procedencia=procedencia(),
    )
    assert len(zona.parametros) == 2, "las dos variantes deben sobrevivir, no pisarse"
    recuperado_pp = zona.parametro("cos.primer_piso")
    recuperado_sup = zona.parametro("cos.pisos_superiores")
    assert recuperado_pp is not None and recuperado_sup is not None
    base_pp, base_sup = recuperado_pp.base, recuperado_sup.base
    assert base_pp is not None and base_sup is not None
    assert base_pp.valor == Decimal("0.6")
    assert base_sup.valor == Decimal("0.4")


def test_la_zona_rechaza_una_clave_que_no_coincide_con_su_parametro() -> None:
    p = par(
        id="cos", valor=Decimal("0.6"), unidad="adimensional", estado=EstadoParametro.APLICABLE,
        cita=cita(), calificador="primer_piso",
    )
    with pytest.raises(ErrorDominio, match="clave"):
        Zona(
            codigo="Z-4", nombre="Z-4", comuna="Ñuñoa",
            parametros={"cos": p},  # la clave debe ser "cos.primer_piso"
            vigencia=Vigencia(), procedencia=procedencia(),
        )


def test_un_parametro_sin_valor_es_legal() -> None:
    """Un dato que no tenemos se representa sin límites y con estado DESCONOCIDO, no con un 0."""
    p = par("densidad", None, calificador="bruta", estado=EstadoParametro.DESCONOCIDO)
    assert p.limites == ()
    assert p.base is None
    assert p.estado is EstadoParametro.DESCONOCIDO
    assert p.clave == "densidad.bruta"


# --- La leyenda de veredictos debe coincidir con el corpus ---


def test_los_cinco_codigos_oficiales() -> None:
    assert [c.value for c in CodigoVeredicto] == ["C", "NC", "P", "NP", "PR"]


def test_los_textos_son_los_de_la_ddu_514() -> None:
    assert CodigoVeredicto.CUMPLE.texto == "Cumple con exigencias normativas"
    assert CodigoVeredicto.NO_CUMPLE.texto == "No cumple con exigencia normativa"
    assert CodigoVeredicto.PENDIENTE.texto == "Pendiente"
    assert CodigoVeredicto.NO_PROCEDE.texto == "No procede"
    assert CodigoVeredicto.PLAN_REGULADOR.texto == "Plan Regulador"


def test_la_leyenda_del_dominio_coincide_con_el_corpus() -> None:
    """El dominio no puede leer YAML (D2), así que la leyenda está hardcodeada.

    Este test es lo que impide que las dos se separen en silencio.
    """
    en_corpus = yaml.safe_load(CORPUS_DDU.read_text(encoding="utf-8"))["leyenda_veredictos"]
    assert {c.value: c.texto for c in CodigoVeredicto} == en_corpus


def test_la_leyenda_expone_los_cinco() -> None:
    assert set(LEYENDA) == set(CodigoVeredicto)


# --- El proyecto (con densidad en alcance, A3) ---


def test_el_proyecto_rechaza_un_predio_sin_superficie() -> None:
    """La densidad divide por la superficie: un cero no es un dato faltante, es un error."""
    with pytest.raises(ErrorDominio, match="superficie"):
        Proyecto(superficie_predio_m2=Decimal("0"), numero_viviendas=10)


def test_el_proyecto_rechaza_viviendas_negativas() -> None:
    with pytest.raises(ErrorDominio, match="viviendas"):
        Proyecto(superficie_predio_m2=Decimal("500"), numero_viviendas=-1)


def test_los_campos_opcionales_del_proyecto_son_opcionales() -> None:
    p = Proyecto(superficie_predio_m2=Decimal("500"), numero_viviendas=10)
    assert p.superficie_edificada_m2 is None
    assert p.altura_m is None


# --- Inmutabilidad ---


@pytest.mark.parametrize(
    ("objeto", "campo"),
    [
        (cita(), "articulo"),
        (Proyecto(superficie_predio_m2=Decimal("500"), numero_viviendas=1), "numero_viviendas"),
    ],
)
def test_los_modelos_son_inmutables(objeto: object, campo: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(objeto, campo, "otro")


# --- Estados ---


def test_los_estados_de_parametro_son_tres_y_distintos() -> None:
    assert {e.value for e in EstadoParametro} == {"aplicable", "no_aplica", "desconocido"}


def test_los_estados_de_revision_son_tres() -> None:
    assert {e.value for e in EstadoRevision} == {"borrador", "revisado", "validado"}
