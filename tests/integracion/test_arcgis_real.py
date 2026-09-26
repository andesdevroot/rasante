"""Test de integración contra la API real de MINVU (T0.4).

Los 9 tests de T0.2 corren offline por diseño (D9) y **no pueden** detectar si MINVU cambia el
esquema, mueve un servicio o altera `maxRecordCount`. Este módulo sí: golpea la API real.

Excluido de la corrida por defecto. Para correrlo:

    RASANTE_INTEGRACION=1 uv run pytest -m integracion
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from rasante.geo.arcgis import URL_BASE, ArcGIS, Capa

SERVICIO = "IPT/PRC_RM_Norte"
CAPA_PILOTO = "Las_Condes"

pytestmark = [
    pytest.mark.integracion,
    pytest.mark.skipif(
        os.environ.get("RASANTE_INTEGRACION") != "1",
        reason="requiere RASANTE_INTEGRACION=1 (golpea la API real de MINVU)",
    ),
]


def buscar_capa(capas: list[Capa], fragmento: str) -> Capa:
    """La capa cuyo nombre contiene `fragmento`, con un error legible si desapareció."""
    for capa in capas:
        if fragmento in capa.nombre:
            return capa
    raise AssertionError(f"no hay capa con {fragmento!r}: {sorted(c.nombre for c in capas)}")


def contar_en_la_api(cliente: httpx.Client, servicio: str, capa_id: int) -> int:
    """Features según el propio servidor. Es la referencia, no un literal escrito a mano."""
    respuesta = cliente.get(
        f"{URL_BASE}/{servicio}/MapServer/{capa_id}/query",
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
    )
    respuesta.raise_for_status()
    return int(respuesta.json()["count"])


def test_el_servicio_expone_capas() -> None:
    with ArcGIS() as ag:
        capas = ag.listar_capas(SERVICIO)

    assert capas, "el servicio no devolvió capas: ¿cambió la URL o el esquema?"
    assert all(isinstance(c.id, int) and c.nombre for c in capas)
    assert any(c.geometria == "esriGeometryPolygon" for c in capas), "geometryType cambió"


def test_la_comuna_piloto_sigue_en_el_servicio() -> None:
    with ArcGIS() as ag:
        buscar_capa(ag.listar_capas(SERVICIO), CAPA_PILOTO)


def test_el_conteo_descargado_coincide_con_el_de_la_api(tmp_path: Path) -> None:
    """Detecta truncamiento, que es el fallo silencioso que importa.

    **No** se compara contra un literal fijo: el PRC de una comuna cambia con el tiempo y un número
    escrito a mano rompería el test sin que nada esté mal. Se compara contra el `count` que reporta
    la API en el momento, con una página deliberadamente chica para forzar varias vueltas.
    """
    with ArcGIS() as ag:
        capas = ag.listar_capas(SERVICIO)
        capa = buscar_capa(capas, CAPA_PILOTO)
        with httpx.Client(timeout=60.0, follow_redirects=True) as cliente:
            esperado = contar_en_la_api(cliente, SERVICIO, capa.id)

        destino = ag.descargar_geojson(
            SERVICIO, capa.id, tmp_path / "capa.geojson", tamano_pagina=100
        )

    obtenido = len(json.loads(destino.read_text(encoding="utf-8"))["features"])
    assert obtenido == esperado, f"descarga truncada: {obtenido} de {esperado}"
