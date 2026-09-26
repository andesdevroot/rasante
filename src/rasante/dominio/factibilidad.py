"""Verificador de factibilidad geométrica (T1.5). Módulo puro (solo stdlib).

D15: los parámetros están **acoplados**, y el motor los evalúa aislados. Chequeados por separado,
todos pueden dar `C` en un proyecto que no se puede construir. Este módulo caza ese caso.

## Las dos cosas que se verifican

1. **Factibilidad del proyecto declarado.** La superficie edificada total no puede exceder la del
   primer piso multiplicada por el número de pisos: cinco pisos de 500 m² de huella no pueden alojar
   3.200 m². Es aritmética, no interpretación.

2. **Consistencia del conjunto normativo.** Si el `cus` que fija la ordenanza excede el máximo
   alcanzable con sus propios `cos`, `cos` de pisos superiores y altura, esa norma es inalcanzable
   para cualquier proyecto. Puede ser un error del corpus o una particularidad real; por eso es
   **advertencia**, no bloqueante.

## Lo que NO se afirma

Sin `numero_pisos`, sin superficies declaradas o sin altura normada, no se emite hallazgo. Es el
mismo principio que el `P` del motor: **lo que no se puede verificar no se afirma**, en ninguna
dirección.
"""

from __future__ import annotations

from decimal import Decimal

from .modelos import (
    Cita,
    CodigoHallazgo,
    Hallazgo,
    Parametro,
    Proyecto,
    Severidad,
    Zona,
)
from .reglas import Reglas

# Referencia de la OGUC `2.1.23`: 3,50 m por piso. Solo se usa para traducir una altura normada
# en metros a un número de pisos cuando la ordenanza no fija pisos. No es la altura de un proyecto
# real.
PISO_REFERENCIA_M = Decimal("3.50")


def verificar(proyecto: Proyecto, zona: Zona, reglas: Reglas) -> list[Hallazgo]:
    """Hallazgos de factibilidad. Lista vacía significa "no se puede afirmar que haya problema"."""
    return [
        *_proyecto_imposible(proyecto, zona, reglas),
        *_cus_inalcanzable(zona, reglas),
    ]


# --- 1. ¿El proyecto declarado se puede construir? ---


def _proyecto_imposible(proyecto: Proyecto, zona: Zona, reglas: Reglas) -> list[Hallazgo]:
    huella = proyecto.superficie_primer_piso_m2
    total = proyecto.superficie_edificada_m2
    pisos = proyecto.numero_pisos
    if huella is None or total is None or pisos is None or pisos <= 0:
        return []

    cabe = huella * pisos
    if total <= cabe:
        return []

    cita = _cita_del_acoplamiento("cus", zona, reglas)
    if cita is None:
        return []  # sin norma que citar no se afirma nada, ni siquiera una verdad aritmética

    return [
        Hallazgo(
            codigo=CodigoHallazgo.PROYECTO_IMPOSIBLE,
            severidad=Severidad.BLOQUEANTE,
            mensaje=(
                f"la superficie edificada declarada ({total} m²) excede la que cabe en {pisos} "
                f"pisos de {huella} m² de huella ({cabe} m²). El proyecto no se puede construir."
            ),
            cita=cita,
            parametros=_claves(zona, "cos.primer_piso", "cos", "cus"),
        )
    ]


# --- 2. ¿El conjunto normativo es alcanzable? ---


def _cus_inalcanzable(zona: Zona, reglas: Reglas) -> list[Hallazgo]:
    cus = _valor(zona, "cus")
    primer_piso = _valor(zona, "cos.primer_piso") or _valor(zona, "cos")
    pisos_superiores = _valor(zona, "cos.pisos_superiores")
    pisos = _pisos_normados(zona)

    if cus is None or primer_piso is None or pisos is None or pisos < 1:
        return []

    cita = _cita_del_acoplamiento("cus", zona, reglas)
    if cita is None:
        return []
    # Sin `cos` de pisos superiores se supone que cada piso repite la huella del primero: es la cota
    # más generosa, así que si aun así no alcanza, no alcanza de ninguna manera.
    por_piso_superior = pisos_superiores if pisos_superiores is not None else primer_piso

    alcanzable = primer_piso + (pisos - 1) * por_piso_superior
    if cus <= alcanzable:
        return []

    return [
        Hallazgo(
            codigo=CodigoHallazgo.CUS_INALCANZABLE,
            severidad=Severidad.ADVERTENCIA,
            mensaje=(
                f"el coeficiente de constructibilidad normado ({cus}) excede el máximo alcanzable "
                f"con la ocupación de suelo y la altura de esta zona ({alcanzable}). Ningún "
                "proyecto podría cumplirla: revisar la ordenanza o el corpus."
            ),
            cita=cita,
            parametros=_claves(
                zona, "cos.primer_piso", "cos.pisos_superiores", "cus", "altura_maxima"
            ),
        )
    ]


def _pisos_normados(zona: Zona) -> int | None:
    """Cuántos pisos permite la norma, según su altura máxima en metros."""
    altura = zona.parametro("altura_maxima")
    if altura is None or altura.valor is None or altura.unidad != "m":
        return None
    return int(altura.valor / PISO_REFERENCIA_M)


# --- utilidades ---


def _valor(zona: Zona, clave: str) -> Decimal | None:
    parametro = zona.parametro(clave)
    return None if parametro is None else parametro.valor


def _claves(zona: Zona, *candidatas: str) -> tuple[str, ...]:
    """Las claves que la zona realmente declara, de las candidatas dadas. Para no citar de más."""
    return tuple(c for c in candidatas if zona.parametro(c) is not None)


def _cita_del_acoplamiento(objetivo: str, zona: Zona, reglas: Reglas) -> Cita | None:
    """La cita que respalda el acoplamiento geométrico, o `None` si no hay ninguna.

    Se prefiere la relación del corpus (que es la que establece el acoplamiento); si no está, sirve
    la cita del propio parámetro. **Sin cita no se emite el hallazgo**: un hallazgo sin respaldo
    normativo es una opinión, y el proyecto no firma opiniones.
    """
    for relacion in reglas.relaciones:
        if relacion.objetivo == objetivo:
            return relacion.cita
    parametro: Parametro | None = zona.parametro(objetivo)
    return None if parametro is None else parametro.cita
