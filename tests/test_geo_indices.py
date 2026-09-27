"""Índice espacial de zonas del PRC (T1.11).

`IndiceZonas.buscar(lat, lon)` responde la única pregunta que separa una coordenada de un veredicto:
**¿en qué zona del plan regulador está este predio?**

## Por qué NO se reproyecta

El diseño original decía "reproyectar EPSG:4326 → 3857 con `pyproj`". Se descartó al mirar el dato:
el servicio ArcGIS de MINVU **devuelve GeoJSON en EPSG:4326** y el ingestor no pide `outSR`, así que
el polígono y el punto ya están en el mismo CRS. Point-in-polygon es exacto en cualquier sistema de
coordenadas —no hay áreas ni distancias de por medio—, de modo que reproyectar sería trabajo y una
dependencia pesada (`pyproj` arrastra los datos de PROJ) **a cambio de nada**.

Si algún día una capa llega en un CRS proyectado, el lugar para reproyectar es la ingesta, no la
consulta: se convierte una vez, no en cada predicción.

## Lo que el índice NO hace

**No normaliza el código de zona.** El servicio devuelve códigos con espaciado irregular
(`'MH- 1'`, `'ZCH- 1'`) y el índice los devuelve tal cual. Corregirlos en silencio escondería que el
corpus y el servicio no coinciden; esa reconciliación es de T1.12, con su propio test.

**No decide en los bordes.** Un punto sobre el límite entre dos zonas intersecta las dos. `buscar`
devuelve una en orden determinista, pero `buscar_todas` expone la ambigüedad para quien tenga que
resolverla.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rasante.geo.indices import ErrorGeo, IndiceZonas

RAIZ = Path(__file__).resolve().parents[1]
FIXTURE_REAL = RAIZ / "tests" / "fixtures" / "arcgis_geom.geojson"

# Alrededor de Ñuñoa. GeoJSON escribe (lon, lat); la API es `buscar(lat, lon)`, y confundirlos es el
# error clásico de este módulo, así que hay un test dedicado.
LON0, LAT0 = -70.6300, -33.4800
LADO = 0.0010
BORDE = LON0 + LADO  # la misma expresión que usa el anillo: el float coincide bit a bit


def cuadrado(lon: float, lat: float, zona: str) -> dict[str, Any]:
    anillo = [
        [lon, lat],
        [lon + LADO, lat],
        [lon + LADO, lat + LADO],
        [lon, lat + LADO],
        [lon, lat],
    ]
    return {
        "type": "Feature",
        "properties": {"ZONA": zona},
        "geometry": {"type": "Polygon", "coordinates": [anillo]},
    }


def dos_zonas_vecinas() -> list[dict[str, Any]]:
    """Dos cuadrados que comparten el meridiano `BORDE`."""
    return [cuadrado(LON0, LAT0, "Z-A"), cuadrado(BORDE, LAT0, "Z-B")]


def indice(features: list[dict[str, Any]]) -> IndiceZonas:
    return IndiceZonas.desde_features(features)


# --- 1. lo básico ---


def test_un_punto_dentro_de_un_poligono_encuentra_su_zona() -> None:
    idx = indice([cuadrado(LON0, LAT0, "Z-A")])
    assert idx.buscar(lat=LAT0 + LADO / 2, lon=LON0 + LADO / 2) == "Z-A"


def test_un_punto_fuera_de_todo_poligono_no_encuentra_nada() -> None:
    idx = indice([cuadrado(LON0, LAT0, "Z-A")])
    assert idx.buscar(lat=-33.4000, lon=-70.5000) is None


def test_discrimina_entre_dos_zonas_vecinas() -> None:
    idx = indice(dos_zonas_vecinas())
    medio = LAT0 + LADO / 2
    assert idx.buscar(lat=medio, lon=LON0 + LADO / 4) == "Z-A"
    assert idx.buscar(lat=medio, lon=BORDE + LADO / 4) == "Z-B"


def test_un_indice_sin_features_no_encuentra_nada() -> None:
    assert indice([]).buscar(lat=LAT0, lon=LON0) is None


# --- 2. lat/lon no se confunden ---


def test_lat_y_lon_no_se_invierten() -> None:
    """GeoJSON escribe `(lon, lat)` y la API pide `(lat, lon)`. Invertirlos es el bug clásico.

    Y **no hay validación numérica que lo atrape**: `-70,6` es una latitud válida (la de la
    Antártida), así que invertirlos simplemente no encuentra nada. La defensa es que `lat` y `lon`
    sean **keyword-only**: la llamada posicional ni siquiera compila.
    """
    idx = indice([cuadrado(LON0, LAT0, "Z-A")])
    medio = LADO / 2
    assert idx.buscar(lat=LAT0 + medio, lon=LON0 + medio) == "Z-A"
    with pytest.raises(TypeError):
        idx.buscar(LAT0 + medio, LON0 + medio)  # type: ignore[call-arg]


def test_una_coordenada_fuera_de_rango_es_un_error() -> None:
    idx = indice([cuadrado(LON0, LAT0, "Z-A")])
    with pytest.raises(ErrorGeo, match="latitud"):
        idx.buscar(lat=91.0, lon=LON0)
    with pytest.raises(ErrorGeo, match="longitud"):
        idx.buscar(lat=LAT0, lon=181.0)


# --- 3. bordes: ambigüedad expuesta, no resuelta ---


def test_un_punto_en_el_borde_pertenece_a_las_dos_zonas() -> None:
    """Un predio sobre el límite entre dos zonas es ambiguo, y el índice no lo decide solo."""
    idx = indice(dos_zonas_vecinas())
    assert idx.buscar_todas(lat=LAT0 + LADO / 2, lon=BORDE) == ("Z-A", "Z-B")


def test_buscar_devuelve_una_sola_y_en_orden_determinista() -> None:
    idx = indice(dos_zonas_vecinas())
    assert idx.buscar(lat=LAT0 + LADO / 2, lon=BORDE) == "Z-A"


def test_buscar_todas_no_repite_zonas() -> None:
    """Dos polígonos de la MISMA zona que se solapan no son una ambigüedad."""
    solapados = [cuadrado(LON0, LAT0, "Z-A"), cuadrado(LON0 + LADO / 2, LAT0, "Z-A")]
    idx = indice(solapados)
    assert idx.buscar_todas(lat=LAT0 + LADO / 2, lon=LON0 + LADO * 0.75) == ("Z-A",)


# --- 4. el código llega como lo da el servicio ---


def test_el_codigo_no_se_normaliza() -> None:
    """`'MH- 1'` con espacio es lo que declara el servicio. Corregirlo en silencio taparía que el
    corpus y el servicio no coinciden, y eso hay que verlo, no esconderlo."""
    raro = cuadrado(LON0, LAT0, "MH- 1")
    assert indice([raro]).buscar(lat=LAT0 + LADO / 2, lon=LON0 + LADO / 2) == "MH- 1"


def test_una_feature_sin_zona_es_un_error() -> None:
    """Ignorarla haría desaparecer una zona del mapa sin que nadie se entere."""
    sin_zona = cuadrado(LON0, LAT0, "Z-A")
    sin_zona["properties"] = {}
    with pytest.raises(ErrorGeo, match="ZONA"):
        indice([sin_zona])


def test_una_feature_sin_geometria_es_un_error() -> None:
    huerfana = {"type": "Feature", "properties": {"ZONA": "Z-A"}, "geometry": None}
    with pytest.raises(ErrorGeo, match="geometr"):
        indice([huerfana])


# --- 5. geometrías ---


def test_soporta_multipolygon() -> None:
    """El servicio devuelve las dos formas: en Ñuñoa hay `Polygon` y `MultiPolygon`."""
    a = cuadrado(LON0, LAT0, "Z-A")["geometry"]["coordinates"][0]
    b = cuadrado(LON0 + LADO * 3, LAT0, "Z-A")["geometry"]["coordinates"][0]
    multi = {
        "type": "Feature",
        "properties": {"ZONA": "Z-A"},
        "geometry": {"type": "MultiPolygon", "coordinates": [[a], [b]]},
    }
    idx = indice([multi])
    assert idx.buscar(lat=LAT0 + LADO / 2, lon=LON0 + LADO / 2) == "Z-A"
    assert idx.buscar(lat=LAT0 + LADO / 2, lon=LON0 + LADO * 3.5) == "Z-A"
    assert idx.buscar(lat=LAT0 + LADO / 2, lon=LON0 + LADO * 2) is None


def test_una_geometria_invalida_se_repara_y_conserva_su_area() -> None:
    """Un anillo con un "pincho" de ancho cero es un defecto real y **no ambiguo**.

    `make_valid` lo repara conservando el cuadrado completo. El test comprueba contención porque acá
    la forma querida no está en duda: el pincho no aporta área.
    """
    pico = [
        [LON0, LAT0],
        [LON0 + LADO, LAT0],
        [LON0 + LADO, LAT0 + LADO],
        [LON0 + LADO / 2, LAT0 + LADO],
        [LON0 + LADO / 2, LAT0 + LADO * 2],
        [LON0 + LADO / 2, LAT0 + LADO],
        [LON0, LAT0 + LADO],
        [LON0, LAT0],
    ]
    feature = {
        "type": "Feature",
        "properties": {"ZONA": "Z-A"},
        "geometry": {"type": "Polygon", "coordinates": [pico]},
    }
    idx = indice([feature])
    for fraccion in (0.25, 0.5, 0.75):
        assert idx.buscar(lat=LAT0 + LADO * fraccion, lon=LON0 + LADO * fraccion) == "Z-A"
    assert idx.reparadas == ("Z-A",)


def test_un_lazo_verdadero_se_registra_aunque_la_reparacion_pierda_area() -> None:
    """Un anillo que se cruza a sí mismo es un dato **malo**, y su forma querida no se puede saber.

    `make_valid` conserva la parte que la orientación define como interior y descarta el resto. El
    índice no puede hacerlo mejor, así que hace lo único honesto: **registrar la zona reparada**
    para que quede rastro de que ahí se perdió cobertura. Este test no fija la forma resultante —es
    decisión de GEOS, no nuestra— sino que no revienta, que no queda vacía y que queda anotada.
    """
    lazo = [
        [LON0, LAT0],
        [LON0 + LADO, LAT0 + LADO],
        [LON0 + LADO, LAT0],
        [LON0, LAT0 + LADO],
        [LON0, LAT0],
    ]
    feature = {
        "type": "Feature",
        "properties": {"ZONA": "Z-A"},
        "geometry": {"type": "Polygon", "coordinates": [lazo]},
    }
    idx = indice([feature])
    assert idx.reparadas == ("Z-A",)
    assert idx.zonas == ("Z-A",)


def test_una_geometria_valida_no_figura_como_reparada() -> None:
    idx = indice(dos_zonas_vecinas())
    assert idx.reparadas == ()


# --- 6. desde un archivo, y contra la respuesta real de ArcGIS ---


def test_desde_geojson_lee_el_archivo(tmp_path: Path) -> None:
    ruta = tmp_path / "capa.geojson"
    ruta.write_text(
        json.dumps({"type": "FeatureCollection", "features": dos_zonas_vecinas()}),
        encoding="utf-8",
    )
    idx = IndiceZonas.desde_geojson(ruta)
    assert idx.buscar(lat=LAT0 + LADO / 2, lon=LON0 + LADO / 4) == "Z-A"


def test_desde_geojson_sin_coleccion_es_un_error(tmp_path: Path) -> None:
    ruta = tmp_path / "vacio.geojson"
    ruta.write_text('{"type": "Feature"}', encoding="utf-8")
    with pytest.raises(ErrorGeo, match="FeatureCollection"):
        IndiceZonas.desde_geojson(ruta)


def test_el_indice_es_utilizable_y_no_depende_de_la_red() -> None:
    """El fixture está grabado de la API real, así que este test no toca la red."""
    idx = IndiceZonas.desde_geojson(FIXTURE_REAL)
    assert idx.buscar(lat=-33.472219, lon=-70.621721) == "Z-2"


@pytest.mark.parametrize("indice_poligono", [0, 1])
def test_el_centro_de_cada_poligono_real_cae_en_su_propia_zona(indice_poligono: int) -> None:
    """La verificación fuerte sobre datos reales: cada polígono se encuentra a sí mismo."""
    datos = json.loads(FIXTURE_REAL.read_text(encoding="utf-8"))
    feature = datos["features"][indice_poligono]
    lon, lat = _centro_del_anillo(feature["geometry"])
    idx = IndiceZonas.desde_geojson(FIXTURE_REAL)
    assert idx.buscar(lat=lat, lon=lon) == feature["properties"]["ZONA"]


def _centro_del_anillo(geometria: dict[str, Any]) -> tuple[float, float]:
    anillos = (
        geometria["coordinates"]
        if geometria["type"] == "Polygon"
        else [a for poligono in geometria["coordinates"] for a in poligono]
    )
    puntos = [p for anillo in anillos for p in anillo]
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
