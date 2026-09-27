"""Monotonía del veredicto bajo refinamiento, y por qué la negativa a concluir la compra (E1).

## El teorema, tal como resultó

Sea `K ⊆ K'` un **refinamiento**: todo hecho que `K` resuelve, `K'` lo resuelve igual, y `K'` puede
además resolver hechos que en `K` eran `None`. Entonces:

1. **`C` y `NC` son estables.** Si `V(K) ∈ {C, NC}`, entonces `V(K') = V(K)`.
2. **`P` es el único inestable, y es inestable en las dos direcciones**: existe `K ⊆ K'` con
   `V(K) = P` y `V(K') = C`, y existe `K ⊆ K'` con `V(K) = P` y `V(K') = NC`.

## Por qué esto es el aporte, y no una obviedad

La monotonía **no es gratis**: es una consecuencia de la negativa a concluir. El motor trata
*cualquier* hecho indeterminado que condicione un límite como motivo de `P`, aunque otro hecho ya
haya descartado esa excepción... no: la descarta con el cortocircuito `X and False = False`, y **eso
es lo que la hace monótona**. Si en cambio eligiera el límite más permisivo cuando un hecho es
desconocido —la alternativa "razonable" que cualquiera escribiría primero— aparecerían inversiones.

La tercera parte de este archivo lo **demuestra por contraste**: implementa esa semántica relajada y
la búsqueda exhaustiva **sí** encuentra inversiones. La negativa a concluir no es prudencia
defensiva: es la condición que compra la estabilidad del veredicto.

## La consecuencia sobre la capa calibrada

De (2) sale, obligado, el diseño del portero:

> Si un `P` puede refinarse a `C` **o** a `NC`, entonces equivocarse resolviendo un hecho como
> **falso** es tan peligroso como resolverlo como cierto. Un umbral de un solo lado —"resuelvo si la
> confianza supera 0,8"— dejaría pasar un `0,3` como falso y produciría un veredicto invertido.

Por eso la banda gris tiene **dos** bordes. La asimetría habitual de los clasificadores se vuelve
acá una **simetría obligatoria**, y es una consecuencia del teorema, no una decisión de tuning.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from rasante.clasificacion.contrato import Politica, PreguntaNoul, RespuestaNoul
from rasante.clasificacion.porteria import resolver
from rasante.clasificacion.proveedor import ProveedorGuionizado
from rasante.corpus.cargador import cargar_reglas, cargar_zona
from rasante.dominio import motor
from rasante.dominio.modelos import (
    CodigoVeredicto,
    EstadoParametro,
    EstadoRevision,
    Limite,
    Parametro,
    Procedencia,
    Proyecto,
    Sentido,
    TipoLimite,
    Vigencia,
    Zona,
)

RAIZ = Path(__file__).resolve().parents[1]
REGLAS = cargar_reglas(RAIZ / "corpus")

# Los hechos que el corpus **no** puede calcular: los resuelve la capa calibrada (T1.10).
EXTERNOS = ("dimension_b", "dimension_c")
ESTADOS: tuple[bool | None, ...] = (None, True, False)
GRILLA_CUS = ("3.5", "4.5", "5.0", "5.5", "5.9", "6.5")


def zona(cus_base: str) -> Zona:
    """Una zona Z-2 con el `cus` que fija el PRC, **firmada**: sin firma todo da `P` (D18)."""
    real = cargar_zona(RAIZ / "corpus" / "prc" / "RM" / "nunoa" / "zonas" / "Z-2.yaml")
    cita = real.parametros["cus"].cita

    def base(clave: str, valor: str, sentido: Sentido) -> Parametro:
        return Parametro(
            id=clave,
            limites=(Limite(TipoLimite.BASE, Decimal(valor), "adimensional", cita),),
            sentido=sentido,
            estado=EstadoParametro.APLICABLE,
            cita=cita,
        )

    return Zona(
        codigo=real.codigo,
        nombre=real.nombre,
        comuna=real.comuna,
        parametros={
            "cus": base("cus", cus_base, Sentido.MAXIMO),
            "superficie_predial_minima": base("superficie_predial_minima", "1000", Sentido.MINIMO),
        },
        vigencia=Vigencia(),
        procedencia=Procedencia(
            url_fuente=real.procedencia.url_fuente,
            hash_fuente=real.procedencia.hash_fuente,
            consolidado_por=real.procedencia.consolidado_por,
            extraido=real.procedencia.extraido,
            revisado_por="Revisor de prueba",
            estado=EstadoRevision.REVISADO,
        ),
    )


def proyecto(cus: str, predio: str = "1000") -> Proyecto:
    """Acogido al Conjunto Armónico: sin eso ninguna excepción de `2.6.5` aplica (D21)."""
    return Proyecto(
        superficie_predio_m2=Decimal(predio),
        numero_viviendas=1,
        superficie_edificada_m2=Decimal(cus) * Decimal(predio),
        acoge_conjunto_armonico=True,
    )


def veredicto(p: Proyecto, z: Zona, estado: Mapping[str, bool | None]) -> CodigoVeredicto:
    return next(v for v in motor.evaluar(p, z, REGLAS, estado) if v.clave == "cus").codigo


def estados_de_conocimiento() -> list[dict[str, bool | None]]:
    return [
        dict(zip(EXTERNOS, valores, strict=True))
        for valores in product(ESTADOS, repeat=len(EXTERNOS))
    ]


def refina(k: Mapping[str, bool | None], kp: Mapping[str, bool | None]) -> bool:
    """`k ⊆ k'`: lo que `k` resuelve, `k'` lo resuelve **igual**. `k'` puede saber más.

    La distinción importa y es la que casi me hace publicar un teorema falso: cambiar un hecho de
    `False` a `True` **no** es refinar, es **revisar**. La información nueva no contradice la vieja.
    """
    return all(v is None or kp[n] is v for n, v in k.items())


def clave(estado: Mapping[str, bool | None]) -> str:
    return ",".join(f"{n}={estado[n]}" for n in EXTERNOS)


# --- 1. monotonía: la búsqueda exhaustiva NO encuentra inversiones ---


def test_ningun_refinamiento_invierte_un_veredicto_ya_concluido() -> None:
    """El teorema, probado por falsación: se recorren **todos** los pares `K ⊆ K'`.

    Si apareciera una sola inversión, el motor no sería monótono y la sección del paper cambiaría.
    Que la búsqueda vuelva vacía **es** el resultado.
    """
    z = zona("4")
    inversiones: list[tuple[str, str, str, str]] = []
    for cus in GRILLA_CUS:
        p = proyecto(cus)
        vistas = {clave(e): veredicto(p, z, e) for e in estados_de_conocimiento()}
        for k, kp in _pares():
            a, b = vistas[clave(k)], vistas[clave(kp)]
            if a is not b and a is not CodigoVeredicto.PENDIENTE:
                inversiones.append((cus, clave(k), clave(kp), f"{a.value}->{b.value}"))
    assert inversiones == [], f"el veredicto no es monótono: {inversiones[:5]}"


def test_lo_concluido_se_mantiene_en_toda_la_grilla() -> None:
    """La misma propiedad desde el otro lado: `C` y `NC` son puntos fijos del refinamiento."""
    z = zona("4")
    for cus in GRILLA_CUS:
        p = proyecto(cus)
        for k, kp in _pares():
            inicial = veredicto(p, z, k)
            if inicial is CodigoVeredicto.PENDIENTE:
                continue
            assert veredicto(p, z, kp) is inicial, (cus, clave(k), clave(kp))


# --- 2. `P` es el único inestable, y lo es en las dos direcciones ---


def test_un_pendiente_puede_refinarse_a_cumple() -> None:
    z, p = zona("4"), proyecto("5.5")
    en_duda = {"dimension_b": True, "dimension_c": None}
    assert veredicto(p, z, en_duda) is CodigoVeredicto.PENDIENTE
    assert veredicto(p, z, {"dimension_b": True, "dimension_c": False}) is CodigoVeredicto.CUMPLE


def test_un_pendiente_puede_refinarse_a_no_cumple() -> None:
    """El mismo estado en duda, resuelto al revés. **Esto obliga a la banda de dos lados.**"""
    z, p = zona("4"), proyecto("5.5")
    en_duda = {"dimension_b": True, "dimension_c": None}
    assert veredicto(p, z, en_duda) is CodigoVeredicto.PENDIENTE
    assert veredicto(p, z, {"dimension_b": True, "dimension_c": True}) is (
        CodigoVeredicto.NO_CUMPLE
    )


def test_ningun_pendiente_es_una_aprobacion_tibia() -> None:
    """Un `P` alcanza los dos veredictos posibles: no es "probablemente cumple"."""
    z, p = zona("4"), proyecto("5.5")
    en_duda = {"dimension_b": None, "dimension_c": None}
    assert veredicto(p, z, en_duda) is CodigoVeredicto.PENDIENTE
    alcanzables = {
        veredicto(p, z, kp) for kp in estados_de_conocimiento() if refina(en_duda, kp)
    }
    assert CodigoVeredicto.CUMPLE in alcanzables
    assert CodigoVeredicto.NO_CUMPLE in alcanzables
    assert CodigoVeredicto.PENDIENTE in alcanzables


# --- 3. la monotonía la compra la negativa a concluir: el contraste ---


def test_sin_la_negativa_a_concluir_aparecerian_inversiones() -> None:
    """El experimento que sostiene el teorema.

    Se reemplaza `_limite_vigente` por la alternativa "razonable" —**si un hecho es desconocido,
    aplica la excepción más permisiva**— y la misma búsqueda exhaustiva **sí** encuentra
    inversiones. O sea: la monotonía no es una propiedad del dominio, es una propiedad **de esta
    semántica de la negativa a concluir**. Es la comparación que convierte una observación en un
    resultado.
    """
    z, p = zona("4"), proyecto("5.5")
    en_duda = {"dimension_b": None, "dimension_c": True}
    resuelto = {"dimension_b": False, "dimension_c": True}
    assert refina(en_duda, resuelto), "resolver `dimension_b` es refinar, no revisar"

    # Con la semántica de la negativa a concluir, el estado en duda es `P` y sigue siéndolo.
    assert veredicto(p, z, en_duda) is CodigoVeredicto.PENDIENTE

    original = motor._limite_vigente
    motor._limite_vigente = _permisiva
    try:
        # Con la permisiva, la duda concede el +50 % (límite 6,0) → `C`.
        assert veredicto(p, z, en_duda) is CodigoVeredicto.CUMPLE
        # Y resolver el hecho —saber MÁS— endurece el límite a 5,2 y **revoca** el cumplimiento.
        assert veredicto(p, z, resuelto) is CodigoVeredicto.NO_CUMPLE
    finally:
        motor._limite_vigente = original


def _permisiva(
    parametro: Parametro, clasificacion: Any, reglas: Any
) -> tuple[Limite | None, tuple[str, ...]]:
    """La semántica relajada, solo para el contraste: ante la duda, concede la excepción más amplia.

    No vive en el motor y no debe vivir ahí. Existe para que el test pueda mostrar qué se perdería.
    """
    candidatos = motor._candidatos(parametro, reglas)
    vigentes = [c for c in candidatos if clasificacion.aplica(c.cuando) is not False]
    if vigentes:
        return max(vigentes, key=lambda x: x.valor), ()
    return parametro.base, ()


# --- 4. la consecuencia sobre el portero ---


def test_la_banda_gris_es_de_dos_lados_y_eso_es_obligatorio() -> None:
    """Consecuencia directa de (2): hay que ser conservador con el «sí» **y** con el «no».

    Un umbral de un solo lado resolvería un `0,3` como falso; y como un `P` falsamente resuelto
    puede producir cualquiera de los dos veredictos, eso alcanza para invertir un informe.
    """
    pregunta = PreguntaNoul(id="dimension_c", instrucciones="¿es fusión predial?")
    politica = Politica()

    def valor(probabilidad: float) -> bool | None:
        proveedor = ProveedorGuionizado({"dimension_c": RespuestaNoul(probabilidad=probabilidad)})
        (r,) = resolver({}, [pregunta], proveedor, politica)
        return r.valor  # type: ignore[return-value]

    assert politica.noul_negativo > 0.0, "el borde inferior no puede ser 0: un 0,05 no es un «no»"
    assert valor(0.95) is True
    assert valor(0.05) is False
    for gris in (0.3, 0.5, 0.7):
        assert valor(gris) is None, f"{gris} cae en la banda y no debe resolverse"


# --- utilidades ---


def _pares() -> list[tuple[Mapping[str, bool | None], Mapping[str, bool | None]]]:
    estados = estados_de_conocimiento()
    return [(k, kp) for k in estados for kp in estados if refina(k, kp) and k != kp]


@pytest.mark.parametrize("estado", estados_de_conocimiento(), ids=clave)
def test_la_grilla_esta_bien_formada(estado: dict[str, bool | None]) -> None:
    """Ancla de la parametrización: los nueve estados existen y se evalúan sin excepción."""
    assert veredicto(proyecto("5.5"), zona("4"), estado) in set(CodigoVeredicto)
