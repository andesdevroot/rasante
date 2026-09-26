"""Tests del motor de evaluación (T1.2).

Es la tarea más delicada de la iteración. El invariante que sostiene el producto:

> **Un dato que no tenemos da `P` (pendiente), jamás `C` (cumple).**

Un `(C)` afirma que el proyecto cumple la norma. Si la norma es desconocida, si el dato del
proyecto falta, o si no sabemos cómo comparar un parámetro, afirmarlo sería un informe falso.

Los cuatro parámetros de la iteración 1 son **máximos** (no deben excederse). Tres se derivan de
primitivas del proyecto; solo `altura_maxima` se compara directo.

| Parámetro | Se deriva de |
|---|---|
| `cos` | superficie del primer piso / superficie del predio |
| `cus` | superficie edificada total / superficie del predio |
| `densidad` | viviendas / hectáreas del predio |
| `altura_maxima` | altura declarada (comparación directa) |
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from rasante.dominio.modelos import (
    Cita,
    CodigoVeredicto,
    EstadoParametro,
    EstadoRevision,
    Parametro,
    Procedencia,
    Proyecto,
    Vigencia,
    Zona,
)
from rasante.dominio.motor import evaluar

CITA = Cita(norma_id="prc:nunoa", articulo="2.1.22", texto="Densidad bruta máxima 200 hab/ha")


def procedencia() -> Procedencia:
    return Procedencia(
        url_fuente="https://www.nunoa.cl/ordenanza.pdf",
        hash_fuente="sha256:" + "0" * 64,
        consolidado_por="Texto refundido, junio 2025",
        extraido="2026-09-26",
        estado=EstadoRevision.REVISADO,
    )


def parametro(
    id_: str,
    valor: str | None,
    *,
    calificador: str | None = None,
    estado: EstadoParametro = EstadoParametro.APLICABLE,
    unidad: str = "adimensional",
) -> Parametro:
    return Parametro(
        id=id_,
        valor=Decimal(valor) if valor is not None else None,
        unidad=unidad,
        estado=estado,
        cita=CITA,
        calificador=calificador,
    )


def zona_con(*parametros: Parametro) -> Zona:
    return Zona(
        codigo="Z-4",
        nombre="Z-4",
        comuna="Ñuñoa",
        parametros={p.clave: p for p in parametros},
        vigencia=Vigencia(),
        procedencia=procedencia(),
    )


def proyecto(**campos: object) -> Proyecto:
    base: dict[str, object] = {"superficie_predio_m2": Decimal("1000"), "numero_viviendas": 10}
    base.update(campos)
    return Proyecto(**base)  # type: ignore[arg-type]


def unico(proyecto_: Proyecto, zona: Zona, clave: str) -> CodigoVeredicto:
    veredictos = [v for v in evaluar(proyecto_, zona) if v.clave == clave]
    assert len(veredictos) == 1, f"esperaba un veredicto para {clave}, hay {len(veredictos)}"
    return veredictos[0].codigo


# --- Comparación directa: cos (derivado de la superficie del primer piso) ---


def test_cos_cumple_cuando_no_excede_la_norma() -> None:
    z = zona_con(parametro("cos", "0.6"))
    p = proyecto(superficie_primer_piso_m2=Decimal("500"))  # 500/1000 = 0.5 <= 0.6
    assert unico(p, z, "cos") is CodigoVeredicto.CUMPLE


def test_cos_no_cumple_cuando_excede_la_norma() -> None:
    z = zona_con(parametro("cos", "0.6"))
    p = proyecto(superficie_primer_piso_m2=Decimal("700"))  # 0.7 > 0.6
    assert unico(p, z, "cos") is CodigoVeredicto.NO_CUMPLE


def test_exactamente_en_el_limite_cumple() -> None:
    """Un máximo se cumple si no se excede: el límite exacto es cumplimiento."""
    z = zona_con(parametro("cos", "0.6"))
    p = proyecto(superficie_primer_piso_m2=Decimal("600"))
    assert unico(p, z, "cos") is CodigoVeredicto.CUMPLE


def test_cus_se_deriva_de_la_superficie_edificada_total() -> None:
    z = zona_con(parametro("cus", "3.6"))
    assert unico(
        proyecto(superficie_edificada_m2=Decimal("3000")), z, "cus"
    ) is CodigoVeredicto.CUMPLE
    assert unico(
        proyecto(superficie_edificada_m2=Decimal("4000")), z, "cus"
    ) is CodigoVeredicto.NO_CUMPLE


def test_altura_se_compara_directo() -> None:
    z = zona_con(parametro("altura_maxima", "20", unidad="m"))
    assert unico(proyecto(altura_m=Decimal("18")), z, "altura_maxima") is CodigoVeredicto.CUMPLE
    assert unico(proyecto(altura_m=Decimal("22")), z, "altura_maxima") is CodigoVeredicto.NO_CUMPLE


# --- Densidad: la única regla derivada (A3) ---


def test_densidad_se_calcula_en_viviendas_por_hectarea() -> None:
    """`2.1.22`: densidad bruta en hab/ha. 10 viviendas en 5000 m² = 20 viv/ha."""
    z = zona_con(parametro("densidad", "20", calificador="bruta", unidad="hab/ha"))
    p = proyecto(superficie_predio_m2=Decimal("5000"), numero_viviendas=10)
    assert unico(p, z, "densidad.bruta") is CodigoVeredicto.CUMPLE


def test_densidad_excedida_no_cumple() -> None:
    z = zona_con(parametro("densidad", "20", calificador="bruta", unidad="hab/ha"))
    p = proyecto(superficie_predio_m2=Decimal("1000"), numero_viviendas=10)  # 100 viv/ha
    assert unico(p, z, "densidad.bruta") is CodigoVeredicto.NO_CUMPLE


def test_la_densidad_depende_del_predio_y_no_solo_de_las_viviendas() -> None:
    """Es una razón: el mismo número de viviendas cumple o no según la superficie."""
    z = zona_con(parametro("densidad", "50", calificador="bruta", unidad="hab/ha"))
    mismas_viviendas = {"numero_viviendas": 10}
    assert unico(
        proyecto(superficie_predio_m2=Decimal("5000"), **mismas_viviendas), z, "densidad.bruta"
    ) is CodigoVeredicto.CUMPLE
    assert unico(
        proyecto(superficie_predio_m2=Decimal("1000"), **mismas_viviendas), z, "densidad.bruta"
    ) is CodigoVeredicto.NO_CUMPLE


# --- EL INVARIANTE: lo desconocido nunca cumple ---


def test_norma_desconocida_da_pendiente_nunca_cumple() -> None:
    """El caso más importante del proyecto."""
    z = zona_con(parametro("cos", None, estado=EstadoParametro.DESCONOCIDO))
    p = proyecto(superficie_primer_piso_m2=Decimal("100"))  # holgadísimo
    assert unico(p, z, "cos") is CodigoVeredicto.PENDIENTE
    assert unico(p, z, "cos") is not CodigoVeredicto.CUMPLE


def test_parametro_que_no_aplica_da_no_procede() -> None:
    z = zona_con(parametro("cos", None, estado=EstadoParametro.NO_APLICA))
    assert unico(proyecto(), z, "cos") is CodigoVeredicto.NO_PROCEDE


def test_dato_de_proyecto_faltante_da_pendiente() -> None:
    z = zona_con(parametro("cos", "0.6"))
    assert unico(proyecto(), z, "cos") is CodigoVeredicto.PENDIENTE


def test_superficie_edificada_faltante_da_pendiente_para_cus() -> None:
    z = zona_con(parametro("cus", "3.6"))
    assert unico(proyecto(), z, "cus") is CodigoVeredicto.PENDIENTE


def test_altura_faltante_da_pendiente() -> None:
    z = zona_con(parametro("altura_maxima", "20", unidad="m"))
    assert unico(proyecto(), z, "altura_maxima") is CodigoVeredicto.PENDIENTE


def test_parametro_que_el_motor_no_sabe_comparar_da_pendiente() -> None:
    """Ante un parámetro desconocido no se asume que sea un máximo: no se puede afirmar nada."""
    z = zona_con(parametro("rasante", "5"))
    assert unico(proyecto(), z, "rasante") is CodigoVeredicto.PENDIENTE


def test_densidad_neta_sin_dato_da_pendiente() -> None:
    """La densidad neta descuenta utilidad pública, dato que el proyecto no declara."""
    z = zona_con(parametro("densidad", "50", calificador="neta", unidad="hab/ha"))
    assert unico(proyecto(), z, "densidad.neta") is CodigoVeredicto.PENDIENTE


def test_cos_de_pisos_superiores_sin_dato_da_pendiente() -> None:
    z = zona_con(parametro("cos", "0.4", calificador="pisos_superiores"))
    assert unico(
        proyecto(superficie_primer_piso_m2=Decimal("100")), z, "cos.pisos_superiores"
    ) is CodigoVeredicto.PENDIENTE


@pytest.mark.parametrize(
    "z",
    [
        zona_con(parametro("cos", None, estado=EstadoParametro.DESCONOCIDO)),
        zona_con(parametro("cos", "0.6")),
        zona_con(parametro("cus", "3.6")),
        zona_con(parametro("altura_maxima", "20", unidad="m")),
        zona_con(parametro("desconocido_x", "1")),
    ],
)
def test_ningun_caso_sin_datos_produce_cumple(z: Zona) -> None:
    veredictos = evaluar(proyecto(), z)
    assert all(v.codigo is not CodigoVeredicto.CUMPLE for v in veredictos), (
        f"un veredicto afirmó cumplimiento sin datos: {veredictos}"
    )


# --- Contrato de la salida ---


def test_un_veredicto_por_cada_parametro_de_la_zona() -> None:
    z = zona_con(
        parametro("cos", "0.6"),
        parametro("cus", "3.6"),
        parametro("altura_maxima", "20", unidad="m"),
        parametro("densidad", "50", calificador="bruta", unidad="hab/ha"),
    )
    assert len(evaluar(proyecto(), z)) == 4


def test_la_zona_sin_parametros_no_produce_veredictos() -> None:
    assert evaluar(proyecto(), zona_con()) == []


def test_el_orden_es_determinista() -> None:
    z = zona_con(
        parametro("densidad", "50", calificador="bruta", unidad="hab/ha"),
        parametro("altura_maxima", "20", unidad="m"),
        parametro("cos", "0.6"),
    )
    assert [v.clave for v in evaluar(proyecto(), z)] == ["altura_maxima", "cos", "densidad.bruta"]


def test_todo_veredicto_lleva_cita() -> None:
    z = zona_con(parametro("cos", "0.6"), parametro("cus", None))
    for v in evaluar(proyecto(), z):
        assert isinstance(v.cita, Cita)
        assert v.cita.texto


def test_el_veredicto_lleva_los_valores_comparados() -> None:
    z = zona_con(parametro("cos", "0.6"))
    v = evaluar(proyecto(superficie_primer_piso_m2=Decimal("500")), z)[0]
    assert v.valor_norma == Decimal("0.6")
    assert v.valor_proyecto == Decimal("0.5")


def test_el_veredicto_conserva_el_calificador() -> None:
    z = zona_con(parametro("densidad", "50", calificador="bruta", unidad="hab/ha"))
    v = evaluar(proyecto(), z)[0]
    assert v.calificador == "bruta"
    assert v.clave == "densidad.bruta"


def test_los_valores_comparados_son_decimal() -> None:
    z = zona_con(parametro("cos", "0.6"), parametro("altura_maxima", "20", unidad="m"))
    p = proyecto(superficie_primer_piso_m2=Decimal("500"), altura_m=Decimal("18"))
    for v in evaluar(p, z):
        assert not isinstance(v.valor_norma, float)
        assert not isinstance(v.valor_proyecto, float)


def test_el_motor_no_muta_la_zona_ni_el_proyecto() -> None:
    z = zona_con(parametro("cos", "0.6"))
    p = proyecto(superficie_primer_piso_m2=Decimal("500"))
    antes = (len(z.parametros), p.superficie_primer_piso_m2)
    evaluar(p, z)
    assert (len(z.parametros), p.superficie_primer_piso_m2) == antes


def test_el_motor_no_importa_nada_fuera_de_la_stdlib() -> None:
    """El guardián de D2 cubre el dominio entero; este test lo deja explícito para el motor."""
    fuente = (Path(__file__).resolve().parents[1] / "src/rasante/dominio/motor.py").read_text(
        encoding="utf-8"
    )
    assert "import httpx" not in fuente
    assert "import yaml" not in fuente
    assert "shapely" not in fuente
