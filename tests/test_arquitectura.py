"""Guardián de la decisión D2 (`design.md` §2 y §3).

`rasante.dominio` es el motor de reglas: debe poder portarse a otro lenguaje o compilarse a
WASM sin arrastrar dependencias. Por eso solo puede importar stdlib.

Si este test falla, el proyecto perdió su única salida barata hacia Rust/WASM.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
DOMINIO = SRC / "rasante" / "dominio"


def imports_de(fuente: str) -> set[str]:
    """Módulos de nivel superior importados por un fuente Python."""
    modulos: set[str] = set()
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:  # import relativo: interno al paquete, siempre permitido
                continue
            if nodo.module:
                modulos.add(nodo.module.split(".")[0])
    return modulos


def terceros(modulos: set[str]) -> set[str]:
    """De un conjunto de módulos, los que no son stdlib ni el propio paquete."""
    return {m for m in modulos if m not in sys.stdlib_module_names and m != "rasante"}


# --- El detector mismo: sin estos tests el guardián podría pasar vacío ---


def test_detecta_import_de_tercero() -> None:
    assert terceros(imports_de("import shapely\n")) == {"shapely"}


def test_detecta_import_from_de_tercero() -> None:
    assert terceros(imports_de("from shapely.geometry import shape\n")) == {"shapely"}


def test_permite_stdlib() -> None:
    fuente = "import decimal\nfrom dataclasses import dataclass\nfrom pathlib import Path\n"
    assert terceros(imports_de(fuente)) == set()


def test_permite_import_relativo_y_del_propio_paquete() -> None:
    fuente = "from .modelos import Zona\nfrom rasante.corpus import cargador\n"
    assert terceros(imports_de(fuente)) == set()


# --- El guardián ---


def test_dominio_existe() -> None:
    assert DOMINIO.is_dir(), f"falta el paquete de dominio en {DOMINIO}"


def test_dominio_solo_stdlib() -> None:
    infracciones: dict[str, set[str]] = {}
    for archivo in sorted(DOMINIO.rglob("*.py")):
        malos = terceros(imports_de(archivo.read_text(encoding="utf-8")))
        if malos:
            infracciones[str(archivo.relative_to(SRC))] = malos
    assert not infracciones, f"D2 violada: el dominio importa terceros: {infracciones}"
