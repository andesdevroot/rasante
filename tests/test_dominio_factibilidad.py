"""Tests del verificador de factibilidad (T1.5).

D15: los parámetros están **acoplados geométricamente**, y el motor los evalúa aislados. La
consecuencia es un informe que aprueba algo que no se puede construir:

    cos = 0,5 y cus = 3,2 sobre 1.000 m² con 5 pisos
    → 5 pisos de 500 m² de huella caben 2.500 m², no 3.200 m²
    → cos, cus y altura dan `C` cada uno por separado
    → el proyecto es imposible igual

Se verifican dos cosas **distintas**, y las dos salen citadas:

1. **Consistencia del conjunto normativo**: ¿existe algún proyecto que satisfaga todos los
   límites de la zona a la vez? Si el `cus` normado excede lo que permiten `cos`, el `cos` de pisos
   superiores y la altura, esa norma es inalcanzable.
2. **Factibilidad del proyecto declarado**: ¿lo que declara es geométricamente posible?

**Límite conocido:** el dominio todavía guarda **un** valor por parámetro, así que la
verificación del conjunto normativo usa ese valor y no la lista de límites simultáneos que el
esquema de T1.3 ya admite. El chequeo del proyecto —el que importa— no depende de eso.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from rasante.corpus.cargador import cargar_reglas
from rasante.dominio.factibilidad import verificar
from rasante.dominio.modelos import (
    Cita,
    CodigoHallazgo,
    EstadoParametro,
    EstadoRevision,
    Hallazgo,
    Limite,
    Parametro,
    Procedencia,
    Proyecto,
    Sentido,
    Severidad,
    TipoLimite,
    Vigencia,
    Zona,
)
from rasante.dominio.reglas import Reglas

RAIZ = Path(__file__).resolve().parents[1]
REGLAS: Reglas = cargar_reglas(RAIZ / "corpus")

CITA = Cita(norma_id="oguc", articulo="1.1.2", texto="definiciones de los coeficientes")


def procedencia() -> Procedencia:
    return Procedencia(
        url_fuente="https://www.nunoa.cl/ordenanza.pdf",
        hash_fuente="sha256:" + "0" * 64,
        consolidado_por="Texto refundido, junio 2025",
        extraido="2026-09-26", revisado_por="Revisor de prueba",
        estado=EstadoRevision.REVISADO,
    )


def parametro(
    id_: str, valor: str, calificador: str | None = None, unidad: str = "adimensional"
) -> Parametro:
    return Parametro(
        id=id_,
        limites=(Limite(TipoLimite.BASE, Decimal(valor), unidad, CITA),),
        sentido=Sentido.MAXIMO,
        estado=EstadoParametro.APLICABLE,
        cita=CITA,
        calificador=calificador,
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


ZONA_TIPICA = zona(
    parametro("cos", "0.6", "primer_piso"),
    parametro("cos", "0.4", "pisos_superiores"),
    parametro("cus", "4"),
    parametro("altura_maxima", "44", unidad="m"),
)


def proyecto(**campos: object) -> Proyecto:
    base: dict[str, object] = {"superficie_predio_m2": Decimal("1000"), "numero_viviendas": 10}
    base.update(campos)
    return Proyecto(**base)  # type: ignore[arg-type]


def codigos(hallazgos: list[Hallazgo]) -> set[CodigoHallazgo]:
    return {h.codigo for h in hallazgos}


# --- 1. Factibilidad del proyecto: la aceptación ---


def test_un_proyecto_coherente_no_produce_hallazgos() -> None:
    """500 m² de huella, 5 pisos: caben 2.500 m². Declara 2.400. Coherente."""
    coherente = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("2400"),
        numero_pisos=5,
    )
    assert verificar(coherente, ZONA_TIPICA, REGLAS) == []


def test_el_caso_de_aceptacion_todos_cumplen_pero_el_proyecto_es_imposible() -> None:
    """Criterio de aceptación de T1.5: cada parámetro da `C`, y el proyecto no se puede construir.

    500 m² de huella por 5 pisos son 2.500 m² como máximo. Declara 3.200 m².
    """
    imposible = proyecto(
        superficie_primer_piso_m2=Decimal("500"),   # cos = 0,5  <= 0,6  -> C
        superficie_edificada_m2=Decimal("3200"),    # cus = 3,2  <= 4    -> C
        numero_pisos=5,
        altura_m=Decimal("20"),                     # 20 <= 44           -> C
    )
    hallazgos = verificar(imposible, ZONA_TIPICA, REGLAS)
    assert CodigoHallazgo.PROYECTO_IMPOSIBLE in codigos(hallazgos)


def test_el_hallazgo_del_proyecto_es_bloqueante() -> None:
    """No es una advertencia: ese proyecto no existe."""
    imposible = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("3200"),
        numero_pisos=5,
    )
    hallazgo = next(h for h in verificar(imposible, ZONA_TIPICA, REGLAS))
    assert hallazgo.severidad is Severidad.BLOQUEANTE


def test_justo_en_el_limite_geometrico_es_coherente() -> None:
    """5 pisos de 500 m² caben exactamente 2.500 m². No es imposible."""
    al_limite = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("2500"),
        numero_pisos=5,
    )
    assert verificar(al_limite, ZONA_TIPICA, REGLAS) == []


def test_sin_numero_de_pisos_no_se_afirma_nada() -> None:
    """Si no sabemos cuántos pisos tiene, no podemos decir que sea imposible."""
    sin_pisos = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("9999"),
    )
    assert verificar(sin_pisos, ZONA_TIPICA, REGLAS) == []


def test_sin_superficies_declaradas_no_se_afirma_nada() -> None:
    assert verificar(proyecto(numero_pisos=5), ZONA_TIPICA, REGLAS) == []


def test_un_proyecto_de_un_piso_no_puede_edificar_mas_que_su_huella() -> None:
    """Con un piso, la superficie edificada no puede exceder la del primer piso."""
    un_piso = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("600"),
        numero_pisos=1,
    )
    assert CodigoHallazgo.PROYECTO_IMPOSIBLE in codigos(verificar(un_piso, ZONA_TIPICA, REGLAS))


# --- 2. Consistencia del conjunto normativo ---


def test_una_norma_alcanzable_no_produce_hallazgos() -> None:
    """cos 0,6 + 11 pisos superiores de 0,4 = 5,0 de cus máximo. El cus normado es 4: alcanzable."""
    assert verificar(proyecto(), ZONA_TIPICA, REGLAS) == []


def test_un_cus_normado_inalcanzable_se_detecta() -> None:
    """Con cos 0,6 y 0,4 a 44 m (12 pisos de 3,50) el cus máximo es 5,0: normar 7 no se alcanza."""
    inalcanzable = zona(
        parametro("cos", "0.6", "primer_piso"),
        parametro("cos", "0.4", "pisos_superiores"),
        parametro("cus", "7"),
        parametro("altura_maxima", "44", unidad="m"),
    )
    hallazgos = verificar(proyecto(), inalcanzable, REGLAS)
    assert CodigoHallazgo.CUS_INALCANZABLE in codigos(hallazgos)


def test_el_hallazgo_de_la_norma_no_es_bloqueante_del_proyecto() -> None:
    """Una norma inalcanzable puede ser un error del corpus o algo real: se advierte."""
    inalcanzable = zona(
        parametro("cos", "0.6", "primer_piso"),
        parametro("cos", "0.4", "pisos_superiores"),
        parametro("cus", "7"),
        parametro("altura_maxima", "44", unidad="m"),
    )
    hallazgo = verificar(proyecto(), inalcanzable, REGLAS)[0]
    assert hallazgo.severidad is Severidad.ADVERTENCIA


def test_sin_altura_ni_pisos_no_se_puede_juzgar_la_norma() -> None:
    """Sin saber cuántos pisos permite la norma, no se puede calcular el cus máximo."""
    solo_cus = zona(parametro("cus", "7"))
    assert CodigoHallazgo.CUS_INALCANZABLE not in codigos(
        verificar(proyecto(), solo_cus, REGLAS)
    )


# --- contrato de la salida ---


def test_todo_hallazgo_trae_cita() -> None:
    imposible = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("3200"),
        numero_pisos=5,
    )
    inalcanzable = zona(
        parametro("cos", "0.6", "primer_piso"),
        parametro("cos", "0.4", "pisos_superiores"),
        parametro("cus", "7"),
        parametro("altura_maxima", "44", unidad="m"),
    )
    hallazgos = verificar(imposible, inalcanzable, REGLAS)
    assert hallazgos
    for hallazgo in hallazgos:
        assert isinstance(hallazgo.cita, Cita)
        assert hallazgo.cita.texto


def test_el_hallazgo_nombra_los_parametros_involucrados() -> None:
    imposible = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("3200"),
        numero_pisos=5,
    )
    hallazgo = next(h for h in verificar(imposible, ZONA_TIPICA, REGLAS))
    assert "cus" in hallazgo.parametros
    assert "cos.primer_piso" in hallazgo.parametros


def test_el_mensaje_dice_por_que() -> None:
    imposible = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("3200"),
        numero_pisos=5,
    )
    hallazgo = next(h for h in verificar(imposible, ZONA_TIPICA, REGLAS))
    assert "2500" in hallazgo.mensaje, "el mensaje debe decir cuánto cabe"
    assert "3200" in hallazgo.mensaje, "y cuánto declara"


def test_un_hallazgo_sin_cita_no_se_puede_construir() -> None:
    with pytest.raises(TypeError):
        Hallazgo(  # type: ignore[call-arg]
            codigo=CodigoHallazgo.PROYECTO_IMPOSIBLE,
            severidad=Severidad.BLOQUEANTE,
            mensaje="x",
            parametros=(),
        )


def test_los_hallazgos_son_inmutables() -> None:
    imposible = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("3200"),
        numero_pisos=5,
    )
    hallazgo = next(h for h in verificar(imposible, ZONA_TIPICA, REGLAS))
    with pytest.raises(FrozenInstanceError):
        hallazgo.mensaje = "otro"  # type: ignore[misc]


def test_verificar_no_muta_nada() -> None:
    z = ZONA_TIPICA
    p = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("3200"),
        numero_pisos=5,
    )
    antes = (len(z.parametros), p.superficie_edificada_m2)
    verificar(p, z, REGLAS)
    assert (len(z.parametros), p.superficie_edificada_m2) == antes


def test_una_zona_sin_parametros_no_produce_hallazgos() -> None:
    assert verificar(proyecto(), zona(), REGLAS) == []


def test_sin_cita_no_se_emite_hallazgo() -> None:
    """Un hallazgo sin respaldo normativo es una opinión. Sin cita, no se afirma.

    El acoplamiento geométrico se respalda con la relación del corpus; si el corpus no la trae y la
    zona tampoco declara el parámetro, no hay nada que citar.
    """
    sin_relaciones = Reglas(derivaciones=REGLAS.derivaciones, relaciones=())
    zona_sin_cus = zona(
        parametro("cos", "0.6", "primer_piso"),
        parametro("altura_maxima", "44", unidad="m"),
    )
    imposible = proyecto(
        superficie_primer_piso_m2=Decimal("500"),
        superficie_edificada_m2=Decimal("3200"),
        numero_pisos=5,
    )
    assert verificar(imposible, zona_sin_cus, sin_relaciones) == []
