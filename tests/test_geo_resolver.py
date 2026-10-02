"""Resolución de una coordenada a la zona del corpus (T1.12).

Une las dos piezas: el índice espacial (T1.11) dice **en qué zona del PRC** está el predio, y el
corpus dice **qué valores tiene esa zona**. Entre las dos hay tres cosas que pueden salir mal, y
**confundirlas es el bug de este módulo**:

| | qué pasó | qué hacer |
|---|---|---|
| `SinZonaError` | la coordenada no está en ninguna zona del PRC | revisar la coordenada |
| `ZonaSinCorpusError` | está en `Z-4`, y el corpus no la tiene | **transcribir la zona** |
| `ZonaAmbiguaError` | el punto cae en el límite entre dos zonas | que lo decida una persona |

Decir "no se pudo resolver" para los tres es lo cómodo y es lo inútil: el primero es un error
de entrada, el segundo es trabajo de corpus pendiente y el tercero es una ambigüedad del plano.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from rasante.corpus.cargador import cargar_zonas
from rasante.dominio.modelos import (
    Cita,
    EstadoParametro,
    EstadoRevision,
    Limite,
    Parametro,
    Procedencia,
    Sentido,
    TipoLimite,
    Vigencia,
    Zona,
)
from rasante.geo.indices import IndiceZonas
from rasante.geo.resolver import (
    CorpusZonas,
    SinZonaError,
    ZonaAmbiguaError,
    ZonaSinCorpusError,
    resolver_zona,
)

RAIZ = Path(__file__).resolve().parents[1]
CITA = Cita(norma_id="prc:nunoa", articulo="26", texto="cuadro normativo")

LON0, LAT0, LADO = -70.6300, -33.4800, 0.0010
BORDE = LON0 + LADO


def zona(codigo: str) -> Zona:
    return Zona(
        codigo=codigo,
        nombre=codigo,
        comuna="Ñuñoa",
        parametros={
            "cus": Parametro(
                id="cus",
                limites=(Limite(TipoLimite.BASE, Decimal("2"), "adimensional", CITA),),
                sentido=Sentido.MAXIMO,
                estado=EstadoParametro.APLICABLE,
                cita=CITA,
            )
        },
        vigencia=Vigencia(),
        procedencia=Procedencia(
            url_fuente="https://x.cl/o.pdf",
            hash_fuente="sha256:" + "0" * 64,
            consolidado_por="refundido",
            extraido="2026-09-27",
            revisado_por="Revisor de prueba",
            estado=EstadoRevision.REVISADO,
        ),
    )


def cuadrado(lon: float, codigo: str) -> dict[str, object]:
    anillo = [
        [lon, LAT0],
        [lon + LADO, LAT0],
        [lon + LADO, LAT0 + LADO],
        [lon, LAT0 + LADO],
        [lon, LAT0],
    ]
    return {
        "type": "Feature",
        "properties": {"ZONA": codigo},
        "geometry": {"type": "Polygon", "coordinates": [anillo]},
    }


def indice(*codigos: tuple[float, str]) -> IndiceZonas:
    return IndiceZonas.desde_features([cuadrado(lon, c) for lon, c in codigos])


# --- 1. el camino feliz ---


def test_una_coordenada_dentro_de_una_zona_del_corpus_devuelve_sus_parametros() -> None:
    idx = indice((LON0, "Z-4"))
    corpus = CorpusZonas.desde_zonas([zona("Z-4")])
    z = resolver_zona(LAT0 + LADO / 2, LON0 + LADO / 2, indice=idx, corpus=corpus)
    assert z.codigo == "Z-4"
    assert "cus" in z.parametros
    assert z.procedencia.revisada is True


def test_sobre_el_corpus_real() -> None:
    """La única zona transcrita es Z-2, y su geometría está en el fixture del índice."""
    idx = IndiceZonas.desde_geojson(RAIZ / "tests" / "fixtures" / "arcgis_geom.geojson")
    corpus = CorpusZonas.desde_zonas(cargar_zonas(RAIZ / "corpus"))
    z = resolver_zona(-33.472219, -70.621721, indice=idx, corpus=corpus)
    assert z.codigo == "Z-2"
    assert len(z.parametros) == 12


# --- 2. los tres fallos, y no se confunden ---


def test_una_coordenada_fuera_de_todo_el_prc_es_sin_zona() -> None:
    """El mensaje **no** nombra ninguna zona: no hay ninguna que nombrar, y eso es el punto."""
    idx = indice((LON0, "Z-4"))
    corpus = CorpusZonas.desde_zonas([zona("Z-4")])
    with pytest.raises(SinZonaError, match="no cae en ninguna zona"):
        resolver_zona(-33.4000, -70.5000, indice=idx, corpus=corpus)


def test_una_zona_que_el_corpus_no_tiene_es_otro_error() -> None:
    """El caso real de hoy: Ñuñoa tiene 40 zonas en el servicio y **una** transcrita."""
    idx = indice((LON0, "Z-4"))
    corpus = CorpusZonas.desde_zonas([zona("Z-2")])
    with pytest.raises(ZonaSinCorpusError, match="Z-4"):
        resolver_zona(LAT0 + LADO / 2, LON0 + LADO / 2, indice=idx, corpus=corpus)


def test_los_dos_errores_no_son_el_mismo() -> None:
    """Se atrapan por separado: uno es error de entrada, el otro es trabajo pendiente."""
    idx = indice((LON0, "Z-4"))
    corpus = CorpusZonas.desde_zonas([zona("Z-2")])
    with pytest.raises(SinZonaError):
        resolver_zona(-33.4000, -70.5000, indice=idx, corpus=corpus)
    try:
        resolver_zona(LAT0 + LADO / 2, LON0 + LADO / 2, indice=idx, corpus=corpus)
    except SinZonaError:  # pragma: no cover
        raise AssertionError("una zona sin corpus no es una coordenada sin zona") from None
    except ZonaSinCorpusError:
        pass


def test_un_punto_en_el_limite_entre_dos_zonas_es_ambiguo() -> None:
    """`buscar_todas` devuelve dos y el resolutor **no elige**: elegir sería inventar."""
    idx = indice((LON0, "Z-A"), (BORDE, "Z-B"))
    corpus = CorpusZonas.desde_zonas([zona("Z-A"), zona("Z-B")])
    with pytest.raises(ZonaAmbiguaError, match="Z-A"):
        resolver_zona(LAT0 + LADO / 2, BORDE, indice=idx, corpus=corpus)


def test_una_zona_del_indice_que_no_esta_en_el_corpus_no_vuelve_ambigua_al_punto() -> None:
    """Si el punto toca dos zonas y solo una está transcrita, se resuelve a esa.

    Es el caso real: el servicio devuelve 40 zonas, el corpus tiene una. Que la otra no esté **no**
    hace ambigua la coordenada; hace que falte corpus, y eso ya lo dice `ZonaSinCorpusError` cuando
    corresponde.
    """
    idx = indice((LON0, "Z-A"), (BORDE, "Z-ZZ"))
    corpus = CorpusZonas.desde_zonas([zona("Z-A")])
    z = resolver_zona(LAT0 + LADO / 2, BORDE, indice=idx, corpus=corpus)
    assert z.codigo == "Z-A"


# --- 3. el espaciado irregular del servicio (hallazgo de T1.11) ---


def test_el_espaciado_interior_del_codigo_no_impide_resolver() -> None:
    """El servicio declara `'MH- 1'` y el corpus tendrá `MH-1` o `MH- 1`: es el mismo código.

    El espacio viene de cómo el PDF escribe el rótulo, no es información. Se normaliza **para
    comparar**, y el código que se devuelve es el de la **zona del corpus**, no el del servicio.
    """
    idx = indice((LON0, "MH- 1"))
    corpus = CorpusZonas.desde_zonas([zona("MH-1")])
    z = resolver_zona(LAT0 + LADO / 2, LON0 + LADO / 2, indice=idx, corpus=corpus)
    assert z.codigo == "MH-1"


def test_la_normalizacion_solo_ignora_espacios() -> None:
    """No se parece "casi": `Z-4m` y `Z-4` son zonas distintas y no deben confundirse."""
    idx = indice((LON0, "Z-4m"))
    corpus = CorpusZonas.desde_zonas([zona("Z-4")])
    with pytest.raises(ZonaSinCorpusError):
        resolver_zona(LAT0 + LADO / 2, LON0 + LADO / 2, indice=idx, corpus=corpus)


def test_un_corpus_vacio_no_resuelve_nada() -> None:
    idx = indice((LON0, "Z-4"))
    vacio = CorpusZonas.desde_zonas([])
    with pytest.raises(ZonaSinCorpusError):
        resolver_zona(LAT0 + LADO / 2, LON0 + LADO / 2, indice=idx, corpus=vacio)
