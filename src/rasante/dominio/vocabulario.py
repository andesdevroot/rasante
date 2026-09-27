"""Vocabulario cerrado del mini-DSL del corpus (D14). Módulo puro (solo stdlib).

El corpus es **dato que llega de fuera**: eventualmente YAMLs contribuidos por la comunidad vía PR.
Sus expresiones se evalúan con `ast` sobre una lista blanca, **nunca con `eval`**. Lo peor que puede
pasar con una expresión maliciosa es un error de validación, y el árbol sintáctico queda auditable.

Este módulo es la única definición de:
- **qué puede nombrar** una expresión (`PRIMITIVAS` + `PARAMETROS`),
- **qué sintaxis** se admite (operadores y nodos del AST).

El validador (T1.3) y el intérprete (T1.4) usan los dos este vocabulario, así que no pueden
divergir.

**Lo que ya NO está acá:** la lista de condiciones que activan un límite condicional. `CONDICIONES`
hardcodeaba `conjunto_armonico` y `agrupamiento_*` en Python para `Proyecto.clasificaciones`, que
nadie consumía. Los hechos que activan un límite los declara el corpus (D14/D16) y los resuelve el
puente de clasificación (T1.10); una lista paralela en Python era un segundo origen de verdad que
además no podía expresar "no se sabe".
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from functools import lru_cache
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
        "acoge_conjunto_armonico": "el proyecto se acoge a la calidad de Conjunto Armónico",
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
        # Los que exige la primera zona real transcrita (Ñuñoa Z-2, T1.14). `pisos_maximos` existe
        # porque la ordenanza escribe la altura como "10 pisos **y** 28,00 m": son dos cotas
        # superiores simultáneas en unidades distintas, y el motor elige **un** límite vigente.
        # El "y" de la norma no es un operador: son dos parámetros.
        "pisos_maximos",
        "rasante",
        "antejarin",
        "distanciamiento",
        "cuerpos_salientes",
        "superficie_predial_minima",
    }
)

# Todo lo que una expresión puede nombrar. Definición ÚNICA: la usan el intérprete (`reglas.py`) y
# el validador del corpus (`corpus/esquema.py`). Si estuviera en dos sitios, podrían divergir y una
# expresión pasaría la validación para romper en la evaluación.
#
# **`NORMADOS` ya no existe.** Era un conjunto aparte para `superficie_predial_minima`, "un valor
# que fija el PRC y que un hecho puede citar, pero que no es una primitiva del proyecto". Al
# transcribir la primera zona real quedó claro que eso **es** un parámetro de la zona: el predio
# debe cumplir la superficie predial mínima, y el valor lo pone el PRC. Un conjunto de un solo
# elemento que además no aportaba nada al intérprete.
VOCABULARIO: frozenset[str] = frozenset(PRIMITIVAS) | PARAMETROS

OPERADORES_BINARIOS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
OPERADORES_UNARIOS = (ast.UAdd, ast.USub)

TAMANO_CACHE = 1024
"""Cuántos árboles sintácticos se memorizan. Un corpus comunal completo cabe de sobra: son cientos
de expresiones, no miles, y una desalojada solo se vuelve a parsear."""
# Las comparaciones son lo que permite que un `hecho` sea un predicado. Sin esto no hay `cuando`.
OPERADORES_COMPARACION = (
    ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq,
)

# Nodos que solo aportan estructura: se aceptan y se validan por su padre.
_ESTRUCTURALES = (
    ast.Expression,
    ast.expr_context,
    ast.operator,
    ast.unaryop,
    ast.cmpop,
    ast.boolop,
)


class ErrorVocabulario(ValueError):
    """La expresión usa algo que no está en el vocabulario cerrado."""


def nombres_de_expresion(expresion: str) -> frozenset[str]:
    """Nombres que referencia una expresión, ya resueltos a rutas con punto.

    `cos.primer_piso` se extrae como `"cos.primer_piso"`, no como `"cos"`: son claves de
    parámetro con punto, no acceso a atributos.

    Levanta `ErrorVocabulario` si la sintaxis sale de la lista blanca.
    """
    return frozenset(_recolectar(arbol(expresion).body))


@lru_cache(maxsize=TAMANO_CACHE)
def arbol(expresion: str) -> ast.Expression:
    """El árbol sintáctico de una expresión del corpus, **memorizado**.

    Se paga dos veces por cada expresión: `ast.parse` (≈37 % del costo) y el recorrido de la lista
    blanca `_revisar` (≈63 %). Las dos son función pura del texto, y los textos del corpus son
    inmutables, así que se calculan una vez por proceso en vez de una vez por evaluación.

    Medido sobre Z-2 (12 parámetros): `evaluar()` pasó de 209 µs a 79 µs. Para evaluar en lote
    —muchos proyectos contra el mismo corpus— es la diferencia entre pagar el parseo N veces o una.

    ## Por qué `lru_cache` y no un `dict` del módulo

    La memoria está acotada. Un `dict` que crece con cada expresión vista es una fuga en un proceso
    de vida larga; `TAMANO_CACHE` acota el costo y una expresión desalojada se vuelve a parsear, que
    es lo correcto.

    ## Lo que el llamador NO puede hacer

    El árbol devuelto es **compartido**: mutarlo envenenaría la caché para todas las evaluaciones
    siguientes. Acá nadie lo hace —`_evaluar` y `nombres_de_expresion` solo lo recorren—, y por eso
    se documenta: es una invariante de uso, no algo que el tipo pueda impedir.
    """
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
        if isinstance(hijo, ast.BoolOp):
            if not isinstance(hijo.op, (ast.And, ast.Or)):
                raise ErrorVocabulario(f"operador lógico no permitido: {type(hijo.op).__name__}")
            continue
        if isinstance(hijo, ast.Compare):
            for op in hijo.ops:
                if not isinstance(op, OPERADORES_COMPARACION):
                    raise ErrorVocabulario(f"comparación no permitida: {type(op).__name__}")
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
    if isinstance(nodo, ast.Compare):
        return _recolectar(nodo.left).union(*(_recolectar(c) for c in nodo.comparators))
    if isinstance(nodo, ast.BoolOp):
        encontrados: set[str] = set()
        for valor in nodo.values:
            encontrados |= _recolectar(valor)
        return encontrados
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
