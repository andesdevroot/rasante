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
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType

from .modelos import Cita, ErrorDominio
from .vocabulario import VOCABULARIO, ErrorVocabulario, arbol, nombres_de_expresion, ruta_de


class ErrorHechoDuplicado(ErrorDominio):
    """Un hecho tiene dos fuentes: el corpus y el puente de clasificación.

    Es un error y no una precedencia a propósito. Un hecho decide **cuál límite rige**, así que
    dejar que dos fuentes lo definan es dejar el veredicto a merced del orden en que se aplicaron.
    """


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
class Excepcion:
    """Una norma de aplicación general que **amplía un valor que fija el plan regulador** (T1.10b).

    OGUC `2.6.5`: *"Los proyectos que cumplan con la condición de dimensión a que se refieren las
    letras a) o b) del número 1. del artículo 2.6.4., podrán exceder hasta en un 50% el coeficiente
    de constructibilidad establecido por el Plan Regulador respectivo."*

    El valor **no es un número**: es un factor sobre lo que fije cada PRC. El `cus` de Ñuñoa no es
    el de Las Condes, y la OGUC aplica a los dos. Un `Limite` con `valor` absoluto no puede
    expresarlo, y expandirlo por zona duplicaría la regla nacional en cada ordenanza hasta perder
    su trazabilidad.

    Que sea un `factor` y no un `valor` es lo que hace que esto **no pueda vivir en la zona**: la
    zona aporta el valor, la OGUC aporta la proporción.

    La disyunción *"letras a) o b)"* se modela con **una entrada por hecho**. Cada una concede su
    factor por separado y, entre las que apliquen, manda la más restrictiva: para un máximo, esa es
    la dirección segura, y evita inventar un operador lógico nuevo.

    `hechos` es una **conjunción**: todos deben cumplirse. Ahí está la diferencia entre "el terreno
    cumple la condición de dimensión" y "el proyecto se acoge al Conjunto Armónico **y** el terreno
    cumple la condición". Sin lo primero, cualquier predio de más de 5.000 m² obtendría el +50 %.
    """

    parametro: str
    hechos: frozenset[str]
    factor: Decimal
    cita: Cita

    def __post_init__(self) -> None:
        if not isinstance(self.factor, Decimal):
            tipo = type(self.factor).__name__
            raise ErrorDominio(f"el factor de una Excepcion debe ser Decimal, no {tipo}")
        if self.factor <= 0:
            raise ErrorDominio("el factor de una Excepcion debe ser mayor que cero")
        if not isinstance(self.cita, Cita):
            raise ErrorDominio("una Excepcion necesita una Cita")
        if not self.parametro.strip():
            raise ErrorDominio("una Excepcion necesita 'parametro'")
        if not self.hechos:
            raise ErrorDominio("una Excepcion necesita 'hechos': sin ellos aplicaría siempre")
        if any(not h.strip() for h in self.hechos):
            raise ErrorDominio("una Excepcion no admite nombres de hecho vacíos")


@dataclass(frozen=True, slots=True)
class Hecho:
    """Un predicado nombrado que el corpus define como expresión (D16).

    Es lo que permite que un límite condicional diga *"aplico si el proyecto cumple la condición
    1.a) del 2.6.4"* sin que nadie tenga que decidirlo con un modelo: la condición es una
    comparación escrita en la norma.
    """

    nombre: str
    expresion: str
    cita: Cita


@dataclass(frozen=True, slots=True)
class Clasificacion:
    """Qué hechos se cumplen para un proyecto.

    Tres estados por hecho, no dos: `True`, `False` y **`None` = no se sabe**. El tercero es el que
    impide que un dato faltante se convierta en un límite más permisivo.
    """

    hechos: Mapping[str, bool | None]

    def aplica(self, cuando: frozenset[str]) -> bool | None:
        """`True` si se cumplen todos; `False` si alguno no; `None` si alguno es indeterminado.

        **Un `False` decide antes que un `None`**, porque `X and False = False`: si una condición
        ya falló, que otra sea desconocida no cambia nada. Evaluar en el otro orden convertía en
        "pendiente" a todo límite con una condición descartada — y con la excepción de `2.6.5`,
        que combina "el proyecto se acoge" con "cumple la condición de dimensión", eso dejaba en `P`
        hasta el `cus` de los proyectos que no se acogen a nada.
        """
        estados = [self.hechos.get(nombre) for nombre in sorted(cuando)]
        if any(estado is False for estado in estados):
            return False
        if any(estado is None for estado in estados):
            return None
        return True

    def indeterminados(self, cuando: frozenset[str]) -> tuple[str, ...]:
        """Los hechos que no se pudieron determinar **y que todavía importan**.

        Si alguno ya es `False`, la condición está descartada y no falta ningún dato (`X and False =
        False`). Devolver nombres ahí produciría un hallazgo pidiéndole al revisor un dato que ya no
        cambia el veredicto — y con la excepción de `2.6.5`, que exige acogerse *y* cumplir una
        condición de dimensión, eso llenaba de hallazgos a todos los proyectos no acogidos.
        """
        estados = {nombre: self.hechos.get(nombre) for nombre in cuando}
        if any(estado is False for estado in estados.values()):
            return ()
        return tuple(sorted(n for n, estado in estados.items() if estado is None))


