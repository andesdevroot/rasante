"""Lo que el motor expone sobre sí mismo: caché, diagnóstico y orden documentado (T1, T3, T4).

Los cuatro cambios de esta tanda comparten una propiedad: **no pueden alterar un veredicto**. La
caché es memoización de una función pura, `procedencia` es diagnóstico, y el orden de `_decidir` ya
estaba bien y solo se documenta. Estos tests fijan esa propiedad, no la suponen.
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from rasante.corpus.cargador import cargar_reglas
from rasante.dominio import motor
from rasante.dominio.modelos import (
    Cita,
    EstadoRevision,
    Procedencia,
    Proyecto,
    Vigencia,
    Zona,
)
from rasante.dominio.reglas import Hecho, ProcedenciaHecho, Reglas
from rasante.dominio.vocabulario import ErrorVocabulario, arbol

RAIZ = Path(__file__).resolve().parents[1]
REGLAS_REALES = cargar_reglas(RAIZ / "corpus")
CITA = Cita(norma_id="oguc", articulo="1.1.2", texto="definiciones")


def reglas(hechos: dict[str, str]) -> Reglas:
    return Reglas(
        derivaciones=MappingProxyType({}),
        hechos=MappingProxyType(
            {n: Hecho(nombre=n, expresion=e, cita=CITA) for n, e in hechos.items()}
        ),
    )


def zona() -> Zona:
    return Zona(
        codigo="Z-4",
        nombre="Z-4",
        comuna="Ñuñoa",
        parametros={},
        vigencia=Vigencia(),
        procedencia=Procedencia(
            url_fuente="https://x.cl/o.pdf",
            hash_fuente="sha256:" + "0" * 64,
            consolidado_por="refundido",
            extraido="2026-09-26",
        ),
    )


def proyecto(**extra: object) -> Proyecto:
    base: dict[str, object] = {"superficie_predio_m2": Decimal("600"), "numero_viviendas": 10}
    base.update(extra)
    return Proyecto(**base)  # type: ignore[arg-type]


# --- T1: la caché de árboles sintácticos ---


def test_arbol_memoiza_la_misma_expresion() -> None:
    """Se paga `ast.parse` **y** la lista blanca una sola vez por expresión."""
    arbol.cache_clear()
    arbol("superficie_predio_m2 >= 500")
    arbol("superficie_predio_m2 >= 500")
    arbol("superficie_predio_m2 >= 500")
    assert arbol.cache_info().misses == 1
    assert arbol.cache_info().hits == 2


def test_la_cache_esta_acotada() -> None:
    """Un `dict` que crece con cada expresión vista es una fuga en un proceso de vida larga."""
    maxsize = arbol.cache_info().maxsize
    assert maxsize is not None
    assert maxsize > 0


def test_una_expresion_invalida_no_envenena_la_cache() -> None:
    """`lru_cache` no memoriza excepciones, así que el error se repite en vez de quedar pegado."""
    for _ in range(2):
        try:
            arbol("__import__('os')")
        except ErrorVocabulario:
            continue
        raise AssertionError("una expresión fuera de la lista blanca debe fallar")


def test_el_arbol_devuelto_es_compartido() -> None:
    """La caché devuelve **el mismo objeto**, que nadie debe mutar.

    No es un detalle: mutarlo envenenaría todas las evaluaciones siguientes. Se documenta acá porque
    el tipo no puede impedirlo, y este test lo deja escrito para que un cambio futuro lo vea.
    """
    assert arbol("numero_pisos") is arbol("numero_pisos")


def test_la_cache_no_cambia_ningun_veredicto() -> None:
    """La prueba de que es memoización y no otra cosa: dos corridas, el mismo resultado."""
    z = _zona_real_firmada()
    p = _proyecto_real()
    externos = {"dimension_b": False, "dimension_c": False}
    primera = [(v.clave, v.codigo) for v in motor.evaluar(p, z, REGLAS_REALES, externos)]
    segunda = [(v.clave, v.codigo) for v in motor.evaluar(p, z, REGLAS_REALES, externos)]
    assert primera == segunda
    assert len(primera) == len(z.parametros)


# --- T3: por qué un hecho quedó en None ---


def test_un_dato_faltante_se_registra_como_tal() -> None:
    """El proyecto no declara `altura_m`: falta el dato, y el arreglo es conseguirlo."""
    c = motor.clasificar(proyecto(), zona(), reglas({"alto": "altura_m >= 15"}))
    assert c.hechos["alto"] is None
    assert c.procedencia_de("alto") is ProcedenciaHecho.DATO_FALTANTE


def test_una_division_por_cero_es_otra_causa() -> None:
    """Todos los nombres están y aun así no dio número. El arreglo es el corpus, no los datos."""
    c = motor.clasificar(
        proyecto(), zona(), reglas({"raro": "numero_viviendas / (superficie_predio_m2 - 600) > 1"})
    )
    assert c.hechos["raro"] is None
    assert c.procedencia_de("raro") is ProcedenciaHecho.EXPRESION_NO_CALCULABLE


def test_un_hecho_externo_indeterminado_se_distingue() -> None:
    c = motor.clasificar(proyecto(), zona(), reglas({}), hechos_externos={"dimension_c": None})
    assert c.hechos["dimension_c"] is None
    assert c.procedencia_de("dimension_c") is ProcedenciaHecho.EXTERNO_INDETERMINADO


def test_un_hecho_que_nadie_declaro_se_responde_por_ausencia() -> None:
    """Tres estados, no dos: "se sabe", "no se sabe y por esto", y "nadie lo declaró"."""
    c = motor.clasificar(proyecto(), zona(), reglas({"alto": "altura_m >= 15"}))
    assert c.procedencia_de("inventado") is ProcedenciaHecho.HECHO_NO_DECLARADO


def test_un_hecho_determinado_no_tiene_procedencia() -> None:
    """Ausencia en `procedencia` significa que se determinó, no que se olvidó registrarlo."""
    c = motor.clasificar(proyecto(), zona(), reglas({"chico": "superficie_predio_m2 <= 1000"}))
    assert c.hechos["chico"] is True
    assert c.procedencia_de("chico") is None


def test_solo_los_indeterminados_traen_procedencia() -> None:
    c = motor.clasificar(
        proyecto(),
        zona(),
        reglas({"chico": "superficie_predio_m2 <= 1000", "alto": "altura_m >= 15"}),
    )
    assert dict(c.procedencia) == {"alto": ProcedenciaHecho.DATO_FALTANTE}


def test_la_procedencia_no_cambia_el_veredicto() -> None:
    """Lo que sostiene todo: un `None` es `None` venga de donde venga, y da `P`.

    Se comprueba **por hecho** y no sobre el mapping entero: `aplica(frozenset())` es `True` por
    vacuidad, así que un caso sin hechos pasaría el test sin probar nada.
    """
    casos = [
        ({"alto": "altura_m >= 15"}, {}, "alto"),
        ({"raro": "numero_viviendas / (superficie_predio_m2 - 600) > 1"}, {}, "raro"),
        ({}, {"dimension_c": None}, "dimension_c"),
    ]
    for hechos, externos, nombre in casos:
        c = motor.clasificar(proyecto(), zona(), reglas(hechos), hechos_externos=externos)
        assert c.hechos[nombre] is None, nombre
        assert c.aplica(frozenset({nombre})) is None, nombre
        assert c.indeterminados(frozenset({nombre})) == (nombre,), nombre


def test_decidir_no_lee_la_procedencia() -> None:
    """El invariante que impide que el diagnóstico empiece a decidir.

    Es una comprobación sobre el código fuente, como la que ya verifica que el intérprete no usa
    `eval`: si `_decidir` nombrara `procedencia`, un campo de diagnóstico estaría influyendo en el
    veredicto, y el invariante "un `None` da `P`" dejaría de ser cierto por construcción.
    """
    fuente = inspect.getsource(motor._decidir)
    cuerpo = fuente.split('"""')[2] if fuente.count('"""') >= 2 else fuente
    assert "procedencia" not in cuerpo
    assert "Procedencia" not in cuerpo


# --- T4: el orden de verificación, documentado ---


def test_el_orden_de_verificacion_esta_documentado() -> None:
    """T4 no aporta código: aporta el porqué, que es lo que se audita desde fuera.

    Se comprueba que el docstring enumere los pasos **y** que diga lo que los hace seguros: que
    ninguno compara hasta el final.
    """
    doc = motor._decidir.__doc__ or ""
    for paso in ("fuente_revisada", "NO_APLICA", "indeterminados", "valor_proyecto", "MAXIMO"):
        assert paso in doc, f"el orden documentado no menciona {paso}"
    assert "solo pueden devolver `P`" in doc
    assert "D18" in doc and "D16" in doc and "D20" in doc


def test_ninguna_comparacion_ocurre_antes_del_ultimo_paso() -> None:
    """El orden documentado se corresponde con el código: los `P` salen antes de comparar."""
    fuente = inspect.getsource(motor._decidir)
    cuerpo = fuente.split('"""')[2] if fuente.count('"""') >= 2 else fuente
    posicion_cumple = cuerpo.index("CUMPLE")
    for salida_previa in ("PENDIENTE", "NO_PROCEDE"):
        assert cuerpo.index(salida_previa) < posicion_cumple


# --- utilidades ---


def _zona_real_firmada() -> Zona:
    from dataclasses import replace

    from rasante.corpus.cargador import cargar_zona

    z = cargar_zona(RAIZ / "corpus" / "prc" / "RM" / "nunoa" / "zonas" / "Z-2.yaml")
    return replace(
        z,
        procedencia=Procedencia(
            url_fuente=z.procedencia.url_fuente,
            hash_fuente=z.procedencia.hash_fuente,
            consolidado_por=z.procedencia.consolidado_por,
            extraido=z.procedencia.extraido,
            revisado_por="Revisor de prueba",
            estado=EstadoRevision.REVISADO,
        ),
    )


def _proyecto_real() -> Proyecto:
    return Proyecto(
        superficie_predio_m2=Decimal("600"),
        numero_viviendas=20,
        superficie_primer_piso_m2=Decimal("300"),
        superficie_edificada_m2=Decimal("900"),
        altura_m=Decimal("20"),
        numero_pisos=8,
    )
