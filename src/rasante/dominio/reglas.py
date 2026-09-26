"""Intérprete de las reglas del corpus (T1.4). Módulo puro (solo stdlib).

Cierra D14: el motor calcula con lo que **el corpus dice**, no con una tabla hardcodeada en Python.

## Por qué `ast` y no `eval`

El corpus es **dato que llega de fuera**: eventualmente YAMLs contribuidos por la comunidad vía PR.
`eval` sobre eso es ejecución de código arbitrario. Acá la expresión se parsea con `ast`, se valida
contra el vocabulario cerrado de `vocabulario.py`, y se recorre a mano evaluando **solo** nombres,
literales y operadores aritméticos. Lo peor que puede provocar un corpus malicioso es un
`ErrorVocabulario`; lo peor que puede provocar un dato imposible es que el veredicto salga `P`.

## `None` no es un error

`evaluar_expresion` devuelve `None` —nunca levanta— cuando no puede calcular:

- un nombre del vocabulario que el proyecto no declara (dato faltante),
- una división por cero.

Los dos significan lo mismo para el motor: **no se puede afirmar nada, así que `P`**. Confundirlos
con un error de programa haría caer el informe por un dato que simplemente falta.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from .modelos import Cita
from .vocabulario import VOCABULARIO, ErrorVocabulario, arbol, ruta_de


@dataclass(frozen=True, slots=True)
class Derivacion:
    """Cómo se calcula un parámetro a partir de las primitivas del proyecto.

    `expresion` viene del corpus; `cita` es la norma que la establece (típicamente la definición en
    la OGUC `1.1.2`).
    """

    parametro: str
    expresion: str
    cita: Cita


@dataclass(frozen=True, slots=True)
class Relacion:
    """Restricción **entre** parámetros, que el verificador de T1.5 evalúa.

    La primera: el `cus` no puede exceder
    `cos.primer_piso + (numero_pisos - 1) * cos.pisos_superiores`, que se deduce de las propias
    definiciones de los coeficientes.
    """

    tipo: str
    objetivo: str
    expresion: str
    cita: Cita


@dataclass(frozen=True, slots=True)
class Reglas:
    """Lo que el corpus aporta al motor. Sin reglas no se puede calcular nada, y todo sale `P`."""

    derivaciones: Mapping[str, Derivacion]
    relaciones: tuple[Relacion, ...] = ()


def evaluar_expresion(expresion: str, valores: Mapping[str, Decimal | None]) -> Decimal | None:
    """Evalúa una expresión del vocabulario cerrado, o `None` si no se puede calcular.

    Levanta `ErrorVocabulario` **solo** si la expresión sale del vocabulario o de la sintaxis
    permitida: eso es un defecto del corpus, no un dato faltante.
    """
    return _evaluar(arbol(expresion).body, valores)


def _evaluar(nodo: ast.expr, valores: Mapping[str, Decimal | None]) -> Decimal | None:
    if isinstance(nodo, ast.Constant):
        # `Decimal(str(...))` y no `Decimal(float)`: `Decimal(3.5)` arrastraría el valor binario.
        return Decimal(str(nodo.value))

    if isinstance(nodo, (ast.Name, ast.Attribute)):
        ruta = ruta_de(nodo)
        if ruta is None or ruta not in VOCABULARIO:
            raise ErrorVocabulario(f"nombre fuera del vocabulario: {ruta!r}")
        return valores.get(ruta)

    if isinstance(nodo, ast.UnaryOp):
        operando = _evaluar(nodo.operand, valores)
        if operando is None:
            return None
        return -operando if isinstance(nodo.op, ast.USub) else operando

    if isinstance(nodo, ast.BinOp):
        izquierda = _evaluar(nodo.left, valores)
        derecha = _evaluar(nodo.right, valores)
        if izquierda is None or derecha is None:
            return None
        return _aplicar(nodo.op, izquierda, derecha)

    # `arbol()` ya filtró esto, pero un nodo nuevo en una versión futura del AST no debe colarse.
    raise ErrorVocabulario(f"nodo no evaluable: {type(nodo).__name__}")


def _aplicar(operador: ast.operator, izquierda: Decimal, derecha: Decimal) -> Decimal | None:
    if isinstance(operador, ast.Add):
        return izquierda + derecha
    if isinstance(operador, ast.Sub):
        return izquierda - derecha
    if isinstance(operador, ast.Mult):
        return izquierda * derecha
    if isinstance(operador, ast.Div):
        # Una división por cero es un dato imposible, no un error de programa: da `P`.
        return None if derecha == 0 else izquierda / derecha
    raise ErrorVocabulario(f"operador no evaluable: {type(operador).__name__}")
