"""Los proveedores: quién responde las preguntas.

El contrato es agnóstico de proveedor a propósito. JEV es el que mejor encaja —está hecho para esto,
cuesta $0,042 por millón de tokens de entrada y responde en ~194 ms— pero el mismo contrato lo puede
cumplir DeepSeek, un modelo local, o un guionizado para tests.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import httpx

from .contrato import (
    ErrorClasificacion,
    Pregunta,
    PreguntaChoice,
    PreguntaNoul,
    PreguntaScore,
    Respuesta,
    RespuestaChoice,
    RespuestaNoul,
    RespuestaScore,
    tipo_de,
)

TIEMPO_LIMITE = 60.0


class Proveedor(Protocol):
    """Quien responde las preguntas tipadas sobre un estado."""

    def responder(
        self, estado: Mapping[str, str], preguntas: Sequence[Pregunta]
    ) -> Mapping[str, Respuesta]:
        """Una respuesta por pregunta, indexada por `id`. Puede omitir las que no sepa."""
        ...


class ProveedorGuionizado:
    """Respuestas predefinidas. Para tests sin red y para ejercitar el portero."""

    def __init__(self, respuestas: Mapping[str, Respuesta]) -> None:
        self._respuestas = dict(respuestas)
        self.llamadas = 0

    def responder(
        self, estado: Mapping[str, str], preguntas: Sequence[Pregunta]
    ) -> Mapping[str, Respuesta]:
        self.llamadas += 1
        return {p.id: self._respuestas[p.id] for p in preguntas if p.id in self._respuestas}


class ProveedorJev:
    """JEV de TypeSafe, vía OpenRouter.

    Solo texto: **no lee PDFs ni imágenes**, así que el estado se arma con lo que devuelva la
    extracción. Y pierde precisión con detalle irrelevante, así que se manda solo lo que cada
    pregunta necesita.

    Nunca decide cumplimiento: es un modelo, y los modelos no son confiables en aritmética, conteo
    ni
    comparación de fechas. Clasifica; el motor calcula.
    """

    URL = "https://openrouter.ai/api/v1/decisions"

    def __init__(
        self, clave: str, modelo: str = "typesafe/jev-1.13", cliente: httpx.Client | None = None
    ) -> None:
        if not clave.strip():
            raise ErrorClasificacion("el proveedor JEV necesita una clave de API")
        self._clave = clave
        self._modelo = modelo
        self._cliente = cliente or httpx.Client(
            timeout=TIEMPO_LIMITE, follow_redirects=True
        )
        self._propio = cliente is None

    def close(self) -> None:
        if self._propio:
            self._cliente.close()

    def responder(
        self, estado: Mapping[str, str], preguntas: Sequence[Pregunta]
    ) -> Mapping[str, Respuesta]:
        if not preguntas:
            return {}
        cuerpo: dict[str, Any] = {
            "model": self._modelo,
            "state": dict(estado),
            "questions": {p.id: _pregunta_como_json(p) for p in preguntas},
        }
        try:
            respuesta = self._cliente.post(
                self.URL,
                headers={"Authorization": f"Bearer {self._clave}"},
                json=cuerpo,
            )
        except httpx.HTTPError as error:
            raise ErrorClasificacion(f"fallo de red consultando JEV: {error}") from error
        if respuesta.status_code != 200:
            raise ErrorClasificacion(
                f"JEV respondió {respuesta.status_code}: {respuesta.text[:200]}"
            )
        return _respuestas_desde_json(respuesta.json(), preguntas)


def _pregunta_como_json(pregunta: Pregunta) -> dict[str, Any]:
    tipo = tipo_de(pregunta).value
    if isinstance(pregunta, PreguntaChoice):
        return {
            "type": tipo,
            "instructions": pregunta.instrucciones,
            "criteria": dict(pregunta.criterios),
        }
    if isinstance(pregunta, PreguntaScore):
        return {
            "type": tipo,
            "instructions": pregunta.instrucciones,
            "levels": list(pregunta.niveles),
        }
    return {"type": tipo, "instructions": pregunta.instrucciones}


def _respuestas_desde_json(
    datos: Any, preguntas: Sequence[Pregunta]
) -> Mapping[str, Respuesta]:
    crudas = datos.get("answers") if isinstance(datos, dict) else None
    if not isinstance(crudas, dict):
        raise ErrorClasificacion("la respuesta de JEV no trae 'answers'")

    respuestas: dict[str, Respuesta] = {}
    for pregunta in preguntas:
        cruda = crudas.get(pregunta.id)
        if not isinstance(cruda, dict):
            continue  # el portero lo marcará como pendiente
        if isinstance(pregunta, PreguntaNoul):
            respuestas[pregunta.id] = RespuestaNoul(float(cruda["noul"]))
            continue
        if isinstance(pregunta, PreguntaChoice):
            respuestas[pregunta.id] = RespuestaChoice(
                eleccion=str(cruda["choice"]),
                confianza=float(cruda.get("confidence", 0.0)),
                probabilidades={
                    str(k): float(v) for k, v in (cruda.get("probabilities") or {}).items()
                },
                opciones=pregunta.criterios,
            )
            continue
        respuestas[pregunta.id] = RespuestaScore(
            nivel=str(cruda["score"]),
            confianza=float(cruda.get("confidence", 0.0)),
            probabilidades={
                str(k): float(v) for k, v in (cruda.get("probabilities") or {}).items()
            },
        )
    return respuestas
