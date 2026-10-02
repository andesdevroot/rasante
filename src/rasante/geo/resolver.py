"""Resolución de una coordenada a la zona del corpus (T1.12). Capa L0.

Une dos piezas que ya existen por separado: el índice espacial (`geo.indices`, T1.11) dice **en qué
zona del PRC** cae el predio, y el corpus dice **qué valores tiene esa zona**. Este módulo es la
costura, y su único trabajo real es **no confundir tres fallos distintos**:

| excepción | qué pasó | quién lo arregla |
|---|---|---|
| `SinZonaError` | la coordenada no está en ninguna zona del PRC | quien la escribió |
| `ZonaSinCorpusError` | está en `Z-4`, y el corpus no tiene `Z-4` | quien cura el corpus |
| `ZonaAmbiguaError` | el punto cae en el límite entre dos zonas | una persona |

Decir "no se pudo resolver" para los tres es lo cómodo y lo inútil. El primero es un error de
entrada, el segundo es trabajo pendiente y el tercero es una ambigüedad del plano que **el programa
no puede resolver sin inventar**.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ..dominio.modelos import Zona
from .indices import IndiceZonas


class ErrorResolucion(RuntimeError):
    """Un nombre base para que el llamador pueda atrapar los tres de una vez, si quiere."""


class SinZonaError(ErrorResolucion):
    """La coordenada no cae en ninguna zona del plan regulador."""


class ZonaSinCorpusError(ErrorResolucion):
    """La coordenada cae en una zona que el corpus todavía no tiene transcrita."""


class ZonaAmbiguaError(ErrorResolucion):
    """La coordenada cae en el límite de dos o más zonas, y las dos están en el corpus."""


def _clave(codigo: str) -> str:
    """Clave de comparación de un código de zona.

    Se ignoran los **espacios**, y solo los espacios. No es una licencia: el servicio de MINVU
    declara `'MH- 1'` y `'ZCH- 1'` con un espacio interior que viene de cómo el PDF escribe el
    rótulo, no de que sean zonas distintas. En un identificador, el espacio no es información.

    Todo lo demás se respeta: `Z-4m` y `Z-4` son zonas **distintas** y hay un test que lo fija.
    """
    return "".join(codigo.split()).upper()


@dataclass(frozen=True, slots=True)
class CorpusZonas:
    """Las zonas del corpus, indexadas por código para resolver en O(1)."""

    _por_clave: Mapping[str, Zona]
    _por_codigo: Mapping[str, Zona]

    @classmethod
    def desde_zonas(cls, zonas: Iterable[Zona]) -> CorpusZonas:
        por_codigo: dict[str, Zona] = {}
        por_clave: dict[str, Zona] = {}
        for zona in zonas:
            if zona.codigo in por_codigo:
                raise ErrorResolucion(f"el corpus declara dos veces la zona {zona.codigo!r}")
            por_codigo[zona.codigo] = zona
            por_clave[_clave(zona.codigo)] = zona
        return cls(
            _por_clave=MappingProxyType(por_clave), _por_codigo=MappingProxyType(por_codigo)
        )

    @property
    def codigos(self) -> tuple[str, ...]:
        return tuple(sorted(self._por_codigo))

    def buscar(self, codigo: str) -> Zona | None:
        """La zona del corpus para ese código del servicio, o `None` si no está transcrita."""
        exacta = self._por_codigo.get(codigo)
        if exacta is not None:
            return exacta
        return self._por_clave.get(_clave(codigo))


def resolver_zona(
    lat: float, lon: float, *, indice: IndiceZonas, corpus: CorpusZonas
) -> Zona:
    """La `Zona` del corpus en la que cae la coordenada. Levanta si no se puede afirmar cuál es.

    Los tres fallos se levantan **distintos** a propósito. Un llamador que los trate igual va a
    mandar a revisar la coordenada cuando el problema era que falta transcribir una zona, y al
    revés. La CLI (T1.13) los mapea a códigos de salida diferentes por la misma razón.

    `lat` y `lon` son keyword-only en el índice y acá se pasan como posicionales en ese mismo orden:
    la firma repite el orden para que no haya dos convenciones conviviendo.
    """
    codigos = indice.buscar_todas(lat=lat, lon=lon)
    if not codigos:
        raise SinZonaError(
            f"la coordenada ({lat}, {lon}) no cae en ninguna zona del plan regulador"
        )

    encontradas = [zona for codigo in codigos if (zona := corpus.buscar(codigo)) is not None]
    if not encontradas:
        raise ZonaSinCorpusError(
            f"la coordenada ({lat}, {lon}) cae en {list(codigos)}, y el corpus no tiene ninguna de "
            f"esas zonas. Transcritas: {list(corpus.codigos)}"
        )
    if len(encontradas) > 1:
        raise ZonaAmbiguaError(
            f"la coordenada ({lat}, {lon}) cae en el límite de "
            f"{sorted(z.codigo for z in encontradas)}: hay que decidir cuál rige"
        )
    return encontradas[0]
