"""Carga del corpus al dominio (T1.4 y T1.6).

Es el **puente** entre el corpus (dato, YAML) y el dominio (puro, sin dependencias). Puede usar
`pyyaml`; el dominio no. La dirección de la dependencia es siempre `corpus` → `dominio`, nunca al
revés.

Acá vive la lectura de `derivaciones` y `relaciones` (T1.4). La lectura de zonas llega en T1.6.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from rasante.corpus.esquema import ErrorEsquema, validar_documento
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
from rasante.dominio.reglas import Derivacion, Hecho, Reglas, Relacion


class ErrorCarga(ValueError):
    """Un documento del corpus no se pudo convertir al dominio."""


def cargar_reglas(raiz: Path) -> Reglas:
    """Lee `derivaciones` y `relaciones` de todos los documentos del corpus bajo `raiz`.

    No falla si no hay ninguna: un corpus sin reglas es un corpus del que no se puede calcular nada,
    y todo saldrá `P`. Eso es correcto, no un error.
    """
    derivaciones: dict[str, Derivacion] = {}
    relaciones: list[Relacion] = []
    hechos: dict[str, Hecho] = {}

    for archivo in sorted(Path(raiz).rglob("*.yaml")):
        datos = _leer(archivo)
        for clave, derivacion in (datos.get("derivaciones") or {}).items():
            derivaciones[clave] = Derivacion(
                parametro=clave,
                expresion=str(derivacion["expresion"]),
                cita=_cita(derivacion.get("cita"), datos, archivo),
            )
        for nombre, hecho in (datos.get("hechos") or {}).items():
            hechos[nombre] = Hecho(
                nombre=nombre,
                expresion=str(hecho["expresion"]),
                cita=_cita(hecho.get("cita"), datos, archivo),
            )
        for relacion in datos.get("relaciones") or []:
            relaciones.append(
                Relacion(
                    tipo=str(relacion["tipo"]),
                    objetivo=str(relacion["objetivo"]),
                    expresion=str(relacion["expresion"]),
                    cita=_cita(relacion.get("cita"), datos, archivo),
                )
            )

    return Reglas(
        derivaciones=MappingProxyType(derivaciones),
        relaciones=tuple(relaciones),
        hechos=MappingProxyType(hechos),
    )


class _SinDuplicados(yaml.SafeLoader):
    """Un `SafeLoader` que **falla** ante una clave repetida.

    PyYAML no las detecta: se queda con la última y descarta la otra en silencio. Con `cos` teniendo
    variantes, eso perdería una regla sin que nadie se entere.
    """


def _mapeo_sin_duplicados(
    loader: _SinDuplicados, nodo: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    vistos: set[Any] = set()
    for clave_nodo, _ in nodo.value:
        clave = loader.construct_object(clave_nodo, deep=deep)
        if clave in vistos:
            raise ErrorCarga(f"clave duplicada en el YAML: {clave!r}")
        vistos.add(clave)
    return yaml.SafeLoader.construct_mapping(loader, nodo, deep)


_SinDuplicados.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapeo_sin_duplicados
)


def decimal_de(texto: Any) -> Decimal:
    """Convierte el texto de una ordenanza a `Decimal` sin adivinar.

    La ordenanza de Ñuñoa escribe `0,6`. Un `float(texto)` o un `Decimal` ingenuo sobre `"0,6"`
    fallaría, y peor: tratar la coma como separador de miles daría `6`, diez veces el coeficiente.
    Por eso el caso ambiguo **no se resuelve: se rechaza**.
    """
    limpio = str(texto).strip().replace(" ", "")
    if not limpio:
        raise ErrorCarga("valor vacío")
    if "," in limpio:
        entero, _, decimales = limpio.rpartition(",")
        if "," in entero:
            raise ErrorCarga(f"{limpio!r}: más de una coma")
        limpio = entero.replace(".", "") + "." + decimales
    elif limpio.count(".") == 1:
        entero, _, decimales = limpio.partition(".")
        if len(decimales) == 3 and entero.isdigit() and entero != "0":
            raise ErrorCarga(
                f"{limpio!r} es ambiguo: ¿{entero}{decimales} (miles) o {entero} coma {decimales}? "
                f"Escribe '{entero}{decimales}' o '{entero},{decimales}'."
            )
    elif limpio.count(".") > 1:
        limpio = limpio.replace(".", "")
    try:
        return Decimal(limpio)
    except InvalidOperation as error:
        raise ErrorCarga(f"{limpio!r} no es un número válido") from error


def cargar_zona(archivo: Path) -> Zona:
    """Convierte un YAML de zona al modelo del dominio."""
    archivo = Path(archivo)
    datos = _leer(archivo)
    try:
        validar_documento(datos, origen=archivo.name)
    except ErrorEsquema as error:
        raise ErrorCarga(str(error)) from error
    if "zona" not in datos:
        raise ErrorCarga(f"{archivo.name}: no es un documento de zona")

    parametros: dict[str, Parametro] = {}
    for clave, bruto in (datos.get("parametros") or {}).items():
        parametro = _parametro(clave, bruto, datos, archivo)
        parametros[parametro.clave] = parametro
    return Zona(
        codigo=str(datos["zona"]),
        nombre=str(datos.get("nombre") or datos["zona"]),
        comuna=str(datos.get("comuna") or ""),
        parametros=MappingProxyType(parametros),
        vigencia=_vigencia(datos.get("vigencia")),
        procedencia=_procedencia(datos["procedencia"]),
    )


def cargar_zonas(raiz: Path) -> list[Zona]:
    """Todas las zonas del corpus bajo `raiz`, en orden determinista."""
    return [cargar_zona(a) for a in sorted(Path(raiz).rglob("zonas/*.yaml"))]


def _parametro(
    clave: str, bruto: dict[str, Any], datos: dict[str, Any], archivo: Path
) -> Parametro:
    limites = tuple(
        _limite(limite, datos, archivo) for limite in (bruto.get("limites") or [])
    )
    estado = EstadoParametro(str(bruto.get("estado") or "aplicable"))
    if not limites and estado is EstadoParametro.APLICABLE:
        # Sin límites no hay nada que comparar: es un dato que aún no tenemos.
        estado = EstadoParametro.DESCONOCIDO
    return Parametro(
        id=str(bruto.get("id") or clave),
        limites=limites,
        sentido=Sentido(str(bruto["sentido"])),
        estado=estado,
        cita=_cita_de_parametro(bruto, datos, archivo),
        calificador=bruto.get("calificador"),
    )


def _cita_de_parametro(bruto: dict[str, Any], datos: dict[str, Any], archivo: Path) -> Cita:
    """La cita del parámetro; si no trae una propia, la del documento.

    Un parámetro sin cita propia no es un dato huérfano: hereda la del artículo de la ordenanza que
    lo fija. Un **límite** sin cita sí es un error, y lo rechaza el esquema.
    """
    if isinstance(bruto.get("cita"), dict):
        return _cita(bruto["cita"], datos, archivo)
    norma_id = str(datos.get("norma_id") or "")
    articulo = str(datos.get("zona") or datos.get("articulo") or "")
    texto = str(datos.get("cita") or "")
    if not norma_id or not articulo or not texto:
        raise ErrorCarga(f"{archivo.name}: el parámetro '{bruto.get('id', '?')}' no tiene cita")
    return Cita(norma_id=norma_id, articulo=articulo, texto=texto)


def _limite(bruto: dict[str, Any], datos: dict[str, Any], archivo: Path) -> Limite:
    return Limite(
        tipo=TipoLimite(str(bruto.get("tipo") or "base")),
        valor=decimal_de(bruto["valor"]),
        unidad=str(bruto.get("unidad") or ""),
        cita=_cita(bruto.get("cita"), datos, archivo),
        cuando=frozenset(bruto.get("cuando") or ()),
    )


def _vigencia(bruto: Any) -> Vigencia:
    if not isinstance(bruto, dict):
        return Vigencia()
    return Vigencia(
        desde=bruto.get("desde"), hasta=bruto.get("hasta"), nota=bruto.get("nota")
    )


def _procedencia(bruto: dict[str, Any]) -> Procedencia:
    return Procedencia(
        url_fuente=str(bruto["url_fuente"]),
        hash_fuente=str(bruto["hash_fuente"]),
        consolidado_por=str(bruto["consolidado_por"]),
        extraido=str(bruto["extraido"]),
        extraido_por=bruto.get("extraido_por"),
        revisado_por=bruto.get("revisado_por"),
        estado=EstadoRevision(str(bruto.get("estado") or "borrador")),
    )


def _leer(archivo: Path) -> dict[str, Any]:
    try:
        datos = yaml.load(archivo.read_text(encoding="utf-8"), Loader=_SinDuplicados)
    except yaml.YAMLError as error:
        raise ErrorCarga(f"{archivo.name}: YAML inválido: {error}") from error
    return datos if isinstance(datos, dict) else {}


def _cita(bruta: Any, documento: dict[str, Any], archivo: Path) -> Cita:
    """Construye una `Cita` del dominio desde una cita del corpus.

    El corpus cita con `norma_id` + `articulo`; el texto se hereda de la cita del artículo cuando el
    límite o la derivación no trae uno propio. Así el veredicto siempre puede mostrar la norma.
    """
    if not isinstance(bruta, dict):
        raise ErrorCarga(f"{archivo.name}: falta la 'cita' de una regla")
    norma_id = str(bruta.get("norma_id") or documento.get("norma_id") or "")
    articulo = str(bruta.get("articulo") or documento.get("articulo") or "")
    texto = str(bruta.get("texto") or documento.get("cita") or "")
    if not norma_id or not articulo or not texto:
        raise ErrorCarga(
            f"{archivo.name}: cita incompleta (norma_id={norma_id!r}, articulo={articulo!r})"
        )
    return Cita(norma_id=norma_id, articulo=articulo, texto=texto)
