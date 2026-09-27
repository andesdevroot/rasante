"""Carga del corpus al dominio (T1.4 y T1.6).

Es el **puente** entre el corpus (dato, YAML) y el dominio (puro, sin dependencias). Puede usar
`pyyaml`; el dominio no. La dirección de la dependencia es siempre `corpus` → `dominio`, nunca al
revés.

Acá vive la lectura de `derivaciones` y `relaciones` (T1.4). La lectura de zonas llega en T1.6.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from rasante.dominio.modelos import Cita
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


def _leer(archivo: Path) -> dict[str, Any]:
    try:
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
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
