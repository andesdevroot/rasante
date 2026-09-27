"""Validador del corpus ejecutable (T1.3).

Comprueba que un documento del corpus tiene la forma que el motor va a poder interpretar (T1.4), y
—lo que importa— que sus expresiones **solo nombran cosas del vocabulario cerrado**.

Dos formas de documento, distinguidas por su contenido:

- **norma** (nacional): trae `articulo`. Puede tener `regla`, `relaciones` y `definiciones`.
- **zona** (municipal): trae `zona` y `parametros`. Cada parámetro lleva `limites`.

No es un validador de esquema genérico a propósito: valida **lo que el motor necesita**, y rechaza
con el motivo concreto en vez de con un error de librería.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from rasante.dominio.modelos import clave_compuesta
from rasante.dominio.vocabulario import (
    PARAMETROS,
    VOCABULARIO,
    ErrorVocabulario,
    nombres_de_expresion,
)

CAMPOS_PROCEDENCIA = ("url_fuente", "hash_fuente", "consolidado_por", "extraido")


class ErrorEsquema(ValueError):
    """Un documento del corpus no cumple el esquema."""


def validar_corpus(raiz: Path) -> list[Path]:
    """Valida todos los YAML bajo `raiz`. Devuelve los validados, en orden.

    Además de cada archivo por separado, comprueba **entre archivos** que todo `cuando` tenga su
    hecho definido en algún artículo. Sin eso, ese límite nunca aplicaría y nadie se enteraría.
    """
    archivos = sorted(Path(raiz).rglob("*.yaml"))
    definidos: set[str] = set()
    exigidos: dict[str, str] = {}
    for archivo in archivos:
        validar_archivo(archivo)
        datos = _leer(archivo)
        definidos.update(datos.get("hechos") or {})
        for parametro in (datos.get("parametros") or {}).values():
            for limite in parametro.get("limites", []):
                for nombre in limite.get("cuando") or []:
                    exigidos.setdefault(nombre, archivo.name)
    huerfanos = {n: a for n, a in exigidos.items() if n not in definidos}
    if huerfanos:
        raise ErrorEsquema(f"'cuando' sin hecho definido en ningún artículo: {huerfanos}")
    return archivos


def _leer(archivo: Path) -> dict[str, Any]:
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    return datos if isinstance(datos, dict) else {}


def validar_archivo(ruta: Path) -> None:
    ruta = Path(ruta)
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ErrorEsquema(f"{ruta.name}: YAML inválido: {error}") from error
    validar_documento(datos, origen=ruta.name)


def validar_documento(datos: Any, *, origen: str = "") -> None:
    prefijo = f"{origen}: " if origen else ""
    if not isinstance(datos, dict):
        raise ErrorEsquema(f"{prefijo}el documento no es un mapping")

    _validar_procedencia(datos, prefijo)
    _validar_texto_obligatorio(datos, "norma_id", prefijo)
    _validar_texto_obligatorio(datos, "cita", prefijo)

    if "parametros" in datos:
        _validar_parametros(datos, prefijo)
    _validar_derivaciones(datos, prefijo)
    _validar_hechos(datos, prefijo)

    declarados = set(datos.get("parametros", {}))
    permitidos = set(VOCABULARIO) | declarados
    for ruta_expresion, expresion in _expresiones(datos):
        _validar_expresion(expresion, permitidos, f"{prefijo}{ruta_expresion}")

    # Un `objetivo` es el parámetro que la relación acota, no un valor del proyecto: `numero_pisos`
    # es una primitiva, no algo que una relación pueda tener por objetivo.
    objetivos = set(PARAMETROS) | declarados
    for indice, relacion in enumerate(_lista(datos.get("relaciones"), "relaciones", prefijo)):
        _validar_relacion(relacion, objetivos, f"{prefijo}relaciones[{indice}]")


def _validar_procedencia(datos: dict[str, Any], prefijo: str) -> None:
    procedencia = datos.get("procedencia")
    if not isinstance(procedencia, dict):
        raise ErrorEsquema(f"{prefijo}falta 'procedencia'")
    for campo in CAMPOS_PROCEDENCIA:
        if not str(procedencia.get(campo, "")).strip():
            raise ErrorEsquema(f"{prefijo}procedencia sin '{campo}'")


def _validar_texto_obligatorio(datos: dict[str, Any], campo: str, prefijo: str) -> None:
    if not str(datos.get(campo, "")).strip():
        raise ErrorEsquema(f"{prefijo}falta '{campo}'")


def _validar_parametros(datos: dict[str, Any], prefijo: str) -> None:
    parametros = datos.get("parametros")
    if not isinstance(parametros, dict):
        raise ErrorEsquema(f"{prefijo}'parametros' no es un mapping")
    for clave, parametro in parametros.items():
        if not isinstance(parametro, dict):
            raise ErrorEsquema(f"{prefijo}'{clave}' no es un mapping")
        esperada = clave_compuesta(str(parametro.get("id", "")), parametro.get("calificador"))
        if clave != esperada:
            raise ErrorEsquema(
                f"{prefijo}la clave '{clave}' no coincide con la de su parametro ('{esperada}')"
            )
        limites = _lista(parametro.get("limites"), "limites", f"{prefijo}'{clave}': ")
        if not limites:
            raise ErrorEsquema(f"{prefijo}'{clave}': 'limites' no puede estar vacío")
        for indice, limite in enumerate(limites):
            _validar_limite(limite, f"{prefijo}'{clave}'.limites[{indice}]")
        _validar_tipos_de_limite(limites, clave, prefijo)


def _validar_limite(limite: Any, donde: str) -> None:
    if not isinstance(limite, dict):
        raise ErrorEsquema(f"{donde}: no es un mapping")
    valor = limite.get("valor")
    if valor is None:
        raise ErrorEsquema(f"{donde}: falta 'valor'")
    if not isinstance(valor, str):
        # Debe ser texto: `0.6` sin comillas es float y reintroduce el error binario (D6).
        raise ErrorEsquema(
            f"{donde}: 'valor' debe ser texto entre comillas, no {type(valor).__name__}"
        )
    if not valor.strip():
        raise ErrorEsquema(f"{donde}: 'valor' está vacío")
    if not isinstance(limite.get("cita"), dict):
        raise ErrorEsquema(f"{donde}: falta 'cita'")
    cuando = limite.get("cuando")
    if cuando is not None:
        if not isinstance(cuando, list) or not cuando:
            raise ErrorEsquema(f"{donde}: 'cuando' debe ser una lista no vacía")
        # `cuando` nombra **hechos** (D16). Que existan se comprueba entre archivos, en
        # `validar_corpus`: un artículo nacional no puede saber qué hechos define otro.
        if any(not isinstance(c, str) or not c.strip() for c in cuando):
            raise ErrorEsquema(f"{donde}: 'cuando' debe ser una lista de nombres")


def _validar_derivaciones(datos: dict[str, Any], prefijo: str) -> None:
    """`derivaciones` es cómo el corpus dice calcular cada parámetro (el corazón de D14).

    Un parámetro **ausente** de `derivaciones` no es un error: significa que sabemos compararlo
    pero el proyecto todavía no declara lo necesario, y da `P`.
    """
    derivaciones = datos.get("derivaciones")
    if derivaciones is None:
        return
    if not isinstance(derivaciones, dict):
        raise ErrorEsquema(f"{prefijo}'derivaciones' no es un mapping")
    for clave, derivacion in derivaciones.items():
        if clave not in PARAMETROS:
            raise ErrorEsquema(f"{prefijo}derivaciones: '{clave}' no es un parámetro conocido")
        if not isinstance(derivacion, dict):
            raise ErrorEsquema(f"{prefijo}derivaciones.{clave}: no es un mapping")
        if not isinstance(derivacion.get("cita"), dict):
            raise ErrorEsquema(f"{prefijo}derivaciones.{clave}: falta 'cita'")


def _validar_tipos_de_limite(limites: list[Any], clave: str, prefijo: str) -> None:
    """Un `base` no lleva condiciones y una `excepcion` las exige, o la semántica se rompe."""
    for indice, limite in enumerate(limites):
        tipo = limite.get("tipo")
        cuando = limite.get("cuando") or []
        if tipo == "base" and cuando:
            raise ErrorEsquema(f"{prefijo}'{clave}'.limites[{indice}]: un 'base' no lleva 'cuando'")
        if tipo == "excepcion" and not cuando:
            raise ErrorEsquema(
                f"{prefijo}'{clave}'.limites[{indice}]: una 'excepcion' sin 'cuando' aplicaría "
                "siempre y anularía al base"
            )


def _validar_hechos(datos: dict[str, Any], prefijo: str) -> None:
    """Un hecho es un predicado nombrado. Su `expresion` la valida `_expresiones`."""
    hechos = datos.get("hechos")
    if hechos is None:
        return
    if not isinstance(hechos, dict):
        raise ErrorEsquema(f"{prefijo}'hechos' no es un mapping")
    for nombre, hecho in hechos.items():
        if not isinstance(hecho, dict):
            raise ErrorEsquema(f"{prefijo}hechos.{nombre}: no es un mapping")
        if not isinstance(hecho.get("cita"), dict):
            raise ErrorEsquema(f"{prefijo}hechos.{nombre}: falta 'cita'")


def _validar_relacion(relacion: Any, objetivos_permitidos: set[str], donde: str) -> None:
    if not isinstance(relacion, dict):
        raise ErrorEsquema(f"{donde}: no es un mapping")
    if not str(relacion.get("tipo", "")).strip():
        raise ErrorEsquema(f"{donde}: falta 'tipo'")
    objetivo = relacion.get("objetivo")
    if objetivo not in objetivos_permitidos:
        raise ErrorEsquema(f"{donde}: 'objetivo' no es un parámetro conocido: {objetivo!r}")
    if not isinstance(relacion.get("cita"), dict):
        raise ErrorEsquema(f"{donde}: falta 'cita'")


def _validar_expresion(expresion: Any, permitidos: set[str], donde: str) -> None:
    if not isinstance(expresion, str) or not expresion.strip():
        raise ErrorEsquema(f"{donde}: 'expresion' debe ser texto no vacío")
    try:
        nombres = nombres_de_expresion(expresion)
    except ErrorVocabulario as error:
        raise ErrorEsquema(f"{donde}: {error}") from error
    fuera = sorted(nombres - permitidos)
    if fuera:
        raise ErrorEsquema(f"{donde}: nombres fuera del vocabulario: {fuera}")


def _expresiones(nodo: Any, ruta: str = "") -> Iterator[tuple[str, Any]]:
    """Toda clave `expresion` del documento, con su ruta, esté donde esté."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave == "expresion":
                yield ruta or "expresion", valor
            else:
                yield from _expresiones(valor, f"{ruta}.{clave}" if ruta else str(clave))
    elif isinstance(nodo, list):
        for indice, valor in enumerate(nodo):
            yield from _expresiones(valor, f"{ruta}[{indice}]")


def _lista(valor: Any, campo: str, prefijo: str) -> list[Any]:
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise ErrorEsquema(f"{prefijo}'{campo}' debe ser una lista")
    return valor
