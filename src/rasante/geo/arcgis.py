"""Ingestor de servicios ArcGIS REST de MINVU (capa L0).

Los planes reguladores comunales de todo Chile están expuestos como MapServer consultables en
GeoJSON (`https://geoide.minvu.cl/server/rest/services/IPT`). Este módulo los lista y los baja a
disco para que el resto del sistema no dependa de la red.

Decisiones: D9 (caché en disco, tests sin red) en `design.md` §2.
Los tests usan `tests/fixtures/`, grabadas contra la API real.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

URL_BASE = "https://geoide.minvu.cl/server/rest/services"
TIEMPO_LIMITE = 60.0
# maxRecordCount que declara el servidor de MINVU. Ñuñoa tiene 1718 features: al borde.
# Por eso se pagina en vez de confiar en una sola respuesta.
MAX_REGISTROS = 2000


class ErrorArcGIS(RuntimeError):
    """Fallo al consultar o descargar de un servicio ArcGIS REST."""


@dataclass(frozen=True)
class Capa:
    """Una capa de un MapServer. `geometria` es el `geometryType` de Esri, sin normalizar."""

    id: int
    nombre: str
    geometria: str


class ArcGIS:
    """Cliente mínimo de ArcGIS REST. Inyectable para tests sin red."""

    def __init__(self, base: str = URL_BASE, cliente: httpx.Client | None = None) -> None:
        self._base = base.rstrip("/")
        self._cliente = cliente or httpx.Client(timeout=TIEMPO_LIMITE, follow_redirects=True)
        self._propio = cliente is None

    def close(self) -> None:
        if self._propio:
            self._cliente.close()

    def __enter__(self) -> ArcGIS:
        return self

    def __exit__(self, *_excepcion: object) -> None:
        self.close()

    def _json(self, url: str, parametros: dict[str, Any]) -> dict[str, Any]:
        try:
            respuesta = self._cliente.get(url, params=parametros)
        except httpx.HTTPError as error:
            raise ErrorArcGIS(f"fallo de red consultando {url}: {error}") from error
        if respuesta.status_code != 200:
            raise ErrorArcGIS(
                f"{url} respondió {respuesta.status_code}: {respuesta.text[:200]}"
            )
        try:
            datos: dict[str, Any] = respuesta.json()
        except ValueError as error:
            raise ErrorArcGIS(f"{url} no devolvió JSON válido") from error
        return datos

    def listar_capas(self, servicio: str) -> list[Capa]:
        """Capas declaradas por el MapServer de un servicio, p. ej. `IPT/PRC_RM_Norte`."""
        url = f"{self._base}/{servicio.strip('/')}/MapServer"
        datos = self._json(url, {"f": "json"})
        return [
            Capa(
                id=int(capa["id"]),
                nombre=str(capa["name"]),
                geometria=str(capa.get("geometryType", "")),
            )
            for capa in datos.get("layers", [])
        ]

    def descargar_geojson(
        self,
        servicio: str,
        capa_id: int,
        destino: Path,
        tamano_pagina: int = MAX_REGISTROS,
    ) -> Path:
        """Baja una capa completa a `destino` como GeoJSON. Idempotente.

        Si `destino` ya existe con contenido, no toca la red: es la caché (D9).
        Se recolectan todas las páginas antes de escribir, de modo que un fallo a mitad de
        camino no deja una caché parcial que luego se lea como si estuviera completa.
        """
        destino = Path(destino)
        if _cache_valida(destino):
            return destino

        features = list(self._paginar(servicio, capa_id, tamano_pagina))

        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_name(destino.name + ".parcial")
        try:
            temporal.write_text(_volcar(features), encoding="utf-8")
            temporal.replace(destino)  # atómico en POSIX
        finally:
            temporal.unlink(missing_ok=True)
        return destino

    def _paginar(self, servicio: str, capa_id: int, tamano_pagina: int) -> Iterator[dict[str, Any]]:
        url = f"{self._base}/{servicio.strip('/')}/MapServer/{capa_id}/query"
        offset = 0
        while True:
            datos = self._json(
                url,
                {
                    "where": "1=1",
                    "outFields": "*",
                    "f": "geojson",
                    "resultOffset": offset,
                    "resultRecordCount": tamano_pagina,
                },
            )
            features: list[dict[str, Any]] = datos.get("features", [])
            yield from features
            # `exceededTransferLimit` es la señal del servidor de que quedan páginas.
            if not features or not datos.get("exceededTransferLimit"):
                return
            offset += len(features)


def _cache_valida(destino: Path) -> bool:
    return destino.is_file() and destino.stat().st_size > 0


def _volcar(features: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"type": "FeatureCollection", "features": features},
        ensure_ascii=False,
        separators=(",", ":"),
    )
