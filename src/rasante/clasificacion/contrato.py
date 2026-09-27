"""El contrato tipado: preguntas y respuestas.

Una pregunta es un **dato**, no código: `choice` elige entre opciones con definición, `noul` pide
una
probabilidad de sí, `score` ubica en niveles ordenados. Una petición lleva un **estado** (bloques de
texto con nombre) y varias preguntas, y se responden en una sola pasada.

Es el contrato de JEV, pero no depende de JEV: cualquier proveedor que lo cumpla sirve.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ErrorClasificacion(ValueError):
    """Una pregunta o una respuesta no cumple el contrato."""


class TipoPregunta(StrEnum):
    """Las tres primitivas."""

    CHOICE = "choice"
    NOUL = "noul"
    SCORE = "score"


def _exigir_texto(valor: str, campo: str) -> None:
    if not valor.strip():
        raise ErrorClasificacion(f"una pregunta necesita '{campo}' no vacío")


@dataclass(frozen=True, slots=True)
class PreguntaChoice:
    """Elige una opción de un conjunto. Cada opción lleva su definición: el proveedor lee
    literal."""

    id: str
    instrucciones: str
    criterios: Mapping[str, str]

    def __post_init__(self) -> None:
        _exigir_texto(self.id, "id")
        _exigir_texto(self.instrucciones, "instrucciones")
        if len(self.criterios) < 2:
            raise ErrorClasificacion(
                "una pregunta 'choice' necesita al menos dos 'criterios': con una opción no hay "
                "elección"
            )


@dataclass(frozen=True, slots=True)
class PreguntaNoul:
    """Una afirmación de sí/no. Devuelve una probabilidad, no un booleano."""

    id: str
    instrucciones: str

    def __post_init__(self) -> None:
        _exigir_texto(self.id, "id")
        _exigir_texto(self.instrucciones, "instrucciones")


@dataclass(frozen=True, slots=True)
class PreguntaScore:
    """Ubica el estado en niveles ordenados, de menor a mayor."""

    id: str
    instrucciones: str
    niveles: tuple[str, ...]

    def __post_init__(self) -> None:
        _exigir_texto(self.id, "id")
        _exigir_texto(self.instrucciones, "instrucciones")
        if len(self.niveles) < 2:
            raise ErrorClasificacion("una pregunta 'score' necesita al menos dos 'niveles'")


Pregunta = PreguntaChoice | PreguntaNoul | PreguntaScore


def tipo_de(pregunta: Pregunta) -> TipoPregunta:
    if isinstance(pregunta, PreguntaChoice):
        return TipoPregunta.CHOICE
    if isinstance(pregunta, PreguntaNoul):
        return TipoPregunta.NOUL
    return TipoPregunta.SCORE


def _exigir_rango(valor: float, campo: str) -> None:
    if not 0.0 <= valor <= 1.0:
        raise ErrorClasificacion(f"la {campo} debe estar entre 0 y 1, no {valor}")


@dataclass(frozen=True, slots=True)
class RespuestaChoice:
    """La opción elegida, su confianza y el reparto de probabilidad entre las opciones."""

    eleccion: str
    confianza: float
    probabilidades: Mapping[str, float]
    opciones: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        _exigir_rango(self.confianza, "confianza")
        if self.opciones is not None and self.eleccion not in self.opciones:
            raise ErrorClasificacion(
                f"la elección {self.eleccion!r} no está entre las opciones ofrecidas"
            )


@dataclass(frozen=True, slots=True)
class RespuestaNoul:
    """La probabilidad de que la afirmación sea cierta."""

    probabilidad: float

    def __post_init__(self) -> None:
        _exigir_rango(self.probabilidad, "probabilidad")


@dataclass(frozen=True, slots=True)
class RespuestaScore:
    """El nivel asignado, con su confianza y el reparto entre niveles."""

    nivel: str
    confianza: float
    probabilidades: Mapping[str, float]

    def __post_init__(self) -> None:
        _exigir_rango(self.confianza, "confianza")


Respuesta = RespuestaChoice | RespuestaNoul | RespuestaScore


@dataclass(frozen=True, slots=True)
class Politica:
    """Cuándo una respuesta cuenta como resuelta.

    Los valores por defecto salen de los datos publicados de JEV: en su benchmark, las inyecciones
    puntuaron 0,86–0,99 y los mensajes normales 0,01–0,20. Una banda gris de 0,20 a 0,80 manda a
    revisión lo que no es ni sí ni no.
    """

    umbral_confianza: float = 0.8
    noul_afirmativo: float = 0.8
    noul_negativo: float = 0.2