@dataclass(frozen=True, slots=True)
class Reglas:
    """Lo que el corpus aporta al motor. Sin reglas no se puede calcular nada, y todo sale `P`."""

    derivaciones: Mapping[str, Derivacion]
    relaciones: tuple[Relacion, ...] = ()
    hechos: Mapping[str, Hecho] = field(
        default_factory=lambda: MappingProxyType({})
    )
    excepciones: tuple[Excepcion, ...] = ()
    """Normas de aplicación general que amplían un valor del plan regulador (`2.6.5`).

    Van acá y no en la `Zona` a propósito: la zona aporta el **valor**, la OGUC aporta la
    **proporción**. Ponerlas en la zona duplicaría la regla nacional en cada ordenanza.
    """


def declarar_nombres(
    expresion: str, valores: Mapping[str, Decimal | None]
) -> dict[str, Decimal | None]:
    """Completa con `None` los nombres que la expresión usa y el llamador no aportó.

    Un nombre que el corpus menciona y el proyecto no declara es un **dato faltante**, no un error:
    debe dar `None` (indeterminado). Sin esto, la evaluación levantaría `ErrorVocabulario` por algo
    que simplemente no sabemos, y el motor no podría distinguir "no lo sé" de "está mal escrito".
    """
    completos = dict(valores)
    for nombre in nombres_de_expresion(expresion):
        completos.setdefault(nombre, None)
    return completos


def evaluar_hecho(expresion: str, valores: Mapping[str, Decimal | None]) -> bool | None:
    """Evalúa un predicado. `None` si no se puede determinar.

    Las comparaciones se representan internamente como `Decimal(1)`/`Decimal(0)` para no tener que
    devolver dos tipos desde el mismo evaluador; acá se traducen a `bool`.
    """
    resultado = evaluar_expresion(expresion, valores)
    return None if resultado is None else bool(resultado)


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
        # Un nombre vale si está en el vocabulario o si el llamador lo aportó: un hecho puede
        # referirse a un valor **normado** (la superficie predial mínima del PRC), que no es una
        # primitiva del proyecto. Los nombres los aporta el llamador, nunca la expresión.
        if ruta is None or (ruta not in VOCABULARIO and ruta not in valores):
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

    if isinstance(nodo, ast.Compare):
        return _comparar_cadena(nodo, valores)

    if isinstance(nodo, ast.BoolOp):
        return _aplicar_logico(nodo, valores)

    # `arbol()` ya filtró esto, pero un nodo nuevo en una versión futura del AST no debe colarse.
    raise ErrorVocabulario(f"nodo no evaluable: {type(nodo).__name__}")


def _aplicar_logico(nodo: ast.BoolOp, valores: Mapping[str, Decimal | None]) -> Decimal | None:
    """`and`/`or` sobre predicados. El cortocircuito de Python se respeta."""
    resultados = [_evaluar(valor, valores) for valor in nodo.values]
    if isinstance(nodo.op, ast.And):
        if any(r is not None and not r for r in resultados):
            return Decimal(0)
        return None if any(r is None for r in resultados) else Decimal(1)
    if any(r is not None and r for r in resultados):
        return Decimal(1)
    return None if any(r is None for r in resultados) else Decimal(0)


def _comparar_cadena(nodo: ast.Compare, valores: Mapping[str, Decimal | None]) -> Decimal | None:
    """`Decimal(1)` si la comparación se cumple, `Decimal(0)` si no, `None` si falta un dato."""
    izquierda = _evaluar(nodo.left, valores)
    if izquierda is None:
        return None
    for operador, comparador in zip(nodo.ops, nodo.comparators, strict=True):
        derecha = _evaluar(comparador, valores)
        if derecha is None:
            return None
        if not _comparar(operador, izquierda, derecha):
            return Decimal(0)
        izquierda = derecha
    return Decimal(1)


def _comparar(operador: ast.cmpop, izquierda: Decimal, derecha: Decimal) -> bool:
    if isinstance(operador, ast.Gt):
        return izquierda > derecha
    if isinstance(operador, ast.GtE):
        return izquierda >= derecha
    if isinstance(operador, ast.Lt):
        return izquierda < derecha
    if isinstance(operador, ast.LtE):
        return izquierda <= derecha
    if isinstance(operador, ast.Eq):
        return izquierda == derecha
    if isinstance(operador, ast.NotEq):
        return izquierda != derecha
    raise ErrorVocabulario(f"comparación no evaluable: {type(operador).__name__}")


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
