"""Cobertura del motor sobre una zona real (E4).

La métrica que el paper necesita: **de los parámetros que la zona declara, cuántos concluye el motor
y qué le falta a cada uno de los que no.** Sobre Ñuñoa Z-2, que es la única zona transcrita.

Los números de acá **son** la tabla de §7, y por eso se fijan en el test: si alguien cambia el motor
y la cobertura se mueve, se entera.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from rasante.corpus.cargador import cargar_reglas, cargar_zona
from rasante.dominio.cobertura import Cobertura, medir
from rasante.dominio.modelos import (
    CodigoVeredicto,
    EstadoRevision,
    Procedencia,
    Proyecto,
    Zona,
)
from rasante.dominio.motor import MotivoPendiente, evaluar

RAIZ = Path(__file__).resolve().parents[1]
REGLAS = cargar_reglas(RAIZ / "corpus")


def zona(firmada: bool = True) -> Zona:
    z = cargar_zona(RAIZ / "corpus" / "prc" / "RM" / "nunoa" / "zonas" / "Z-2.yaml")
    if not firmada:
        return z
    return replace(
        z,
        procedencia=Procedencia(
            url_fuente=z.procedencia.url_fuente,
            hash_fuente=z.procedencia.hash_fuente,
            consolidado_por=z.procedencia.consolidado_por,
            extraido=z.procedencia.extraido,
            revisado_por="Revisor de prueba",
            estado=EstadoRevision.REVISADO,
        ),
    )


def proyecto() -> Proyecto:
    return Proyecto(
        superficie_predio_m2=Decimal("600"),
        numero_viviendas=20,
        superficie_primer_piso_m2=Decimal("300"),
        superficie_edificada_m2=Decimal("900"),
        altura_m=Decimal("20"),
        numero_pisos=8,
    )


def cobertura(externos: dict[str, bool | None] | None = None, firmada: bool = True) -> Cobertura:
    return medir(evaluar(proyecto(), zona(firmada), REGLAS, externos or {}))


# --- 1. la tabla del paper ---


def test_la_zona_declara_doce_parametros() -> None:
    assert cobertura().total == 14


def test_el_motor_concluye_seis_de_catorce_sin_clasificar_nada() -> None:
    """El número base: **6 de 12**.

    Y el `cus` **se concluye**, que es lo contraintuitivo y lo correcto: el proyecto no se acoge al
    Conjunto Armónico, así que el cortocircuito `X and False = False` descarta las excepciones de
    `2.6.5` y los hechos que no se saben dejan de importar. La negativa a concluir no es
    indiscriminada: **no concluye solo cuando la duda cambia el resultado**.
    """
    c = cobertura()
    assert c.concluidos == 6
    assert c.pendientes == 8
    assert c.proporcion == 6 / 14


def test_acogerse_al_conjunto_armonico_cuesta_una_cobertura() -> None:
    """El mismo expediente, acogido: el `cus` pasa a pendiente hasta clasificar sus condiciones.

    Es la conexión con E1 y con el portero: acogerse **activa** la duda, y por eso los dos hechos
    que la resuelven existen (T1.10). La cobertura no es una propiedad del corpus solo: depende del
    expediente.
    """
    acogido = replace(proyecto(), acoge_conjunto_armonico=True)
    c = medir(evaluar(acogido, zona(), REGLAS, {}))
    assert c.concluidos == 5
    assert c.codigos(MotivoPendiente.LIMITE_INDETERMINADO.value) == ("cus",)
    # Y clasificando los dos hechos vuelve a concluirse.
    resuelto = medir(
        evaluar(acogido, zona(), REGLAS, {"dimension_b": False, "dimension_c": False})
    )
    assert resuelto.concluidos == 6


def test_el_desglose_por_causa() -> None:
    """No todas las `P` son iguales, y cada causa tiene un arreglo distinto.

    - **`parametro_desconocido`** (2): la ordenanza remite a otra norma. Se arregla en el corpus.
    - **`sin_dato_proyecto`** (4): el límite se conoce, el expediente no declara el dato.
    """
    c = cobertura()
    assert c.codigos(MotivoPendiente.PARAMETRO_DESCONOCIDO.value) == (
        "adosamiento",
        "agrupamiento",
    )
    assert c.codigos(MotivoPendiente.SIN_DATO_PROYECTO.value) == (
        "antejarin",
        "area_libre",
        "area_libre_techada",
        "cuerpos_salientes",
        "distanciamiento",
        "rasante",
    )
    assert c.codigos(MotivoPendiente.LIMITE_INDETERMINADO.value) == ()


def test_sin_firma_no_se_concluye_nada_y_la_causa_lo_dice() -> None:
    """D18 sobre la métrica: una zona en borrador da 0 de 12, y las doce por la misma razón.

    Sirve como recordatorio de que la cobertura **no** mide solo el corpus: mide también si alguien
    lo firmó.
    """
    c = cobertura(firmada=False)
    assert c.concluidos == 0
    assert c.pendientes == 14
    assert len(c.codigos(MotivoPendiente.FUENTE_SIN_REVISAR.value)) == 14


# --- 2. invariantes del reporte ---


def test_todo_pendiente_tiene_motivo() -> None:
    """Un `P` sin causa sería un agujero en la trazabilidad, y el reporte lo delataría."""
    assert "sin_motivo" not in cobertura().por_motivo
    assert "sin_motivo" not in cobertura(firmada=False).por_motivo


def test_los_motivos_observados_son_los_declarados() -> None:
    """Los motivos del motor y los que aparecen en un reporte real no pueden divergir."""
    declarados = {m.value for m in MotivoPendiente}
    casos = (
        cobertura(),
        cobertura(firmada=False),
        cobertura({"dimension_b": None, "dimension_c": None}),
    )
    for c in casos:
        assert set(c.por_motivo) <= declarados


def test_solo_los_pendientes_llevan_motivo() -> None:
    """Un veredicto concluido no arrastra un diagnóstico: el motivo describe una ausencia."""
    for v in evaluar(proyecto(), zona(), REGLAS, {}):
        if v.codigo is CodigoVeredicto.PENDIENTE:
            assert v.motivo is not None
        else:
            assert v.motivo is None


def test_el_reporte_no_cuenta_dos_veces() -> None:
    """La suma de los códigos y la de los motivos dan el mismo total."""
    c = cobertura()
    assert sum(len(v) for v in c.por_codigo.values()) == c.total
    assert sum(len(v) for v in c.por_motivo.values()) == c.pendientes


def test_una_evaluacion_vacia_no_divide_por_cero() -> None:
    c = medir([])
    assert (c.total, c.concluidos, c.pendientes, c.proporcion) == (0, 0, 0, 0.0)
