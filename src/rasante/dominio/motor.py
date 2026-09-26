"""Motor de evaluación. Capa L1, **módulo puro** (D2: solo stdlib).

Compara un `Proyecto` contra los parámetros que una `Zona` declara y devuelve un `Veredicto` por
parámetro, cada uno con su cita.

## El invariante que sostiene el producto

> **Un dato que no tenemos da `P` (pendiente), jamás `C` (cumple).**

Un `(C)` afirma que el proyecto cumple la norma. Si la norma es desconocida, si el dato del
proyecto falta, o si no sabemos cómo comparar un parámetro, afirmarlo sería un informe falso firmado
por un profesional. Por eso los caminos hacia `P` están separados y testeados.

## El corpus manda (D14)

**Cómo se calcula** cada parámetro viene del corpus (`derivaciones`), no de una tabla en
Python. Este módulo solo aporta el proyecto, y `reglas.py` evalúa lo que el corpus dice.

**Qué queda hardcodeado, y por qué.** `MAXIMOS` dice qué parámetros son cotas superiores. El esquema
del corpus todavía no expresa el sentido de la comparación, así que vive acá —en **un** sitio
explícito— en vez de disperso. Un parámetro con derivación pero sin sentido declarado da `P`, y un
test lo obliga a fallar en vez de degradarse en silencio.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from .modelos import (
    CodigoVeredicto,
    EstadoParametro,
    Parametro,
    Proyecto,
    Veredicto,
    Zona,
)
from .reglas import Reglas, evaluar_expresion

# Parámetros cuyo sentido conocemos: son máximos, no deben excederse.
#
# Un parámetro que NO esté acá da `P`, no se asume nada sobre él. Suponer que algo desconocido es un
# máximo y compararlo produciría un `(C)` o un `(NC)` sin fundamento.
MAXIMOS: frozenset[str] = frozenset(
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


def evaluar(proyecto: Proyecto, zona: Zona, reglas: Reglas) -> list[Veredicto]:
    """Evalúa cada parámetro que la zona declara, en orden determinista por clave."""
    valores = valores_del_proyecto(proyecto)
    parametros = sorted(zona.parametros.values(), key=lambda p: p.clave)
    return [_evaluar_uno(parametro, valores, reglas) for parametro in parametros]


def valores_del_proyecto(proyecto: Proyecto) -> dict[str, Decimal | None]:
    """Las primitivas del proyecto, con los nombres del vocabulario del corpus.

    Un campo que el proyecto no declara se incluye como `None`, no se omite: así el intérprete
    distingue "no lo declaró" de "no existe ese nombre".
    """
    return {
        "superficie_predio_m2": proyecto.superficie_predio_m2,
        "superficie_primer_piso_m2": proyecto.superficie_primer_piso_m2,
        "superficie_edificada_m2": proyecto.superficie_edificada_m2,
        "numero_pisos": _decimal(proyecto.numero_pisos),
        "numero_viviendas": Decimal(proyecto.numero_viviendas),
        "altura_m": proyecto.altura_m,
    }


def _decimal(entero: int | None) -> Decimal | None:
    return Decimal(entero) if entero is not None else None


def _evaluar_uno(
    parametro: Parametro, valores: Mapping[str, Decimal | None], reglas: Reglas
) -> Veredicto:
    derivacion = reglas.derivaciones.get(parametro.clave)
    valor_proyecto = (
        evaluar_expresion(derivacion.expresion, valores) if derivacion is not None else None
    )
    return Veredicto(
        parametro_id=parametro.id,
        codigo=_decidir(parametro, valor_proyecto),
        cita=parametro.cita,
        valor_norma=parametro.valor,
        valor_proyecto=valor_proyecto,
        calificador=parametro.calificador,
    )


def _decidir(parametro: Parametro, valor_proyecto: Decimal | None) -> CodigoVeredicto:
    """El orden importa: todo lo que no se puede afirmar sale antes de cualquier comparación."""
    if parametro.estado is EstadoParametro.NO_APLICA:
        return CodigoVeredicto.NO_PROCEDE
    if parametro.estado is EstadoParametro.DESCONOCIDO or parametro.valor is None:
        return CodigoVeredicto.PENDIENTE  # no sabemos cuál es el límite
    if valor_proyecto is None:
        return CodigoVeredicto.PENDIENTE  # no sabemos cuánto mide el proyecto
    if parametro.clave not in MAXIMOS:
        return CodigoVeredicto.PENDIENTE  # no sabemos cómo se compara
    if valor_proyecto <= parametro.valor:
        return CodigoVeredicto.CUMPLE
    return CodigoVeredicto.NO_CUMPLE
