"""El puente: hechos que el corpus no puede calcular, resueltos por clasificación (T1.10).

`2.6.4` declara `hechos_pendientes`: cosas que deciden si un proyecto tiene la calidad de Conjunto
Armónico y que **no son aritmética sobre el proyecto**. Si el predio constituye una manzana
existente, o si es una fusión predial del art. 63 del DFL 458, no se deduce de una superficie: se
acredita con el acta registral. El motor no puede calcularlo y no debe fingir que puede.

Este módulo los resuelve con la capa de clasificación (D19) y los entrega al motor como **hechos
externos**. Tres invariantes lo gobiernan:

1. **Sin documento no se pregunta.** Si el estado no trae una sola línea de texto, el proveedor no
   se llama: no se gasta una consulta para que un modelo adivine sobre la nada. Todo queda
   indeterminado, y por lo tanto en `P`.
2. **Lo que no se resuelve no se inventa.** Una respuesta bajo el umbral deja el hecho en `None`, y
   el motor lo convierte en `P`. Nunca en el límite permisivo.
3. **Una respuesta no se redondea a un booleano.** En `choice`/`score` el corpus declara qué
   valores vuelven cierto el hecho; cualquier otro valor resuelto lo vuelve falso. No se infiere.

## Qué NO hace

No emite hallazgos. El único lugar que reporta `CLASIFICACION_INDETERMINADA` es
`dominio.factibilidad`, por parámetro y por límite. Si el puente emitiera además uno por hecho, el
mismo dato faltante aparecería dos veces en el informe del revisor. Acá se expone `motivos()`, que
explica **por qué** cada hecho quedó pendiente; `factibilidad` dice **qué** falta.

## La consecuencia que hay que decir en voz alta

Un hecho `None` da `P`, y un `P` no es una aprobación. Si el expediente no acredita la fusión
predial, el proyecto **no** recibe el aumento de `cus`: queda pendiente hasta que alguien lo mire.
Es el mismo invariante de siempre, aplicado a la fuente en vez de al cálculo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from rasante.clasificacion.contrato import (
    Politica,
    PreguntaDeHecho,
    PreguntaNoul,
)
from rasante.clasificacion.porteria import Resolucion, resolver
from rasante.clasificacion.proveedor import Proveedor

MOTIVO_SIN_DOCUMENTO = (
    "el expediente no aporta texto para clasificar: no se consulta al proveedor sobre la nada"
)


@dataclass(frozen=True, slots=True)
class ResultadoPuente:
    """Los hechos que el puente pudo resolver, y por qué no pudo con los demás."""

    hechos: Mapping[str, bool | None]
    resoluciones: tuple[Resolucion, ...] = ()

    @property
    def pendientes(self) -> tuple[str, ...]:
        """Los hechos que quedaron indeterminados, en orden determinista."""
        return tuple(sorted(n for n, v in self.hechos.items() if v is None))

    def motivos(self) -> Mapping[str, str]:
        """Por qué cada hecho pendiente lo está. Lo que el revisor necesita para conseguirlo."""
        return MappingProxyType(
            {
                r.pregunta: r.motivo or "el proveedor no dio una respuesta para este hecho"
                for r in self.resoluciones
                if r.requiere_revision
            }
        )


def resolver_hechos(
    declaradas: Mapping[str, PreguntaDeHecho],
    estado: Mapping[str, str],
    proveedor: Proveedor,
    politica: Politica | None = None,
) -> ResultadoPuente:
    """Resuelve los hechos que el corpus declara como pendientes de clasificación.

    El orden de las preguntas es determinista (por nombre de hecho), no el del diccionario: dos
    corridas sobre el mismo expediente deben producir exactamente el mismo resultado.
    """
    ordenadas = [declaradas[nombre] for nombre in sorted(declaradas)]
    if not ordenadas:
        return ResultadoPuente(hechos=MappingProxyType({}))

    if not _hay_texto(estado):
        return ResultadoPuente(
            hechos=MappingProxyType({d.hecho: None for d in ordenadas}),
            resoluciones=tuple(
                Resolucion(
                    pregunta=d.hecho,
                    valor=None,
                    confianza=0.0,
                    requiere_revision=True,
                    motivo=MOTIVO_SIN_DOCUMENTO,
                )
                for d in ordenadas
            ),
        )

    resoluciones = resolver(estado, [d.pregunta for d in ordenadas], proveedor, politica)
    por_pregunta = {r.pregunta: r for r in resoluciones}
    return ResultadoPuente(
        hechos=MappingProxyType(
            {d.hecho: _a_booleano(d, por_pregunta[d.hecho]) for d in ordenadas}
        ),
        resoluciones=tuple(resoluciones),
    )


def _hay_texto(estado: Mapping[str, str]) -> bool:
    """Si el estado trae algo que un clasificador pueda leer."""
    return any(valor.strip() for valor in estado.values())


def _a_booleano(declarada: PreguntaDeHecho, resolucion: Resolucion) -> bool | None:
    """Traduce una respuesta tipada al booleano del hecho.

    Un `noul` **ya es** el booleano: el portero lo resolvió contra su banda gris. Una respuesta
    categórica se compara contra el `verdadero_si` que declara el corpus — nunca contra la opción
    más parecida, y nunca contra la más permisiva.
    """
    if resolucion.requiere_revision or resolucion.valor is None:
        return None
    if isinstance(declarada.pregunta, PreguntaNoul):
        return bool(resolucion.valor)
    return str(resolucion.valor) in declarada.verdadero_si
