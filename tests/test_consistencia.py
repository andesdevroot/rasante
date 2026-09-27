"""Invariantes transversales del proyecto, en un solo sitio.

No comprueban una función: comprueban que las piezas **concuerden entre sí**. Cada uno corresponde a
una forma concreta en que el sistema se pudre en silencio — dos listas que se separan, un corpus que
deriva algo que el motor no compara, una leyenda duplicada que deja de coincidir.

Estaban dispersos por los tests de cada tarea; acá se ven juntos y se rompen juntos.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from rasante.corpus.cargador import cargar_reglas
from rasante.dominio.modelos import (
    Cita,
    CodigoVeredicto,
    EstadoParametro,
    Limite,
    Parametro,
    Procedencia,
    Proyecto,
    Sentido,
    TipoLimite,
    Vigencia,
    Zona,
)
from rasante.dominio.motor import evaluar
from rasante.dominio.vocabulario import (
    PARAMETROS,
    PRIMITIVAS,
    VOCABULARIO,
    nombres_de_expresion,
)

RAIZ = Path(__file__).resolve().parents[1]
CORPUS = RAIZ / "corpus"
REGLAS = cargar_reglas(CORPUS)
ARCHIVOS = sorted(CORPUS.rglob("*.yaml"))
CITA = Cita(norma_id="prc:nunoa", articulo="Z-4", texto="ordenanza local")
PROCEDENCIA = Procedencia(
    url_fuente="https://x.cl/o.pdf",
    hash_fuente="sha256:" + "0" * 64,
    consolidado_por="refundido",
    extraido="2026-09-26", revisado_por="Revisor de prueba",
)


def documento(archivo: Path) -> dict[str, Any]:
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    return datos if isinstance(datos, dict) else {}


def zona_completa() -> Zona:
    """Una zona que declara **todos** los parámetros conocidos, con norma 1."""
    parametros = {}
    for clave in sorted(PARAMETROS):
        id_, _, calificador = clave.partition(".")
        parametros[clave] = Parametro(
            id=id_,
            limites=(Limite(TipoLimite.BASE, Decimal("1"), "adimensional", CITA),),
            sentido=Sentido.MAXIMO,
            estado=EstadoParametro.APLICABLE,
            cita=CITA,
            calificador=calificador or None,
        )
    return Zona(
        codigo="Z-4",
        nombre="Z-4",
        comuna="Ñuñoa",
        parametros=parametros,
        vigencia=Vigencia(),
        procedencia=PROCEDENCIA,
    )


# --- el vocabulario ---


def test_el_vocabulario_es_exactamente_la_union_de_sus_partes() -> None:
    """`NORMADOS` desapareció en T1.14: un valor del PRC que un hecho cita **es** un parámetro."""
    assert frozenset(PRIMITIVAS) | PARAMETROS == VOCABULARIO


def test_el_motor_no_hardcodea_que_se_compara() -> None:
    """`MAXIMOS` era lo ultimo hardcodeado; el sentido lo declara ahora cada parametro."""
    from rasante.dominio import motor

    assert not hasattr(motor, "MAXIMOS")



def test_toda_expresion_del_corpus_usa_solo_el_vocabulario() -> None:
    for archivo in ARCHIVOS:
        datos = documento(archivo)
        for seccion in ("derivaciones", "hechos"):
            for nombre, entrada in (datos.get(seccion) or {}).items():
                fuera = nombres_de_expresion(str(entrada["expresion"])) - VOCABULARIO
                assert not fuera, f"{archivo.name}:{seccion}.{nombre} usa {fuera}"


# --- el corpus y el motor ---


def test_toda_derivacion_del_corpus_cabe_en_el_vocabulario() -> None:
    """El sentido de la comparacion ya no vive en el motor: lo declara cada parametro."""
    assert set(REGLAS.derivaciones) <= PARAMETROS



def test_todo_cuando_del_corpus_tiene_hecho_definido() -> None:
    definidos = set(REGLAS.hechos)
    for archivo in ARCHIVOS:
        for clave, parametro in (documento(archivo).get("parametros") or {}).items():
            for limite in parametro.get("limites", []):
                for nombre in limite.get("cuando") or []:
                    assert nombre in definidos, (
                        f"{archivo.name}:{clave} exige '{nombre}', que nadie define"
                    )


def test_la_leyenda_del_dominio_coincide_con_el_corpus() -> None:
    """El dominio no puede leer YAML (D2), así que la leyenda está duplicada. Esto la vigila."""
    en_corpus = documento(CORPUS / "ddu" / "514.yaml")["leyenda_veredictos"]
    assert {c.value: c.texto for c in CodigoVeredicto} == en_corpus


# --- el invariante que sostiene el producto, sobre TODOS los parámetros a la vez ---


@pytest.mark.parametrize(
    "proyecto",
    [
        Proyecto(superficie_predio_m2=Decimal("1000"), numero_viviendas=10),
        Proyecto(
            superficie_predio_m2=Decimal("1000"),
            numero_viviendas=10,
            superficie_edificada_m2=Decimal("3000"),
            superficie_primer_piso_m2=Decimal("600"),
            altura_m=Decimal("20"),
            numero_pisos=5,
        ),
    ],
    ids=["sin-datos", "con-datos"],
)
def test_nunca_se_afirma_cumplimiento_sin_norma_ni_cita(proyecto: Proyecto) -> None:
    """El invariante del proyecto, comprobado de una vez sobre los 8 parámetros conocidos."""
    for veredicto in evaluar(proyecto, zona_completa(), REGLAS):
        if veredicto.codigo is not CodigoVeredicto.CUMPLE:
            continue
        assert veredicto.valor_norma is not None, f"{veredicto.clave}: cumplió sin norma"
        assert isinstance(veredicto.cita, Cita), f"{veredicto.clave}: cumplió sin cita"
        assert veredicto.cita.texto, f"{veredicto.clave}: la cita no tiene texto"
