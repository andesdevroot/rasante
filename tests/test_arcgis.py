"""Tests del ingestor ArcGIS REST (T0.2).

Corren **sin red**: las respuestas vienen de `tests/fixtures/`, grabadas una vez contra la API
real de MINVU. Decisión D9 (`doc/03-DISENO.md` §1): los tests no dependen de que el servicio
esté arriba.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from rasante.geo.arcgis import ArcGIS, ErrorArcGIS

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(nombre: str) -> dict:
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


class ServidorFalso:
    """Sirve fixtures y registra las peticiones recibidas."""

    def __init__(
        self, catalogo: dict | None = None, paginas: dict[int, dict] | None = None
    ) -> None:
        self.catalogo = catalogo or {}
        self.paginas = paginas or {}
        self.peticiones: list[httpx.Request] = []

    def handler(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        if peticion.url.path.endswith("/query"):
            offset = int(dict(peticion.url.params).get("resultOffset", 0))
            cuerpo = self.paginas.get(offset, {"type": "FeatureCollection", "features": []})
            return httpx.Response(200, json=cuerpo)
        return httpx.Response(200, json=self.catalogo)

    @property
    def offsets(self) -> list[int]:
        return [
            int(dict(p.url.params).get("resultOffset", 0))
            for p in self.peticiones
            if p.url.path.endswith("/query")
        ]

    def cliente(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


# --- listar_capas ---


def test_listar_capas_parsea_el_catalogo() -> None:
    servidor = ServidorFalso(catalogo=fixture("arcgis_catalogo.json"))
    capas = ArcGIS(cliente=servidor.cliente()).listar_capas("IPT/PRC_RM_Norte")

    assert len(capas) > 10
    assert all(isinstance(c.id, int) for c in capas)
    assert all(c.nombre for c in capas)

    las_condes = next(c for c in capas if c.nombre == "PRC_Las_Condes")
    assert las_condes.id == 11
    assert las_condes.geometria == "esriGeometryPolygon"


def test_error_http_es_explicito() -> None:
    transporte = httpx.MockTransport(lambda _: httpx.Response(500, text="boom"))
    with pytest.raises(ErrorArcGIS, match="500"):
        ArcGIS(cliente=httpx.Client(transport=transporte)).listar_capas("IPT/PRC_RM_Norte")


# --- descargar_geojson ---


def test_descargar_recorre_todas_las_paginas(tmp_path: Path) -> None:
    servidor = ServidorFalso(
        paginas={0: fixture("arcgis_pagina_1.json"), 3: fixture("arcgis_pagina_2.json")}
    )
    destino = ArcGIS(cliente=servidor.cliente()).descargar_geojson(
        "IPT/PRC_RM_Norte", 17, tmp_path / "nunoa.geojson", tamano_pagina=3
    )

    coleccion = json.loads(destino.read_text(encoding="utf-8"))
    assert coleccion["type"] == "FeatureCollection"
    assert len(coleccion["features"]) == 6  # 3 de la página 1 + 3 de la página 2
    # La página 1 trae exceededTransferLimit y la 2 no: debe parar tras la segunda.
    assert servidor.offsets == [0, 3]


def test_descargar_sin_exceeded_no_pide_una_pagina_de_mas(tmp_path: Path) -> None:
    servidor = ServidorFalso(paginas={0: fixture("arcgis_pagina_2.json")})
    destino = ArcGIS(cliente=servidor.cliente()).descargar_geojson(
        "IPT/PRC_RM_Norte", 17, tmp_path / "x.geojson", tamano_pagina=3
    )

    assert len(json.loads(destino.read_text(encoding="utf-8"))["features"]) == 3
    assert servidor.offsets == [0]


def test_descargar_preserva_la_geometria(tmp_path: Path) -> None:
    servidor = ServidorFalso(paginas={0: fixture("arcgis_geom.geojson")})
    destino = ArcGIS(cliente=servidor.cliente()).descargar_geojson(
        "IPT/PRC_RM_Norte", 17, tmp_path / "geom.geojson", tamano_pagina=3
    )

    features = json.loads(destino.read_text(encoding="utf-8"))["features"]
    assert features[0]["geometry"]["type"] == "Polygon"
    assert features[0]["geometry"]["coordinates"]


def test_cache_evita_la_red(tmp_path: Path) -> None:
    servidor = ServidorFalso(paginas={0: fixture("arcgis_pagina_1.json")})
    destino = tmp_path / "ya-existe.geojson"
    destino.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")

    resultado = ArcGIS(cliente=servidor.cliente()).descargar_geojson(
        "IPT/PRC_RM_Norte", 17, destino, tamano_pagina=3
    )

    assert resultado == destino
    assert servidor.peticiones == [], "no debe tocar la red si el destino ya existe"
    assert json.loads(destino.read_text(encoding="utf-8"))["features"] == []


def test_cache_ignora_archivo_vacio(tmp_path: Path) -> None:
    servidor = ServidorFalso(paginas={0: fixture("arcgis_pagina_2.json")})
    destino = tmp_path / "vacio.geojson"
    destino.write_text("", encoding="utf-8")

    ArcGIS(cliente=servidor.cliente()).descargar_geojson(
        "IPT/PRC_RM_Norte", 17, destino, tamano_pagina=3
    )

    assert servidor.offsets == [0], "un archivo vacío no es caché válida"
    assert len(json.loads(destino.read_text(encoding="utf-8"))["features"]) == 3


def test_error_http_al_descargar_es_explicito(tmp_path: Path) -> None:
    transporte = httpx.MockTransport(lambda _: httpx.Response(503))
    with pytest.raises(ErrorArcGIS, match="503"):
        ArcGIS(cliente=httpx.Client(transport=transporte)).descargar_geojson(
            "IPT/PRC_RM_Norte", 17, tmp_path / "x.geojson"
        )


def test_no_deja_archivo_a_medias_si_falla(tmp_path: Path) -> None:
    """Si la descarga falla, no debe quedar un GeoJSON parcial: sería caché envenenada."""
    llamadas = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return httpx.Response(200, json=fixture("arcgis_pagina_1.json"))
        return httpx.Response(500)

    destino = tmp_path / "parcial.geojson"
    with pytest.raises(ErrorArcGIS):
        ArcGIS(cliente=httpx.Client(transport=httpx.MockTransport(handler))).descargar_geojson(
            "IPT/PRC_RM_Norte", 17, destino, tamano_pagina=3
        )

    assert not destino.exists(), "no debe persistir una descarga incompleta"
