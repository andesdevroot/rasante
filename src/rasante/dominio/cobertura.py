"""Métrica de cobertura del motor (E4). Módulo puro (solo stdlib).

Responde la pregunta que el paper necesita y que un conteo de tests no responde:

> De los parámetros que una zona real declara, **¿cuántos puede concluir el motor, y qué le falta a
> cada uno de los que no?**

No es una métrica del software. Es una métrica del **corpus** y del **expediente**, y por eso
discrimina: un `P` porque la ordenanza remite a otra norma no se arregla igual que un `P` porque el
proyecto no declaró su antejarín. `motor.MotivoPendiente` ya distingue esas causas; acá solo se
cuentan.

**El reporte no reimplementa la cascada.** Lee `Veredicto.motivo`, que el motor calculó con la misma
función que decidió el veredicto. Si se agregara un paso a la cascada y no al reporte, no podrían
divergir: hay una sola definición.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .modelos import CodigoVeredicto, Veredicto


@dataclass(frozen=True, slots=True)
class Cobertura:
    """El reparto de los parámetros de una zona entre concluidos y pendientes, con el porqué.

    `por_motivo` trae **solo los pendientes**. Una lista vacía de códigos significa que todos los
    parámetros se concluyeron, y eso es un dato, no una ausencia.
    """

    total: int
    por_codigo: Mapping[str, tuple[str, ...]]
    por_motivo: Mapping[str, tuple[str, ...]]

    @property
    def concluidos(self) -> int:
        """`C` + `NC` + `NO_PROCEDE`: los que el motor pudo afirmar, en cualquier dirección."""
        pendientes = self.por_codigo.get(CodigoVeredicto.PENDIENTE.value, ())
        return self.total - len(pendientes)

    @property
    def pendientes(self) -> int:
        return self.total - self.concluidos

    @property
    def proporcion(self) -> float:
        """Qué fracción de los parámetros declarados pudo concluir el motor, entre 0 y 1.

        `0.0` cuando la zona no declara nada: no hay nada que cubrir, y dividir por cero sería una
        mentira peor que un cero.
        """
        return self.concluidos / self.total if self.total else 0.0

    def codigos(self, motivo: str) -> tuple[str, ...]:
        """Los parámetros pendientes por esa causa, en orden determinista."""
        return self.por_motivo.get(motivo, ())


def medir(veredictos: Iterable[Veredicto]) -> Cobertura:
    """Cuenta los veredictos de una evaluación. El orden de salida es determinista."""
    por_codigo: dict[str, list[str]] = {}
    por_motivo: dict[str, list[str]] = {}
    total = 0
    for veredicto in veredictos:
        total += 1
        por_codigo.setdefault(veredicto.codigo.value, []).append(veredicto.clave)
        if veredicto.codigo is CodigoVeredicto.PENDIENTE:
            # Un `P` sin motivo no debería existir: `_decidir` siempre sabe por qué. Si apareciera,
            # se cuenta igual y se ve en el reporte, en vez de desaparecer.
            por_motivo.setdefault(veredicto.motivo or "sin_motivo", []).append(veredicto.clave)
    return Cobertura(
        total=total,
        por_codigo=MappingProxyType({k: tuple(sorted(v)) for k, v in sorted(por_codigo.items())}),
        por_motivo=MappingProxyType({k: tuple(sorted(v)) for k, v in sorted(por_motivo.items())}),
    )
