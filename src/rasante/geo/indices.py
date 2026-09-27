"""Índice espacial de zonas del PRC (T1.11). Capa L0.

`IndiceZonas.buscar(lat, lon)` responde la única pregunta que separa una coordenada de un veredicto:
**¿en qué zona del plan regulador está este predio?**

## Por qué NO se reproyecta

El diseño original decía "reproyectar EPSG:4326 → 3857 con `pyproj`". Se descartó al mirar el dato:
el servicio ArcGIS de MINVU **devuelve GeoJSON en EPSG:4326** (`f=geojson` y sin `outSR`) y el
ingestor no lo cambia, así que el polígono y el punto ya están en el mismo CRS. Point-in-polygon es
exacto en cualquier sistema de coordenadas —no hay áreas ni distancias de por medio—, de modo que
reproyectar sería trabajo y una dependencia pesada (`pyproj` arrastra los datos de PROJ) **a cambio
de nada**.

Si alguna vez una capa llega en un CRS proyectado, el lugar para reproyectar es la **ingesta**,
no la consulta: se convierte una vez, no en cada predicción. Ver D9.

## Lo que el índice NO hace

**No normaliza el código de zona.** El servicio devuelve códigos irregulares —en Ñuñoa hay
`'MH- 1'` y `'ZCH- 1'`, con espacio interior— y el índice los devuelve tal cual. Corregirlos en
silencio escondería que el corpus y el servicio no coinciden; esa reconciliación es de T1.12, con su
propio test. Lo único que se recorta es el espacio de los **extremos**, que no es parte del nombre.

**No decide en los bordes.** Un punto sobre el límite entre dos zonas intersecta las dos. `buscar`
devuelve una en orden determinista —lo necesita la CLI—, pero `buscar_todas` expone la ambigüedad
para quien tenga que resolverla.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shapely import make_valid
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

CRS = "EPSG:4326"
"""El CRS del servicio. No se reproyecta: el punto de consulta llega en el mismo."""


class ErrorGeo(RuntimeError):
    """Una capa del PRC no se pudo indexar, o la consulta no es una coordenada válida."""


@dataclass(frozen=True, eq=False)
class IndiceZonas:
    """Las zonas del PRC, indexadas para responder point-in-polygon.

    `eq=False` a propósito: la igualdad por campos compararía árboles espaciales, que no tienen un
    orden ni una identidad útil. Dos índices con las mismas zonas son iguales para quien los usa,
    pero lo que importa es que **consulten** bien, y eso lo fijan los tests.
    """

    _arbol: STRtree | None
    _geometrias: tuple[BaseGeometry, ...]
    _zonas: tuple[str, ...]
    _reparadas: tuple[str, ...] = ()

    @classmethod
    def desde_features(cls, features: Sequence[Mapping[str, Any]]) -> IndiceZonas:
        """Construye el índice desde las `features` de una respuesta GeoJSON del servicio.

        Una feature sin `ZONA` o sin geometría **corta la carga**: descartarla en silencio haría
        desaparecer una zona del mapa, y el revisor no tendría cómo notarlo.
        """
        geometrias: list[BaseGeometry] = []
        zonas: list[str] = []
        reparadas: list[str] = []
        for indice, feature in enumerate(features):
            propiedades = feature.get("properties") or {}
            # Se recorta el espacio de los extremos, que no es parte del identificador. El interior
            # se respeta: `'MH- 1'` es lo que declara el servicio y así se devuelve.
            zona = str(propiedades.get("ZONA") or "").strip()
            if not zona:
                raise ErrorGeo(f"la feature {indice} no declara 'ZONA'")
            cruda = feature.get("geometry")
            if not cruda:
                raise ErrorGeo(f"la feature {indice} ('{zona}') no trae geometría")
            geometria = shape(cruda)
            if not geometria.is_valid:
                # Un anillo auto-intersectado es común en datos municipales. Se repara para no
                # perder la zona, pero **se registra**: la reparación descarta el área que el anillo
                # no define como interior, y eso no puede pasar desapercibido.
                geometria = make_valid(geometria)
                reparadas.append(zona)
            if geometria.is_empty:
                raise ErrorGeo(
                    f"la feature {indice} ('{zona}') quedó vacía al reparar su geometría"
                )
            geometrias.append(geometria)
            zonas.append(zona)
        arbol = STRtree(geometrias) if geometrias else None
        return cls(
            _arbol=arbol,
            _geometrias=tuple(geometrias),
            _zonas=tuple(zonas),
            _reparadas=tuple(reparadas),
        )

    @classmethod
    def desde_geojson(cls, ruta: Path) -> IndiceZonas:
        """Carga una capa ya descargada. No toca la red: eso lo hizo `geo.arcgis` (D9)."""
        ruta = Path(ruta)
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ErrorGeo(f"{ruta.name}: no se pudo leer como GeoJSON: {error}") from error
        if not isinstance(datos, dict) or datos.get("type") != "FeatureCollection":
            raise ErrorGeo(f"{ruta.name}: no es una FeatureCollection de GeoJSON")
        return cls.desde_features(datos.get("features") or [])

    @property
    def zonas(self) -> tuple[str, ...]:
        """Los códigos declarados, tal como los da el servicio, en orden de carga."""
        return self._zonas

    @property
    def reparadas(self) -> tuple[str, ...]:
        """Las zonas cuya geometría venía inválida y hubo que reparar.

        Se expone porque la reparación **descarta área**: `make_valid` conserva solo la parte que el
        anillo define como interior, así que un polígono auto-intersectado pierde el resto. Callarlo
        dejaría un pedazo del mapa sin cobertura y sin que nadie lo sepa.
        """
        return self._reparadas

    def buscar_todas(self, *, lat: float, lon: float) -> tuple[str, ...]:
        """Todas las zonas que contienen el punto, sin repetir y en orden determinista.

        Más de una significa que el punto está en un borde compartido. El índice **no elige**.

        `lat` y `lon` son **keyword-only** a propósito: GeoJSON escribe `(lon, lat)` y esta API pide
        `(lat, lon)`. Invertirlos no siempre falla —`-70,6` es una latitud válida, la de la
        Antártida— así que la única defensa real es obligar a nombrarlos.
        """
        _exigir_coordenada(lat, lon)
        if self._arbol is None:
            return ()
        # GeoJSON y `Point` escriben (x, y) = (lon, lat). La API de acá es (lat, lon) porque es el
        # orden en que se lee una coordenada en Chile.
        encontrados = self._arbol.query(Point(lon, lat), predicate="intersects")
        return tuple(sorted({self._zonas[int(i)] for i in encontrados}))

    def buscar(self, *, lat: float, lon: float) -> str | None:
        """La zona del punto, o `None` si está fuera de todas.

        Si el punto cae en un borde, devuelve la primera en orden alfabético —determinista, para que
        dos corridas coincidan—. Quien necesite distinguir un borde de un punto interior usa
        `buscar_todas`.
        """
        todas = self.buscar_todas(lat=lat, lon=lon)
        return todas[0] if todas else None


def _exigir_coordenada(lat: float, lon: float) -> None:
    """Descarta valores imposibles antes de consultar.

    **Lo que esto NO atrapa, y hay que decirlo:** el intercambio de latitud y longitud cuando ambos
    valores caen en rango. `-70,6` es una latitud perfectamente válida, así que la consulta
    simplemente no encuentra nada y parece que el predio está fuera del PRC. Contra eso no hay
    validación numérica que sirva: la defensa es que `buscar` reciba `lat` y `lon` por nombre.
    """
    if not -90.0 <= lat <= 90.0:
        raise ErrorGeo(f"la latitud {lat} está fuera de rango")
    if not -180.0 <= lon <= 180.0:
        raise ErrorGeo(f"la longitud {lon} está fuera de rango")
