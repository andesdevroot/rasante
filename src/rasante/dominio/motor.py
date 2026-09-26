"""Motor de evaluación. Capa L1, **módulo puro** (D2: solo stdlib).

Compara un `Proyecto` contra los parámetros que una `Zona` declara y devuelve un `Veredicto` por
parámetro, cada uno con su cita.

## El invariante que sostiene el producto

> **Un dato que no tenemos da `P` (pendiente), jamás `C` (cumple).**

Un `(C)` afirma que el proyecto cumple la norma. Si la norma es desconocida, si el dato del
proyecto falta, o si no sabemos cómo comparar un parámetro, afirmarlo sería un informe falso
firmado por un profesional. Por eso los tres caminos hacia `P` están separados y testeados.

## Una sola tabla

`DERIVACIONES` es la **única** fuente de verdad sobre qué parámetros conocemos y cómo se obtiene su
valor del proyecto. No hay una lista de claves y otra de sentidos que puedan divergir: estar en la
tabla significa "sé calcularlo y sé que es un máximo". Un parámetro que no esté ahí da `P`.

| Parámetro | Cómo se obtiene el valor del proyecto |
|---|---|
| `cos`, `cos.primer_piso` | superficie del primer piso / superficie del predio |
| `cus` | superficie edificada total / superficie del predio |
| `densidad`, `densidad.bruta` | viviendas / hectáreas del predio |
| `altura_maxima` | altura declarada, comparación directa |

Es lo que obliga a que `evaluar` reciba el `Proyecto` completo y no un número suelto (§A3).

**Nota (D13, pendiente).** La OGUC aporta la regla y el PRC el valor, así que un veredicto de
densidad debería citar **las dos**. Hoy `Veredicto.cita` es singular y lleva la norma que fija el
valor. Añadir la cita de la regla es aditivo y se hará cuando el informe la necesite (iteración 3).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from types import MappingProxyType

from .modelos import (
    CodigoVeredicto,
    EstadoParametro,
    Parametro,
    Proyecto,
    Veredicto,
    Zona,
)

M2_POR_HECTAREA = Decimal("10000")


def _cos(proyecto: Proyecto) -> Decimal | None:
    return _razon(proyecto.superficie_primer_piso_m2, proyecto.superficie_predio_m2)


def _cus(proyecto: Proyecto) -> Decimal | None:
    return _razon(proyecto.superficie_edificada_m2, proyecto.superficie_predio_m2)


def _altura(proyecto: Proyecto) -> Decimal | None:
    return proyecto.altura_m


def _densidad_bruta(proyecto: Proyecto) -> Decimal | None:
    return _razon(
        Decimal(proyecto.numero_viviendas), proyecto.superficie_predio_m2 / M2_POR_HECTAREA
    )


def _sin_dato(_proyecto: Proyecto) -> Decimal | None:
    """Parámetro que sabemos comparar pero cuyo dato el proyecto todavía no declara.

    Registrarlo explícitamente, en vez de dejarlo caer por un `else`, hace visible la carencia y
    garantiza que dé `P` en vez de `C`.
    """
    return None


DERIVACIONES: Mapping[str, Callable[[Proyecto], Decimal | None]] = MappingProxyType(
    {
        "cos": _cos,
        "cos.primer_piso": _cos,
        "cos.pisos_superiores": _sin_dato,  # falta la superficie de un piso superior
        "cus": _cus,
        "altura_maxima": _altura,
        "densidad": _densidad_bruta,
        "densidad.bruta": _densidad_bruta,
        "densidad.neta": _sin_dato,  # falta el descuento por utilidad pública
    }
)


def evaluar(proyecto: Proyecto, zona: Zona) -> list[Veredicto]:
    """Evalúa cada parámetro que la zona declara, en orden determinista por clave."""
    parametros = sorted(zona.parametros.values(), key=lambda p: p.clave)
    return [_evaluar_uno(proyecto, parametro) for parametro in parametros]


def _evaluar_uno(proyecto: Proyecto, parametro: Parametro) -> Veredicto:
    derivar = DERIVACIONES.get(parametro.clave)
    valor_proyecto = derivar(proyecto) if derivar is not None else None
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
    if valor_proyecto <= parametro.valor:
        return CodigoVeredicto.CUMPLE
    return CodigoVeredicto.NO_CUMPLE


def _razon(numerador: Decimal | None, denominador: Decimal) -> Decimal | None:
    """Cociente, o `None` si falta el numerador o el denominador es cero.

    No se redondea a propósito: redondear antes de comparar puede convertir un `(NC)` en un `(C)`
    justo en el límite. El redondeo es cosa del informe, no del veredicto.
    """
    if numerador is None or denominador == 0:
        return None
    return numerador / denominador
