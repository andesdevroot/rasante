"""Ingesta del corpus normativo: descarga, extracción de texto y troceado por artículo (T0.5).

La OGUC consolidada se trocea de forma **determinista**, sin LLM: el motor no adivina dónde empieza
un artículo. Ver `doc/03-DISENO.md` §2.2 y §2.4.

El troceado es una función pura sobre texto, así que los tests corren sin red ni PDFs. La descarga
es cacheada, con el mismo patrón que `rasante.geo.arcgis` (D9).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import httpx

URL_OGUC = (
    "https://www.minvu.gob.cl/wp-content/uploads/2019/05/"
    "OGUC-Mayo-2026-D.S.-N5-D.O.-22-05-2026-rev-15.09.2026.pdf"
)
TIEMPO_LIMITE = 120.0

# Encabezado de artículo de la OGUC. Decisiones, todas verificadas contra el texto real:
#
#  - `A` mayúscula OBLIGATORIA, resto del vocablo tolerante a caso y tilde. Con IGNORECASE pleno
#    se cuelan referencias en minúscula que un salto de línea deja al inicio de línea
#    (p. ej. "...se refiere el \nartículo 116 Bis A)..."): 673 matches en vez de 591.
#  - el número exige al menos un punto. Así se descartan "Artículo 116" y "Artículo 2003", que
#    son de la LGUC o de notas, no de la OGUC.
#  - anclado a inicio de línea. Sin anclaje, las referencias dentro del cuerpo ("...el Artículo
#    4.5.6. de esta Ordenanza") se contarían como encabezados.
#  - el sufijo `bis` va DESPUÉS del punto, porque el formato real de la OGUC es
#    `Artículo  2.1.3. bis.` (con dos espacios y punto intermedio). Poner el grupo `BIS` antes del
#    punto detecta 0 de los 18 artículos `bis` reales y los etiqueta con su número base,
#    colisionando con el artículo base. Verificado contra el texto real.
#
# Con estas reglas, sobre la OGUC real: 591 matches, 582 únicos, 18 `bis`, ningún id sin punto y
# ningún par fuera de orden documental.
PATRON_ARTICULO = re.compile(
    r"(?m)^[ \t]*A(?i:rt[íi]culo)[ \t]+(\d+(?:\.\d+)+)"
    r"[ \t]*\.?[ \t]*(?i:(BIS)\b)?[ \t]*\.?[ \t]*"
)


class ErrorIngesta(RuntimeError):
    """Fallo al descargar, leer o trocear una fuente normativa."""


@dataclass(frozen=True)
class Articulo:
    """Un artículo de la OGUC, con su número normalizado (p. ej. `"2.2.4 bis"`)."""

    numero: str
    texto: str
    inicio: int


def trocear(texto: str) -> list[Articulo]:
    """Parte el texto consolidado en artículos, en orden documental.

    **Preserva los duplicados**: hay 5 números repetidos en la OGUC real. Descartarlos en silencio
    escondería un problema del documento fuente. Usa `indexar()` para consultar por número.
    """
    marcas = list(PATRON_ARTICULO.finditer(texto))
    articulos: list[Articulo] = []
    for posicion, marca in enumerate(marcas):
        fin = marcas[posicion + 1].start() if posicion + 1 < len(marcas) else len(texto)
        numero = f"{marca.group(1)} bis" if marca.group(2) else marca.group(1)
        articulos.append(
            Articulo(numero=numero, texto=texto[marca.end() : fin].strip(), inicio=marca.start())
        )
    return articulos


def indexar(articulos: Iterable[Articulo]) -> dict[str, Articulo]:
    """`numero -> Articulo`. Ante duplicados gana el primero."""
    indice: dict[str, Articulo] = {}
    for articulo in articulos:
        indice.setdefault(articulo.numero, articulo)
    return indice


def descargar_fuente(
    url: str, destino: Path, cliente: httpx.Client | None = None
) -> Path:
    """Descarga una fuente normativa a `destino`. Idempotente: si ya existe, no toca la red.

    Escribe vía archivo temporal para que un fallo no deje un PDF a medias que luego se lea
    como si estuviera completo.
    """
    destino = Path(destino)
    if _cache_valida(destino):
        return destino

    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=TIEMPO_LIMITE, follow_redirects=True)
    try:
        try:
            respuesta = cliente.get(url)
        except httpx.HTTPError as error:
            raise ErrorIngesta(f"fallo de red descargando {url}: {error}") from error
        if respuesta.status_code != 200:
            raise ErrorIngesta(f"{url} respondió {respuesta.status_code}")
        contenido = respuesta.content
    finally:
        if propio:
            cliente.close()

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".parcial")
    try:
        temporal.write_bytes(contenido)
        temporal.replace(destino)  # atómico en POSIX
    finally:
        temporal.unlink(missing_ok=True)
    return destino


def extraer_texto(pdf: Path) -> str:
    """Texto plano de un PDF. `pypdf` se importa acá para que `trocear` no dependa de nada."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    pdf = Path(pdf)
    try:
        lector = PdfReader(pdf)
        return "\n".join((pagina.extract_text() or "") for pagina in lector.pages)
    except (PdfReadError, OSError, ValueError) as error:
        raise ErrorIngesta(f"no se pudo leer el PDF {pdf}: {error}") from error


def _cache_valida(destino: Path) -> bool:
    return destino.is_file() and destino.stat().st_size > 0
