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

from rasante.dominio.modelos import Cita


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


@dataclass(frozen=True, slots=True)
class PreguntaDeHecho:
    """Una pregunta del corpus, atada al **hecho** que resuelve y a la norma que lo exige.

    El corpus no pregunta en general: pregunta para llenar un hueco concreto. `hecho` es el nombre
    del hecho que el motor espera, y `cita` la norma que lo establece — sin cita, un hecho
    clasificado no es trazable y el veredicto que dependa de él tampoco.

    `verdadero_si` es cómo una respuesta categórica se vuelve booleana. Un `noul` ya es booleano y
    no lo lleva. En `choice`/`score` el corpus declara **explícitamente** qué valores hacen cierto
    el hecho: cualquier otro valor resuelto lo hace falso, y una respuesta sin resolver lo deja
    indeterminado. La alternativa —inferir el booleano de la opción "más parecida"— sería inventar.
    """

    hecho: str
    pregunta: Pregunta
    cita: Cita
    verdadero_si: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.pregunta.id != self.hecho:
            raise ErrorClasificacion(
                f"la pregunta {self.pregunta.id!r} resuelve el hecho {self.hecho!r}: los "
                "identificadores deben coincidir, o el motor no sabría a qué hecho corresponde "
                "la respuesta"
            )
        if isinstance(self.pregunta, PreguntaNoul):
            if self.verdadero_si:
                raise ErrorClasificacion(
                    f"{self.hecho!r}: un 'noul' ya es booleano, no lleva 'verdadero_si'"
                )
            return
        if not self.verdadero_si:
            raise ErrorClasificacion(
                f"{self.hecho!r}: una pregunta '{tipo_de(self.pregunta).value}' necesita "
                "'verdadero_si': sin eso no se sabe qué respuesta vuelve cierto el hecho"
            )
        ofrecidos = (
            set(self.pregunta.criterios)
            if isinstance(self.pregunta, PreguntaChoice)
            else set(self.pregunta.niveles)
        )
        ajenos = sorted(self.verdadero_si - ofrecidos)
        if ajenos:
            raise ErrorClasificacion(
                f"{self.hecho!r}: 'verdadero_si' nombra valores que la pregunta no ofrece: {ajenos}"
            )
