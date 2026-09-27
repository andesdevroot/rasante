"""El puente: de las preguntas del corpus a los hechos del motor (T1.10).

El corpus declara hechos que **no puede calcular**: si el predio constituye una manzana existente,
si es una fusión predial. El motor no puede inventarlos. Este módulo los resuelve con la capa de
clasificación y los inyecta, y estos tests fijan los tres invariantes que lo hacen honesto:

1. sin documento no se pregunta al proveedor,
2. lo que no se resuelve queda en `None` —y por lo tanto en `P`—, nunca en el límite permisivo,
3. una respuesta categórica se traduce con el `verdadero_si` que declara el corpus, no por
   parecido.

Y el que cierra el circuito: **un hecho externo cambia el veredicto del motor**, en las tres
direcciones (cumple / no cumple / pendiente).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from rasante.clasificacion.contrato import (
    ErrorClasificacion,
    PreguntaChoice,
    PreguntaDeHecho,
    PreguntaNoul,
    PreguntaScore,
    RespuestaChoice,
    RespuestaNoul,
)
from rasante.clasificacion.proveedor import ProveedorGuionizado
from rasante.corpus.cargador import cargar_preguntas, cargar_reglas
from rasante.corpus.esquema import ErrorEsquema, validar_corpus, validar_documento
from rasante.dominio.modelos import (
    Cita,
    CodigoVeredicto,
    ErrorDominio,
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
from rasante.dominio.motor import evaluar
from rasante.puente import MOTIVO_SIN_DOCUMENTO, resolver_hechos

RAIZ = Path(__file__).resolve().parents[1]
REGLAS = cargar_reglas(RAIZ / "corpus")
CITA = Cita(norma_id="oguc", articulo="2.6.4", texto="Conjunto Armónico")


# --- helpers ---


def procedencia() -> Procedencia:
    return Procedencia(
        url_fuente="https://www.nunoa.cl/ordenanza.pdf",
        hash_fuente="sha256:" + "0" * 64,
        consolidado_por="Texto refundido, junio 2025",
        extraido="2026-09-26",
        revisado_por="Revisor de prueba",
        estado=EstadoRevision.REVISADO,
    )


def zona(*parametros: Parametro) -> Zona:
    return Zona(
        codigo="Z-4",
        nombre="Z-4",
        comuna="Ñuñoa",
        parametros={p.clave: p for p in parametros},
        vigencia=Vigencia(),
        procedencia=procedencia(),
    )


def parametro_cos(base: str, excepcion: str, cuando: str) -> Parametro:
    """El `cos` de una zona, con una excepción condicionada a un hecho clasificado."""
    return Parametro(
        id="cos",
        limites=(
            Limite(TipoLimite.BASE, Decimal(base), "adimensional", CITA),
            Limite(TipoLimite.EXCEPCION, Decimal(excepcion), "adimensional", CITA,
            frozenset({cuando})),
        ),
        sentido=Sentido.MAXIMO,
        estado=EstadoParametro.APLICABLE,
        cita=CITA,
    )


def proyecto_cos_060() -> Proyecto:
    """1.000 m² de predio con 600 m² de primer piso: un `cos` de 0,6."""
    return Proyecto(
        superficie_predio_m2=Decimal("1000"),
        numero_viviendas=1,
        superficie_primer_piso_m2=Decimal("600"),
    )


def codigo_de(
    p: Proyecto, z: Zona, clave: str, externos: dict[str, bool | None]
) -> CodigoVeredicto:
    veredicto = next(v for v in evaluar(p, z, REGLAS, externos) if v.clave == clave)
    return veredicto.codigo


def noul(hecho: str) -> PreguntaDeHecho:
    return PreguntaDeHecho(
        hecho=hecho,
        pregunta=PreguntaNoul(id=hecho, instrucciones="¿Se acredita en el expediente?"),
        cita=CITA,
    )


def choice(hecho: str, verdadero_si: frozenset[str]) -> PreguntaDeHecho:
    return PreguntaDeHecho(
        hecho=hecho,
        pregunta=PreguntaChoice(
            id=hecho,
            instrucciones="Clasifique el destino principal.",
            criterios={"equipamiento": "de equipamiento", "vivienda": "residencial"},
        ),
        cita=CITA,
        verdadero_si=verdadero_si,
    )


# --- 1. sin documento no se pregunta ---


def test_sin_documento_no_se_consulta_al_proveedor() -> None:
    """No se gasta una consulta para que un modelo adivine sobre la nada."""
    proveedor = ProveedorGuionizado({"dimension_c": RespuestaNoul(probabilidad=0.99)})
    resultado = resolver_hechos({"dimension_c": noul("dimension_c")}, {}, proveedor)

    assert proveedor.llamadas == 0
    assert resultado.hechos["dimension_c"] is None
    assert resultado.pendientes == ("dimension_c",)


def test_un_estado_de_puros_espacios_es_un_documento_vacio() -> None:
    """Un PDF que se extrajo en blanco no es evidencia: es la ausencia de evidencia."""
    proveedor = ProveedorGuionizado({"dimension_c": RespuestaNoul(probabilidad=0.99)})
    resultado = resolver_hechos(
        {"dimension_c": noul("dimension_c")}, {"memoria": "   \n  "}, proveedor
    )

    assert proveedor.llamadas == 0
    assert resultado.hechos["dimension_c"] is None
    assert resultado.motivos()["dimension_c"] == MOTIVO_SIN_DOCUMENTO


def test_sin_preguntas_declaradas_no_hay_nada_que_resolver() -> None:
    proveedor = ProveedorGuionizado({})
    resultado = resolver_hechos({}, {"memoria": "texto"}, proveedor)

    assert resultado.hechos == {}
    assert resultado.pendientes == ()
    assert proveedor.llamadas == 0


# --- 2. lo que no se resuelve no se inventa ---


def test_un_noul_sobre_el_umbral_vuelve_cierto_el_hecho() -> None:
    proveedor = ProveedorGuionizado({"dimension_c": RespuestaNoul(probabilidad=0.93)})
    resultado = resolver_hechos({"dimension_c": noul("dimension_c")}, {"m": "x"}, proveedor)

    assert resultado.hechos["dimension_c"] is True
    assert resultado.pendientes == ()


def test_un_noul_bajo_el_piso_vuelve_falso_el_hecho() -> None:
    proveedor = ProveedorGuionizado({"dimension_c": RespuestaNoul(probabilidad=0.04)})
    resultado = resolver_hechos({"dimension_c": noul("dimension_c")}, {"m": "x"}, proveedor)

    assert resultado.hechos["dimension_c"] is False


def test_la_banda_gris_deja_el_hecho_sin_resolver() -> None:
    """0,5 no es ni sí ni no. Redondearlo sería exactamente lo que el proyecto no hace."""
    proveedor = ProveedorGuionizado({"dimension_c": RespuestaNoul(probabilidad=0.5)})
    resultado = resolver_hechos({"dimension_c": noul("dimension_c")}, {"m": "x"}, proveedor)

    assert resultado.hechos["dimension_c"] is None
    assert resultado.pendientes == ("dimension_c",)
    assert "banda gris" in resultado.motivos()["dimension_c"]


def test_una_eleccion_de_baja_confianza_no_se_resuelve() -> None:
    proveedor = ProveedorGuionizado(
        {
            "condicion_uso": RespuestaChoice(
                eleccion="equipamiento", confianza=0.55, probabilidades={"equipamiento": 0.55}
            )
        }
    )
    resultado = resolver_hechos(
        {"condicion_uso": choice("condicion_uso", frozenset({"equipamiento"}))},
        {"m": "x"},
        proveedor,
    )

    assert resultado.hechos["condicion_uso"] is None
    assert "umbral" in resultado.motivos()["condicion_uso"]


def test_un_hecho_que_el_proveedor_no_respondio_queda_pendiente() -> None:
    proveedor = ProveedorGuionizado({})
    resultado = resolver_hechos({"dimension_b": noul("dimension_b")}, {"m": "x"}, proveedor)

    assert resultado.hechos["dimension_b"] is None
    assert resultado.motivos()["dimension_b"]


# --- 3. una respuesta categórica no se redondea ---


def test_la_eleccion_declarada_como_verdadera_vuelve_cierto_el_hecho() -> None:
    proveedor = ProveedorGuionizado(
        {
            "condicion_uso": RespuestaChoice(
                eleccion="equipamiento", confianza=0.9, probabilidades={"equipamiento": 0.9}
            )
        }
    )
    resultado = resolver_hechos(
        {"condicion_uso": choice("condicion_uso", frozenset({"equipamiento"}))},
        {"m": "x"},
        proveedor,
    )

    assert resultado.hechos["condicion_uso"] is True


def test_una_eleccion_no_declarada_vuelve_falso_el_hecho() -> None:
    """La otra opción se resuelve, pero **no** vuelve cierto el hecho."""
    proveedor = ProveedorGuionizado(
        {"condicion_uso": RespuestaChoice(eleccion="vivienda", confianza=0.9, probabilidades={})}
    )
    resultado = resolver_hechos(
        {"condicion_uso": choice("condicion_uso", frozenset({"equipamiento"}))},
        {"m": "x"},
        proveedor,
    )

    assert resultado.hechos["condicion_uso"] is False


def test_la_eleccion_no_depende_de_la_opcion_mas_probable_sino_de_la_elegida() -> None:
    """Resolver el hecho por `probabilidades` sería inventar: manda la elección del proveedor."""
    proveedor = ProveedorGuionizado(
        {
            "condicion_uso": RespuestaChoice(
                eleccion="vivienda",
                confianza=0.9,
                probabilidades={"equipamiento": 0.55, "vivienda": 0.45},
            )
        }
    )
    resultado = resolver_hechos(
        {"condicion_uso": choice("condicion_uso", frozenset({"equipamiento"}))},
        {"m": "x"},
        proveedor,
    )

    assert resultado.hechos["condicion_uso"] is False


def test_el_orden_de_las_preguntas_no_depende_del_diccionario() -> None:
    """Dos corridas sobre el mismo expediente deben mandar exactamente lo mismo."""
    vistas: list[list[str]] = []

    class Espia(ProveedorGuionizado):
        def responder(self, estado, preguntas):  # type: ignore[no-untyped-def]
            vistas.append([p.id for p in preguntas])
            return super().responder(estado, preguntas)

    declaradas = {
        "dimension_c": noul("dimension_c"),
        "condicion_uso": choice("condicion_uso", frozenset({"equipamiento"})),
        "dimension_b": noul("dimension_b"),
    }
    resolver_hechos(declaradas, {"m": "x"}, Espia({}))
    resolver_hechos(dict(reversed(list(declaradas.items()))), {"m": "x"}, Espia({}))

    assert vistas[0] == vistas[1] == ["condicion_uso", "dimension_b", "dimension_c"]


# --- 4. el circuito completo: el hecho externo cambia el veredicto ---


def test_un_hecho_externo_cierto_aplica_la_excepcion() -> None:
    """0,6 de `cos` no cumple el base de 0,5, pero sí la excepción de 0,8."""
    z = zona(parametro_cos("0.5", "0.8", "dimension_c"))
    assert codigo_de(proyecto_cos_060(), z, "cos", {"dimension_c": True}) is (
        CodigoVeredicto.CUMPLE
    )


def test_un_hecho_externo_falso_deja_el_base() -> None:
    z = zona(parametro_cos("0.5", "0.8", "dimension_c"))
    assert codigo_de(proyecto_cos_060(), z, "cos", {"dimension_c": False}) is (
        CodigoVeredicto.NO_CUMPLE
    )


def test_un_hecho_externo_indeterminado_no_aplica_lo_permisivo() -> None:
    """Es el test que sostiene todo: sin la fusión no se aplica el +30 %, ni se rechaza."""
    z = zona(parametro_cos("0.5", "0.8", "dimension_c"))
    assert codigo_de(proyecto_cos_060(), z, "cos", {"dimension_c": None}) is (
        CodigoVeredicto.PENDIENTE
    )


def test_sin_hecho_externo_el_limite_condicional_tampoco_se_asume() -> None:
    z = zona(parametro_cos("0.5", "0.8", "dimension_c"))
    assert codigo_de(proyecto_cos_060(), z, "cos", {}) is CodigoVeredicto.PENDIENTE


def test_el_motor_no_deja_que_un_hecho_externo_sobrescriba_al_corpus() -> None:
    """`dimension_a` lo calcula el corpus: dos fuentes para un hecho dejan el veredicto al azar."""
    z = zona(parametro_cos("0.5", "0.8", "dimension_a"))
    with pytest.raises(ErrorDominio, match="dimension_a"):
        evaluar(proyecto_cos_060(), z, REGLAS, {"dimension_a": True})


def test_el_puente_y_el_motor_resuelven_los_hechos_de_punta_a_punta() -> None:
    """Del texto del expediente al veredicto, sin que nadie toque el booleano a mano."""
    proveedor = ProveedorGuionizado({"dimension_c": RespuestaNoul(probabilidad=0.95)})
    declaradas = cargar_preguntas(RAIZ / "corpus")
    resultado = resolver_hechos(
        {"dimension_c": declaradas["dimension_c"]},
        {"memoria": "El plano de loteo acredita la fusión predial del art. 63."},
        proveedor,
    )
    z = zona(parametro_cos("0.5", "0.8", "dimension_c"))

    veredicto = next(
        v for v in evaluar(proyecto_cos_060(), z, REGLAS, resultado.hechos) if v.clave == "cos"
    )

    assert veredicto.codigo is CodigoVeredicto.CUMPLE
    assert veredicto.valor_norma == Decimal("0.8")


# --- 5. el contrato de una pregunta de hecho ---


def noul_con(verdadero_si: frozenset[str]) -> PreguntaDeHecho:
    return PreguntaDeHecho(
        hecho="dimension_c",
        pregunta=PreguntaNoul(id="dimension_c", instrucciones="¿x?"),
        cita=CITA,
        verdadero_si=verdadero_si,
    )


def test_una_pregunta_noul_no_lleva_verdadero_si() -> None:
    with pytest.raises(ErrorClasificacion, match="booleano"):
        noul_con(frozenset({"si"}))


def test_una_pregunta_categorica_exige_verdadero_si() -> None:
    """Sin él no hay forma de saber qué respuesta vuelve cierto el hecho."""
    with pytest.raises(ErrorClasificacion, match="verdadero_si"):
        PreguntaDeHecho(
            hecho="condicion_uso",
            pregunta=PreguntaChoice(
                id="condicion_uso", instrucciones="¿x?", criterios={"a": "A", "b": "B"}
            ),
            cita=CITA,
        )


def test_verdadero_si_no_puede_nombrar_valores_que_la_pregunta_no_ofrece() -> None:
    with pytest.raises(ErrorClasificacion, match="no ofrece"):
        choice("condicion_uso", frozenset({"industrial"}))


def test_el_id_de_la_pregunta_tiene_que_ser_el_nombre_del_hecho() -> None:
    """Si no coinciden, el motor no sabría a qué hecho corresponde la respuesta."""
    with pytest.raises(ErrorClasificacion, match="coincidir"):
        PreguntaDeHecho(
            hecho="dimension_c",
            pregunta=PreguntaScore(
                id="otra_cosa", instrucciones="¿x?", niveles=("bajo", "alto")
            ),
            cita=CITA,
            verdadero_si=frozenset({"alto"}),
        )


# --- 6. el esquema del corpus ---


def documento(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "norma_id": "oguc",
        "articulo": "2.6.4",
        "cita": "texto de la norma",
        "procedencia": {
            "url_fuente": "https://x.cl/o.pdf",
            "hash_fuente": "sha256:" + "0" * 64,
            "consolidado_por": "refundido",
            "extraido": "2026-09-26",
        },
    }
    base.update(extra)
    return base


def pregunta_noul_yaml() -> dict[str, object]:
    return {
        "tipo": "noul",
        "instrucciones": "¿Constituye una manzana existente?",
        "cita": {"norma_id": "oguc", "articulo": "2.6.4"},
    }


def escribir(tmp_path: Path, nombre: str, datos: dict[str, object]) -> None:
    import yaml

    (tmp_path / nombre).write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")


def test_el_esquema_rechaza_una_pregunta_sin_cita() -> None:
    sin_cita = pregunta_noul_yaml()
    del sin_cita["cita"]
    with pytest.raises(ErrorEsquema, match="cita"):
        validar_documento(
            documento(
                hechos_pendientes={"dimension_c": "exige historial registral"},
                preguntas={"dimension_c": sin_cita},
            )
        )


def test_el_esquema_rechaza_un_tipo_de_pregunta_desconocido() -> None:
    with pytest.raises(ErrorEsquema, match="tipo"):
        validar_documento(
            documento(
                hechos_pendientes={"dimension_c": "exige historial registral"},
                preguntas={"dimension_c": {**pregunta_noul_yaml(), "tipo": "libre"}},
            )
        )


def test_el_esquema_rechaza_un_pendiente_sin_nota() -> None:
    """La nota es lo que justifica por qué el hecho no se calcula en el corpus."""
    with pytest.raises(ErrorEsquema, match="nota"):
        validar_documento(documento(hechos_pendientes={"dimension_c": "  "}))


def test_el_esquema_rechaza_un_choice_sin_definiciones() -> None:
    with pytest.raises(ErrorEsquema, match="definici"):
        validar_documento(
            documento(
                hechos_pendientes={"condicion_uso": "requiere el destino"},
                preguntas={
                    "condicion_uso": {
                        "tipo": "choice",
                        "instrucciones": "Clasifique el destino.",
                        "criterios": {"equipamiento": "  ", "vivienda": "residencial"},
                        "verdadero_si": ["equipamiento"],
                        "cita": {"norma_id": "oguc", "articulo": "2.6.4"},
                    }
                },
            )
        )


def test_el_esquema_rechaza_un_verdadero_si_que_nombra_lo_que_no_se_ofrece() -> None:
    with pytest.raises(ErrorEsquema, match="verdadero_si"):
        validar_documento(
            documento(
                hechos_pendientes={"condicion_uso": "requiere el destino"},
                preguntas={
                    "condicion_uso": {
                        "tipo": "choice",
                        "instrucciones": "Clasifique el destino.",
                        "criterios": {"equipamiento": "eq", "vivienda": "viv"},
                        "verdadero_si": ["industrial"],
                        "cita": {"norma_id": "oguc", "articulo": "2.6.4"},
                    }
                },
            )
        )


def test_una_pregunta_sobre_un_hecho_ya_calculable_es_un_error(tmp_path: Path) -> None:
    """Dos fuentes para un mismo hecho: cuál gana sería una decisión implícita."""
    escribir(
        tmp_path,
        "a.yaml",
        documento(
            hechos={
                "dimension_a": {
                    "expresion": "numero_pisos >= 1",
                    "cita": {"norma_id": "oguc"},
                }
            },
            hechos_pendientes={"dimension_a": "nota"},
            preguntas={"dimension_a": pregunta_noul_yaml()},
        ),
    )
    with pytest.raises(ErrorEsquema, match="preguntados"):
        validar_corpus(tmp_path)


def test_una_pregunta_sin_pendiente_que_la_justifique_es_un_error(tmp_path: Path) -> None:
    escribir(tmp_path, "a.yaml", documento(preguntas={"dimension_c": pregunta_noul_yaml()}))
    with pytest.raises(ErrorEsquema, match="hechos_pendientes"):
        validar_corpus(tmp_path)


def test_un_cuando_puede_apoyarse_en_un_hecho_preguntado(tmp_path: Path) -> None:
    """Es el caso de uso: el límite condicional depende de un hecho que el corpus no calcula."""
    escribir(
        tmp_path,
        "a.yaml",
        documento(
            hechos_pendientes={"dimension_c": "exige historial registral"},
            preguntas={"dimension_c": pregunta_noul_yaml()},
        ),
    )
    escribir(
        tmp_path,
        "zona.yaml",
        {
            "norma_id": "prc:nunoa",
            "zona": "Z-4",
            "cita": "ordenanza local",
            "parametros": {
                "cus": {
                    "id": "cus",
                    "sentido": "maximo",
                    "limites": [
                        {
                            "tipo": "base",
                            "valor": "4",
                            "cita": {"norma_id": "prc:nunoa", "articulo": "Z-4"},
                        },
                        {
                            "tipo": "excepcion",
                            "valor": "6",
                            "cuando": ["dimension_c"],
                            "cita": {"norma_id": "prc:nunoa", "articulo": "Z-4"},
                        },
                    ],
                }
            },
            "procedencia": {
                "url_fuente": "https://x.cl/o.pdf",
                "hash_fuente": "sha256:" + "0" * 64,
                "consolidado_por": "refundido",
                "extraido": "2026-09-26",
            },
        },
    )
    assert len(validar_corpus(tmp_path)) == 2


# --- 7. el corpus real ---


def test_el_corpus_real_declara_una_pregunta_por_cada_hecho_pendiente() -> None:
    """`2.6.4` tiene tres hechos que no puede calcular, y los tres tienen su pregunta."""
    declaradas = cargar_preguntas(RAIZ / "corpus")
    assert sorted(declaradas) == ["condicion_uso", "dimension_b", "dimension_c"]
    for hecho, declarada in declaradas.items():
        assert declarada.hecho == hecho
        assert declarada.cita.articulo == "2.6.4"


def test_el_corpus_real_no_pregunta_nada_que_ya_sepa_calcular() -> None:
    declaradas = cargar_preguntas(RAIZ / "corpus")
    assert "dimension_a" not in declaradas
    assert "dimension_a" in REGLAS.hechos


def test_toda_pregunta_del_corpus_real_tiene_su_cita_con_texto() -> None:
    for declarada in cargar_preguntas(RAIZ / "corpus").values():
        assert declarada.cita.texto.strip()
