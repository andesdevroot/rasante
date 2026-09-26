"""Vocabulario cerrado del mini-DSL del corpus (D14). Módulo puro (solo stdlib).

El corpus es **dato que llega de fuera**: eventualmente YAMLs contribuidos por la comunidad vía PR.
Sus expresiones se evalúan con `ast` sobre una lista blanca, **nunca con `eval`**. Lo peor que puede
pasar con una expresión maliciosa es un error de validación, y el árbol sintáctico queda auditable.

Este módulo es la única definición de:
- **qué puede nombrar** una expresión (`PRIMITIVAS` + `PARAMETROS`),
- **qué condiciones** puede exigir un límite condicional (`CONDICIONES`),
- **qué sintaxis** se admite (operadores y nodos del AST).

El validador (T1.3) y el intérprete (T1.4) usan los dos este vocabulario, así que no pueden
divergir.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from types import MappingProxyType

# Valores que el proyecto aporta. Los nombres son los de `Proyecto` en `modelos.py`.
PRIMITIVAS: Mapping[str, str] = MappingProxyType(
    {
        "superficie_predio_m2": "superficie del predio, en m²",
        "superficie_primer_piso_m2": "superficie edificada del primer piso, en m²",
        "superficie_edificada_m2": "superficie edificada total, en m²",
        "numero_pisos": "número de pisos sobre el terreno natural",
        "numero_viviendas": "número de unidades de vivienda",
        "altura_m": "altura de edificación, en metros",
    }
)

# Claves de parámetro que el corpus puede nombrar. Deben coincidir con las de
# `motor.DERIVACIONES`; lo verifica `tests/test_corpus_esquema.py`.
PARAMETROS: frozenset[str] = frozenset(
    {
        "cos",
        "cos.primer_piso",
        "cos.pisos_superiores",
        "cus",
        "altura_maxima",
        "densidad",
        "densidad.bruta",
        "densidad.neta",
    }
)

# Atributos del proyecto que activan un límite condicional. El caso real: la OGUC 2.6.5 permite al
# Conjunto Armónico exceder el coeficiente de constructibilidad hasta en un 50 %.
CONDICIONES: frozenset[str] = frozenset(
    {
        "conjunto_armonico",
        "agrupamiento_aislada",
        "agrupamiento_pareada",
        "agrupamiento_continua",
    }
)

# Todo lo que una expresión puede nombrar. Definición ÚNICA: la usan el intérprete (`reglas.py`) y
# el validador del corpus (`corpus/esquema.py`). Si estuviera en dos sitios, podrían divergir y una
# expresión pasaría la validación para romper en la evaluación.
VOCABULARIO: frozenset[str] = frozenset(PRIMITIVAS) | PARAMETROS

OPERADORES_BINARIOS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
OPERADORES_UNARIOS = (ast.UAdd, ast.USub)

# Nodos que solo aportan estructura: se aceptan y se validan por su padre.
_ESTRUCTURALES = (ast.Expression, ast.expr_context, ast.operator, ast.unaryop)


class ErrorVocabulario(ValueError):
    """La expresión usa algo que no está en el vocabulario cerrado."""


def nombres_de_expresion(expresion: str) -> frozenset[str]:
    """Nombres que referencia una expresión, ya resueltos a rutas con punto.

    `cos.primer_piso` se extrae como `"cos.primer_piso"`, no como `"cos"`: son claves de
    parámetro con punto, no acceso a atributos.

    Levanta `ErrorVocabulario` si la sintaxis sale de la lista blanca.
    """
    return frozenset(_recolectar(arbol(expresion).body))


def arbol(expresion: str) -> ast.Expression:
    try:
        arbol = ast.parse(expresion, mode="eval")
    except SyntaxError as error:
        raise ErrorVocabulario(f"sintaxis inválida en {expresion!r}: {error.msg}") from error
    _revisar(arbol)
    return arbol


def _revisar(nodo: ast.AST) -> None:
    """Lista blanca de nodos. No valida *qué* nombres se usan: eso lo hace el validador."""
    for hijo in ast.walk(nodo):
        if isinstance(hijo, _ESTRUCTURALES):
            continue
        if isinstance(hijo, ast.Constant):
            # `bool` es subclase de `int`: se descarta explícitamente. Tampoco hay literales de
            # texto, porque las expresiones son aritméticas.
            if isinstance(hijo.value, bool) or not isinstance(hijo.value, (int, float)):
                raise ErrorVocabulario(f"literal no permitido: {hijo.value!r}")
            continue
        if isinstance(hijo, (ast.Name, ast.Attribute)):
            continue  # la ruta se comprueba contra el vocabulario en `validar_documento`
        if isinstance(hijo, ast.BinOp):
            if not isinstance(hijo.op, OPERADORES_BINARIOS):
                raise ErrorVocabulario(f"operador no permitido: {type(hijo.op).__name__}")
            continue
        if isinstance(hijo, ast.UnaryOp):
            if not isinstance(hijo.op, OPERADORES_UNARIOS):
                raise ErrorVocabulario(f"operador unario no permitido: {type(hijo.op).__name__}")
            continue
        raise ErrorVocabulario(f"construcción no permitida: {type(hijo).__name__}")


def _recolectar(nodo: ast.expr) -> set[str]:
    """Solo desciende por operadores, así que no parte `cos.primer_piso` en `cos`."""
    if isinstance(nodo, ast.BinOp):
        return _recolectar(nodo.left) | _recolectar(nodo.right)
    if isinstance(nodo, ast.UnaryOp):
        return _recolectar(nodo.operand)
    if isinstance(nodo, (ast.Name, ast.Attribute)):
        ruta = ruta_de(nodo)
        return {ruta} if ruta else set()
    return set()


def ruta_de(nodo: ast.expr) -> str | None:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        base = ruta_de(nodo.value)
        return f"{base}.{nodo.attr}" if base else None
    return None
