"""El portero: decide si una respuesta está lista o va a revisión humana.

**Nunca se redondea una duda hacia el lado permisivo.** Una elección con confianza 0,54 no se
resuelve
a la opción más probable, y un `noul` de 0,5 no se resuelve ni a sí ni a no: se marcan para
revisión.
Sin esto, la capa de clasificación sería una forma elegante de inventar datos.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .contrato import (
    Politica,
    Pregunta,
    PreguntaChoice,
    PreguntaNoul,
    PreguntaScore,
    Respuesta,
    RespuestaChoice,
    RespuestaNoul,
    RespuestaScore,
)
from .proveedor import Proveedor


@dataclass(frozen=True, slots=True)
class Resolucion:
    """El resultado de una pregunta, ya pasada por el portero.

    `valor` es `None` cuando requiere revisión: **no se entrega la mejor conjetura**. `confianza` se
    conserva igual, para que el revisor humano sepa cuán cerca estaba.
    """

    pregunta: str
    valor: str | bool | None
    confianza: float
    requiere_revision: bool
    motivo: str | None = None


def resolver(
    estado: Mapping[str, str],
    preguntas: list[Pregunta],
    proveedor: Proveedor,
    politica: Politica | None = None,
) -> list[Resolucion]:
    """Resuelve todas las preguntas en **una sola pasada** sobre el mismo estado.

    Una pasada y no una por pregunta: comparten la interpretación del estado, así que no pueden
    contradecirse entre sí.
    """
    if not preguntas:
        return []
    efectiva = politica or Politica()
    respuestas = proveedor.responder(estado, preguntas)
    return [_resolver_una(p, respuestas.get(p.id), efectiva) for p in preguntas]


def _resolver_una(
    pregunta: Pregunta, respuesta: Respuesta | None, politica: Politica
) -> Resolucion:
    if respuesta is None:
        return Resolucion(
            pregunta=pregunta.id,
            valor=None,
            confianza=0.0,
            requiere_revision=True,
            motivo="el proveedor no respondió esta pregunta",
        )

    if isinstance(pregunta, PreguntaNoul):
        if not isinstance(respuesta, RespuestaNoul):
            raise TypeError(f"{pregunta.id}: se esperaba una respuesta 'noul'")
        return _resolver_noul(pregunta, respuesta, politica)

    if isinstance(respuesta, (RespuestaChoice, RespuestaScore)):
        valor = respuesta.eleccion if isinstance(respuesta, RespuestaChoice) else respuesta.nivel
        return _resolver_categorica(pregunta, valor, respuesta.confianza, politica)

    raise TypeError(f"{pregunta.id}: tipo de respuesta inesperado")


def _resolver_noul(
    pregunta: PreguntaNoul, respuesta: RespuestaNoul, politica: Politica
) -> Resolucion:
    probabilidad = respuesta.probabilidad
    if probabilidad >= politica.noul_afirmativo:
        return Resolucion(pregunta.id, True, probabilidad, False)
    if probabilidad <= politica.noul_negativo:
        return Resolucion(pregunta.id, False, probabilidad, False)
    return Resolucion(
        pregunta=pregunta.id,
        valor=None,
        confianza=probabilidad,
        requiere_revision=True,
        motivo=(
            f"probabilidad {probabilidad:.2f} en la banda gris "
            f"({politica.noul_negativo:.2f}–{politica.noul_afirmativo:.2f}): no es ni sí ni no"
        ),
    )


def _resolver_categorica(
    pregunta: PreguntaChoice | PreguntaScore, valor: str, confianza: float, politica: Politica
) -> Resolucion:
    if confianza < politica.umbral_confianza:
        return Resolucion(
            pregunta=pregunta.id,
            valor=None,
            confianza=confianza,
            requiere_revision=True,
            motivo=(
                f"confianza {confianza:.2f}, por debajo del umbral "
                f"{politica.umbral_confianza:.2f}: se resuelve con una persona, no con la opción "
                "más probable"
            ),
        )
    return Resolucion(pregunta.id, valor, confianza, False)
