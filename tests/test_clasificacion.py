"""Capa de clasificación con contrato tipado (D19).

El motor solo sabe comparar números. Usos de suelo, agrupamiento y las condiciones que **no** son
aritmética sobre el proyecto —`dimension_b`: ¿es una manzana?, `dimension_c`: ¿es una
fusión predial?—
no tienen representación. Esta capa las responde con las tres primitivas de JEV —`choice`, `noul`,
`score`— y **devuelve respuestas tipadas con confianza, no prosa**.

**El portero es lo que importa.** Una respuesta por debajo del umbral **no se resuelve**: queda
marcada para revisión humana. Es D18 aplicado aguas arriba: la confianza decide *si un dato está
listo*, no *cuánto cumple*. Nunca se redondea una duda hacia el lado permisivo.

Los umbrales por defecto salen de los datos publicados de JEV: en su benchmark, las inyecciones
puntuaron 0,86–0,99 y los mensajes normales 0,01–0,20.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from rasante.clasificacion.contrato import (
    ErrorClasificacion,
    Politica,
    Pregunta,
    PreguntaChoice,
    PreguntaNoul,
    PreguntaScore,
    RespuestaChoice,
    RespuestaNoul,
    RespuestaScore,
    tipo_de,
)
from rasante.clasificacion.porteria import resolver
from rasante.clasificacion.proveedor import ProveedorGuionizado, ProveedorJev

USOS = {
    "residencial": "vivienda, en cualquiera de sus formas",
    "equipamiento": "comercio, culto, educación, salud, deporte, seguridad",
    "actividad_productiva": "talleres, bodegas e industria inofensiva",
    "infraestructura": "sanitaria, energética o de transporte",
}
ESTADO = {"ordenanza": "Z-4: usos permitidos equipamiento y área verde."}


# --- el contrato ---


def test_cada_primitiva_declara_su_tipo() -> None:
    assert tipo_de(PreguntaChoice("u", "¿?", USOS)).value == "choice"
    assert tipo_de(PreguntaNoul("c", "¿?")).value == "noul"
    assert tipo_de(PreguntaScore("s", "¿?", ("bajo", "medio", "alto"))).value == "score"


def test_una_eleccion_necesita_al_menos_dos_opciones() -> None:
    with pytest.raises(ErrorClasificacion, match="criterios"):
        PreguntaChoice("u", "¿?", {"unica": "la única opción"})


def test_un_score_necesita_al_menos_dos_niveles() -> None:
    with pytest.raises(ErrorClasificacion, match="niveles"):
        PreguntaScore("s", "¿?", ("solo_uno",))


def test_una_pregunta_necesita_instrucciones() -> None:
    with pytest.raises(ErrorClasificacion, match="instrucciones"):
        PreguntaNoul("c", "   ")


@pytest.mark.parametrize("confianza", [-0.1, 1.1])
def test_la_confianza_vive_entre_cero_y_uno(confianza: float) -> None:
    with pytest.raises(ErrorClasificacion, match="confianza"):
        RespuestaChoice("residencial", confianza, {"residencial": 1.0})


def test_una_eleccion_fuera_del_conjunto_es_un_error() -> None:
    with pytest.raises(ErrorClasificacion, match="no está entre"):
        RespuestaChoice("industrial_pesada", 1.0, {"industrial_pesada": 1.0}, opciones=USOS)


def test_una_probabilidad_de_noul_fuera_de_rango_es_un_error() -> None:
    with pytest.raises(ErrorClasificacion, match="probabilidad"):
        RespuestaNoul(1.4)


# --- el portero: lo que decide si un dato está listo ---


def test_una_eleccion_segura_se_resuelve() -> None:
    proveedor = ProveedorGuionizado(
        {"uso": RespuestaChoice("equipamiento", 0.97, {"equipamiento": 0.97})}
    )
    pregunta = PreguntaChoice("uso", "¿Qué uso permite la zona?", USOS)
    (resolucion,) = resolver(ESTADO, [pregunta], proveedor)
    assert resolucion.valor == "equipamiento"
    assert not resolucion.requiere_revision


def test_una_eleccion_dudosa_va_a_revision_humana() -> None:
    """Un 0,54 no es una respuesta: es una pregunta para una persona."""
    proveedor = ProveedorGuionizado(
        {"uso": RespuestaChoice("equipamiento", 0.54, {"equipamiento": 0.54, "residencial": 0.46})}
    )
    pregunta = PreguntaChoice("uso", "¿Qué uso permite la zona?", USOS)
    (resolucion,) = resolver(ESTADO, [pregunta], proveedor)
    assert resolucion.requiere_revision
    assert resolucion.valor is None, "no se resuelve a la opción más probable"
    assert "0.54" in (resolucion.motivo or "")


def test_un_noul_claro_se_resuelve_booleano() -> None:
    proveedor = ProveedorGuionizado({"armonico": RespuestaNoul(0.96)})
    (resolucion,) = resolver(
        ESTADO, [PreguntaNoul("armonico", "¿Es Conjunto Armónico?")], proveedor
    )
    assert resolucion.valor is True


def test_un_noul_claro_en_negativo_se_resuelve_falso() -> None:
    proveedor = ProveedorGuionizado({"armonico": RespuestaNoul(0.02)})
    (resolucion,) = resolver(ESTADO, [PreguntaNoul("armonico", "¿?")], proveedor)
    assert resolucion.valor is False


def test_un_noul_en_la_banda_gris_va_a_revision() -> None:
    """0,5 no es ni sí ni no. Resolverlo hacia cualquiera de los dos lados sería inventar."""
    proveedor = ProveedorGuionizado({"armonico": RespuestaNoul(0.5)})
    (resolucion,) = resolver(ESTADO, [PreguntaNoul("armonico", "¿?")], proveedor)
    assert resolucion.requiere_revision
    assert resolucion.valor is None
    assert "banda" in (resolucion.motivo or "").lower()


def test_la_banda_del_noul_es_ajustable() -> None:
    politica = Politica(noul_afirmativo=0.5, noul_negativo=0.1)
    proveedor = ProveedorGuionizado({"armonico": RespuestaNoul(0.5)})
    (resolucion,) = resolver(ESTADO, [PreguntaNoul("armonico", "¿?")], proveedor, politica)
    assert resolucion.valor is True


def test_un_score_seguro_se_resuelve() -> None:
    proveedor = ProveedorGuionizado({"legibilidad": RespuestaScore("alta", 0.9, {"alta": 0.9})})
    pregunta = PreguntaScore(
        "legibilidad", "¿Qué tan legible es la página?", ("baja", "media", "alta")
    )
    (resolucion,) = resolver(ESTADO, [pregunta], proveedor)
    assert resolucion.valor == "alta"


def test_un_score_dudoso_va_a_revision() -> None:
    proveedor = ProveedorGuionizado({"legibilidad": RespuestaScore("media", 0.6, {"media": 0.6})})
    pregunta = PreguntaScore("legibilidad", "¿?", ("baja", "media", "alta"))
    (resolucion,) = resolver(ESTADO, [pregunta], proveedor)
    assert resolucion.requiere_revision


def test_las_resoluciones_conservan_la_confianza_para_auditar() -> None:
    proveedor = ProveedorGuionizado({"armonico": RespuestaNoul(0.93)})
    (resolucion,) = resolver(ESTADO, [PreguntaNoul("armonico", "¿?")], proveedor)
    assert resolucion.confianza == 0.93


# --- una pasada, varias preguntas ---


def test_varias_preguntas_se_resuelven_en_una_pasada() -> None:
    """Como JEV: un estado, N preguntas, una sola llamada al proveedor."""
    proveedor = ProveedorGuionizado(
        {
            "uso": RespuestaChoice("equipamiento", 0.95, {"equipamiento": 0.95}),
            "armonico": RespuestaNoul(0.9),
            "legibilidad": RespuestaScore("alta", 0.85, {"alta": 0.85}),
        }
    )
    preguntas: list[Pregunta] = [
        PreguntaChoice("uso", "¿?", USOS),
        PreguntaNoul("armonico", "¿?"),
        PreguntaScore("legibilidad", "¿?", ("baja", "media", "alta")),
    ]
    resoluciones = resolver(ESTADO, preguntas, proveedor)
    assert [r.pregunta for r in resoluciones] == ["uso", "armonico", "legibilidad"]
    assert proveedor.llamadas == 1, "una sola pasada, no una por pregunta"
    assert all(not r.requiere_revision for r in resoluciones)


def test_sin_preguntas_no_se_llama_al_proveedor() -> None:
    proveedor = ProveedorGuionizado({})
    assert resolver(ESTADO, [], proveedor) == []
    assert proveedor.llamadas == 0


def test_una_respuesta_que_falta_va_a_revision() -> None:
    """Si el proveedor no contesta una pregunta, no se inventa: queda pendiente."""
    proveedor = ProveedorGuionizado({})
    (resolucion,) = resolver(ESTADO, [PreguntaNoul("armonico", "¿?")], proveedor)
    assert resolucion.requiere_revision


# --- el proveedor JEV ---


RESPUESTA_JEV: dict[str, Any] = {
    "answers": {
        "uso": {
            "type": "choice",
            "choice": "equipamiento",
            "confidence": 0.97,
            "probabilities": {"equipamiento": 0.97, "residencial": 0.03},
        },
        "armonico": {"type": "noul", "noul": 0.91},
    },
    "model": "typesafe/jev-1.13",
    "usage": {"cost": 0.000016},
}


def test_el_proveedor_jev_traduce_la_respuesta() -> None:
    transporte = httpx.MockTransport(lambda _: httpx.Response(200, json=RESPUESTA_JEV))
    with httpx.Client(transport=transporte) as cliente:
        proveedor = ProveedorJev("clave-de-prueba", cliente=cliente)
        respuestas = proveedor.responder(
            ESTADO, [PreguntaChoice("uso", "¿?", USOS), PreguntaNoul("armonico", "¿?")]
        )
    uso, armonico = respuestas["uso"], respuestas["armonico"]
    assert isinstance(uso, RespuestaChoice)
    assert isinstance(armonico, RespuestaNoul)
    assert uso.eleccion == "equipamiento"
    assert armonico.probabilidad == 0.91


def test_el_proveedor_jev_manda_el_estado_y_las_preguntas() -> None:
    visto: dict[str, Any] = {}

    def handler(peticion: httpx.Request) -> httpx.Response:
        import json

        visto.update(json.loads(peticion.content))
        return httpx.Response(200, json=RESPUESTA_JEV)

    with httpx.Client(transport=httpx.MockTransport(handler)) as cliente:
        ProveedorJev("clave", cliente=cliente).responder(
            ESTADO, [PreguntaChoice("uso", "¿Qué uso?", USOS)]
        )
    assert visto["state"] == ESTADO
    assert visto["questions"]["uso"]["type"] == "choice"
    assert set(visto["questions"]["uso"]["criteria"]) == set(USOS)


def test_el_proveedor_jev_falla_explicito_sin_clave() -> None:
    with pytest.raises(ErrorClasificacion, match="clave"):
        ProveedorJev("")
