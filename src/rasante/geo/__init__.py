"""Capa L0: fuentes autoritativas. ArcGIS REST de MINVU e índice espacial de zonas.

Es la única capa con red y con dependencias geoespaciales (`shapely`, `httpx`).

**No usa `pyproj`.** El diseño lo preveía para reproyectar EPSG:4326 → 3857, pero el servicio de
MINVU ya devuelve GeoJSON en 4326 y el punto de consulta llega en el mismo CRS, así que reproyectar
sería una dependencia pesada a cambio de nada. Ver `indices.py`.
"""

from __future__ import annotations
