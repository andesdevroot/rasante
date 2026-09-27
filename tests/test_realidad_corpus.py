"""Suite de realidad: el corpus se contrasta contra el artículo real (T1.7+).

**Por qué existe.** En T0.5 el troceador fusionaba `2.1.3` con `2.1.3 bis` — dos artículos
distintos— y **los 27 tests sintéticos pasaban igual**. Lo cazó la comprobación contra la OGUC
real. Un corpus que no se contrasta con su fuente es un corpus que se cree a sí mismo.

El fixture `oguc_articulos.json` guarda el texto de los artículos citados y el sha256 del PDF del
que salieron. Todo lo de acá corre **sin red**.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
OGUC = RAIZ / "corpus" / "oguc"
FIXTURE = json.loads(
    (RAIZ / "tests" / "fixtures" / "oguc_articulos.json").read_text(encoding="utf-8")
)
REALES: dict[str, str] = FIXTURE["articulos"]

ARCHIVOS = sorted(OGUC.glob("*.yaml"))
CON_ARTICULO = [
    a for a in ARCHIVOS if yaml.safe_load(a.read_text(encoding="utf-8")).get("articulo")
]


def normalizar(texto: Any) -> str:
    return " ".join(str(texto).split())


def documento(archivo: Path) -> dict[str, Any]:
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    assert isinstance(datos, dict)
    return datos


def test_el_fixture_declara_su_fuente_y_su_hash() -> None:
    assert FIXTURE["sha256"] and len(FIXTURE["sha256"]) == 64
    assert FIXTURE["fuente"].startswith("https://")


def test_el_fixture_tiene_los_articulos_que_el_corpus_cita() -> None:
    for archivo in CON_ARTICULO:
        articulo = documento(archivo)["articulo"]
        assert articulo in REALES, f"{archivo.name}: '{articulo}' no está en el fixture"


@pytest.mark.parametrize("archivo", CON_ARTICULO, ids=lambda p: p.name)
def test_la_cita_es_texto_literal_del_articulo(archivo: Path) -> None:
    """Una cita parafraseada no es una cita. Si el texto no está en el artículo, no lo respalda."""
    datos = documento(archivo)
    articulo = datos["articulo"]
    assert normalizar(datos["cita"]) in REALES[articulo], (
        f"{archivo.name}: la cita no aparece literalmente en el artículo {articulo}. "
        "¿Está parafraseada?"
    )


def test_las_definiciones_son_literales() -> None:
    """Cada definición de `1.1.2` debe aparecer en el artículo real, no ser un resumen."""
    definiciones = documento(OGUC / "1.1.2.yaml")["definiciones"]
    real = REALES["1.1.2"]
    for termino, texto in definiciones.items():
        assert normalizar(texto) in real, f"la definición de '{termino}' no está literalmente"


def test_los_hechos_citan_articulos_del_fixture() -> None:
    for archivo in ARCHIVOS:
        for nombre, hecho in (documento(archivo).get("hechos") or {}).items():
            articulo = str(hecho["cita"]["articulo"])
            assert articulo in REALES, (
                f"{archivo.name}:{nombre} cita '{articulo}', fuera del fixture"
            )


def test_las_expresiones_de_los_hechos_solo_usan_el_vocabulario() -> None:
    """Un hecho que nombra algo fuera del vocabulario no se podría evaluar."""
    from rasante.dominio.vocabulario import VOCABULARIO, nombres_de_expresion

    for archivo in ARCHIVOS:
        for nombre, hecho in (documento(archivo).get("hechos") or {}).items():
            fuera = nombres_de_expresion(str(hecho["expresion"])) - VOCABULARIO
            assert not fuera, f"{archivo.name}:{nombre} usa nombres fuera del vocabulario: {fuera}"
