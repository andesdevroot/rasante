"""El corpus normativo debe citar y declarar procedencia (T0.6).

Invariante 6 de `doc/05-VALIDACION.md`: una regla sin fuente no entra al corpus.

Estos tests **no** verifican que la cita sea correcta — eso lo valida un revisor humano. Verifican
que esté, que sea trazable a una fuente con hash, y que no falte ninguna de las piezas que la
iteración 1 necesita.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
CORPUS = RAIZ / "corpus"
OGUC = CORPUS / "oguc"
DDU = CORPUS / "ddu"

ARCHIVOS = sorted(OGUC.glob("*.yaml")) + sorted(DDU.glob("*.yaml"))

# Piezas que la iteración 1 necesita sí o sí (doc/02-ALCANCE.md).
ARTICULOS_DE_CALCULO = ("2.1.22", "2.1.23", "5.1.10", "5.1.11", "5.1.12")
DEFINICIONES = (
    "coeficiente de constructibilidad",
    "coeficiente de ocupacion del suelo",
    "coeficiente de ocupacion de los pisos superiores",
    "densidad",
    "densidad bruta",
    "densidad neta",
    "altura de edificacion",
    "superficie edificada",
)


def sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def cargar(ruta: Path) -> dict[str, Any]:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    assert isinstance(datos, dict), f"{ruta.name} no es un mapping YAML"
    return datos


# --- el corpus existe y no está vacío ---


def test_el_corpus_no_esta_vacio() -> None:
    assert len(ARCHIVOS) >= 7, f"esperaba >= 7 normas en corpus/, hay {len(ARCHIVOS)}"


def test_hay_un_archivo_de_fuentes_de_la_oguc() -> None:
    assert (OGUC / "fuentes.yaml").is_file()


# --- toda norma cita y declara procedencia ---


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda p: p.name)
def test_declara_la_fuente_con_hash(ruta: Path) -> None:
    datos = cargar(ruta)
    proc = datos.get("procedencia")
    assert isinstance(proc, dict), f"{ruta.name}: falta 'procedencia'"
    assert proc.get("url_fuente", "").startswith("https://"), f"{ruta.name}: url_fuente inválida"
    hash_ = str(proc.get("hash_fuente", ""))
    assert hash_.startswith("sha256:") and len(hash_) == 71, (
        f"{ruta.name}: hash_fuente no es sha256"
    )
    assert proc.get("consolidado_por"), f"{ruta.name}: falta el decreto consolidante"
    assert proc.get("extraido"), f"{ruta.name}: falta la fecha de extracción"
    estados = {"borrador", "revisado", "validado"}
    assert proc.get("estado") in estados, f"{ruta.name}: estado inválido"


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda p: p.name)
def test_declara_su_identidad_normativa(ruta: Path) -> None:
    datos = cargar(ruta)
    assert datos.get("norma_id"), f"{ruta.name}: falta norma_id"
    assert datos.get("cita"), f"{ruta.name}: falta la cita textual"


# --- cobertura de lo que la iteración 1 necesita ---


def test_estan_los_articulos_de_calculo() -> None:
    faltan = [n for n in ARTICULOS_DE_CALCULO if not (OGUC / f"{n}.yaml").is_file()]
    assert not faltan, f"faltan artículos de cálculo: {faltan}"


def test_el_articulo_de_definiciones_cubre_los_terminos_necesarios() -> None:
    definiciones = cargar(OGUC / "1.1.2.yaml").get("definiciones", {})
    claves = [sin_acentos(k.lower()) for k in definiciones]
    faltan = [d for d in DEFINICIONES if not any(d in k for k in claves)]
    assert not faltan, f"faltan definiciones en 1.1.2: {faltan}"


def test_la_densidad_declara_la_regla_de_bruta() -> None:
    """El art. 2.1.22 fija que los IPT expresan la densidad en BRUTA.

    Sin eso, el cálculo de densidad es ambiguo y el veredicto queda sin fundamento (A3).
    """
    regla = cargar(OGUC / "2.1.22.yaml").get("regla", {})
    assert regla.get("expresion_obligatoria") == "densidad bruta"
    assert regla.get("unidad") == "hab/ha"
    assert regla.get("factor_habitantes_por_vivienda")


def test_la_altura_declara_la_conversion_de_pisos() -> None:
    regla = cargar(OGUC / "2.1.23.yaml").get("regla", {})
    assert str(regla.get("metros_por_piso")) == "3.50"


def test_los_valores_normativos_son_texto_no_float() -> None:
    """Decimal, nunca float (D6): un float en el YAML reintroduce el error binario."""
    for ruta in ARCHIVOS:
        for clave, valor in _hojas(cargar(ruta)):
            assert not isinstance(valor, float), f"{ruta.name}: '{clave}' es float, debe ser str"


def _hojas(nodo: Any, ruta: str = "") -> list[tuple[str, Any]]:
    """Todos los valores hoja del YAML, con su ruta, para poder señalarlos en el error."""
    encontrados: list[tuple[str, Any]] = []
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            encontrados.extend(_hojas(valor, f"{ruta}.{clave}" if ruta else str(clave)))
    elif isinstance(nodo, list):
        for i, valor in enumerate(nodo):
            encontrados.extend(_hojas(valor, f"{ruta}[{i}]"))
    else:
        encontrados.append((ruta, nodo))
    return encontrados


# --- DDU 514: el formato de salida ---


def test_la_ddu_514_declara_la_leyenda_de_veredictos() -> None:
    leyenda = cargar(DDU / "514.yaml").get("leyenda_veredictos", {})
    assert set(leyenda) == {"C", "NC", "P", "NP", "PR"}, f"leyenda incompleta: {sorted(leyenda)}"


def test_la_ddu_514_registra_que_la_fuente_es_ocr() -> None:
    """La fuente es un PDF escaneado: extraer reglas de ahí exige verificación visual."""
    datos = cargar(DDU / "514.yaml")
    assert datos["procedencia"].get("texto_extraible") is False
    assert datos["procedencia"].get("requiere_verificacion_visual") is True
