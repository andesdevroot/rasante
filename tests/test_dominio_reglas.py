"""Tests del intérprete de reglas del corpus (T1.4).

D14 se cierra acá: el motor deja de tener su tabla hardcodeada y calcula con lo que **el corpus
dice**. El intérprete evalúa expresiones del vocabulario cerrado (`dominio/vocabulario.py`) usando
`ast`, **nunca `eval`**.

El corpus es dato que llega de fuera — eventualmente PRs de la comunidad. Un YAML malicioso no debe
poder ejecutar nada, y lo peor que puede provocar es que un veredicto salga `P`.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from rasante.corpus.cargador import cargar_reglas
from rasante.dominio.modelos import Cita
from rasante.dominio.reglas import Derivacion, Reglas, evaluar_expresion
from rasante.dominio.vocabulario import ErrorVocabulario

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "rasante"

VALORES: dict[str, Decimal | None] = {
    "superficie_predio_m2": Decimal("1000"),
    "superficie_primer_piso_m2": Decimal("600"),
    "superficie_edificada_m2": Decimal("3000"),
    "numero_pisos": Decimal("7"),
    "numero_viviendas": Decimal("10"),
    "altura_m": Decimal("24.5"),
}


# --- aritmética ---


def test_evalua_una_division() -> None:
    assert evaluar_expresion("superficie_edificada_m2 / superficie_predio_m2", VALORES) == Decimal(
        "3"
    )


def test_evalua_sumas_restas_y_productos() -> None:
    assert evaluar_expresion("numero_pisos + 1 - 2", VALORES) == Decimal("6")
    assert evaluar_expresion("numero_pisos * 2", VALORES) == Decimal("14")


def test_evalua_la_relacion_geometrica_real() -> None:
    """`cos.primer_piso + (numero_pisos - 1) * cos.pisos_superiores` con 7 pisos."""
    valores = dict(VALORES)
    valores["cos.primer_piso"] = Decimal("0.6")
    valores["cos.pisos_superiores"] = Decimal("0.4")
    assert evaluar_expresion(
        "cos.primer_piso + (numero_pisos - 1) * cos.pisos_superiores", valores
    ) == Decimal("3.0")


def test_evalua_un_nombre_solo() -> None:
    assert evaluar_expresion("altura_m", VALORES) == Decimal("24.5")


def test_evalua_un_parentesis_anidado() -> None:
    assert evaluar_expresion("((numero_pisos))", VALORES) == Decimal("7")


# --- decimal, nunca float ---


def test_el_resultado_es_decimal() -> None:
    resultado = evaluar_expresion("superficie_predio_m2 / numero_pisos", VALORES)
    assert isinstance(resultado, Decimal)
    assert not isinstance(resultado, float)


def test_un_literal_decimal_no_arrastra_error_binario() -> None:
    """`3.50` en el texto se convierte a `Decimal('3.5')`, no al float 3.5."""
    resultado = evaluar_expresion("numero_pisos * 3.50", VALORES)
    assert resultado == Decimal("24.5")
    assert isinstance(resultado, Decimal)


def test_no_cuenta_a_menos_decimales() -> None:
    """El intérprete no cuantiza: `0,604` debe seguir excediendo un límite de `0,6`.

    Si el intérprete redondeara a dos decimales, `0,604` se volvería `0,60` y el veredicto pasaría
    de `(NC)` a `(C)`. `Decimal` sí redondea la *división* a la precisión del contexto (28 dígitos),
    que es otra cosa: eso no cambia el lado del límite.
    """
    resultado = evaluar_expresion("604 / 1000", VALORES)
    assert resultado == Decimal("0.604")
    assert resultado > Decimal("0.6"), "cuantizar habría perdido el exceso sobre el límite"


def test_la_division_conserva_la_precision_del_contexto() -> None:
    resultado = evaluar_expresion("superficie_predio_m2 / 3", VALORES)
    assert resultado is not None
    assert len(str(resultado).split(".")[1]) >= 20, "se perdió precisión"


# --- lo que NO se puede calcular da None, no excepción ---


def test_la_division_por_cero_da_none_y_no_excepcion() -> None:
    """Una expresión válida sobre datos imposibles no debe romper el motor."""
    assert evaluar_expresion("superficie_predio_m2 / 0", VALORES) is None


def test_la_division_por_un_nombre_nulo_da_none() -> None:
    valores = dict(VALORES, **{"numero_pisos": None})
    assert evaluar_expresion("altura_m / numero_pisos", valores) is None


def test_un_nombre_del_vocabulario_sin_valor_da_none() -> None:
    """Nombre conocido pero el proyecto no lo declara: es un dato faltante, no un error."""
    assert evaluar_expresion("superficie_primer_piso_m2", {}) is None


def test_una_expresion_que_usa_un_nombre_sin_valor_da_none() -> None:
    assert evaluar_expresion("superficie_primer_piso_m2 / superficie_predio_m2", {}) is None


# --- el vocabulario cerrado es lo que impide ejecutar código ---


def test_un_nombre_fuera_del_vocabulario_levanta() -> None:
    with pytest.raises(ErrorVocabulario, match="vocabulario"):
        evaluar_expresion("superficie_inventada * 2", VALORES)


@pytest.mark.parametrize(
    "expresion",
    [
        "__import__('os').system('id')",
        "os.system('id')",
        "superficie_predio_m2.__class__",
        "[x for x in range(3)]",
        "lambda: 1",
        "altura_m if True else 0",
        "superficie_predio_m2 ** 2",
        "open('/etc/passwd')",
        "(1).__class__.__bases__",
    ],
)
def test_no_se_puede_ejecutar_nada(expresion: str) -> None:
    with pytest.raises(ErrorVocabulario):
        evaluar_expresion(expresion, VALORES)


def test_una_expresion_con_sintaxis_invalida_levanta() -> None:
    with pytest.raises(ErrorVocabulario, match="sintaxis"):
        evaluar_expresion("2 +", VALORES)


# --- el invariante de aceptación: no se usa eval ---


def test_no_se_usa_eval_ni_exec_en_ningun_camino() -> None:
    """Criterio de aceptación de T1.4, verificado sobre el código fuente, no sobre la intención."""
    sospechosas: list[str] = []
    for archivo in sorted(SRC.rglob("*.py")):
        fuente = archivo.read_text(encoding="utf-8")
        # `re.compile` no es ejecución dinámica: se excluye explícitamente.
        for patron in (
            r"\beval\s*\(",
            r"\bexec\s*\(",
            r"(?<!re\.)\bcompile\s*\(",
            r"__import__\s*\(",
        ):
            if re.search(patron, fuente):
                sospechosas.append(f"{archivo.relative_to(RAIZ)}: {patron}")
    assert not sospechosas, f"aparece ejecución dinámica: {sospechosas}"


# --- las reglas vienen del corpus ---


def test_cargar_reglas_lee_las_derivaciones_del_corpus() -> None:
    reglas = cargar_reglas(RAIZ / "corpus")
    assert "cus" in reglas.derivaciones
    assert reglas.derivaciones["cus"].expresion == (
        "superficie_edificada_m2 / superficie_predio_m2"
    )


def test_las_derivaciones_del_corpus_traen_su_cita() -> None:
    reglas = cargar_reglas(RAIZ / "corpus")
    for clave, derivacion in reglas.derivaciones.items():
        assert isinstance(derivacion.cita, Cita), f"{clave} sin cita"
        assert derivacion.cita.texto, f"{clave}: la cita no tiene texto"


def test_cargar_reglas_lee_la_relacion_geometrica() -> None:
    reglas = cargar_reglas(RAIZ / "corpus")
    objetivos = {r.objetivo for r in reglas.relaciones}
    assert "cus" in objetivos, "el acoplamiento del cus debe venir del corpus"


def test_cargar_reglas_sobre_un_corpus_vacio_da_reglas_vacias(tmp_path: Path) -> None:
    reglas = cargar_reglas(tmp_path)
    assert reglas.derivaciones == {}
    assert reglas.relaciones == ()


def test_las_reglas_son_inmutables() -> None:
    reglas = cargar_reglas(RAIZ / "corpus")
    with pytest.raises(TypeError):
        reglas.derivaciones["nuevo"] = Derivacion(  # type: ignore[index]
            parametro="nuevo", expresion="1", cita=Cita("x", "y", "z")
        )


def test_una_derivacion_sin_cita_no_se_puede_construir() -> None:
    with pytest.raises(TypeError):
        Derivacion(parametro="cus", expresion="1")  # type: ignore[call-arg]


def test_reglas_admite_derivaciones_vacias() -> None:
    assert Reglas(derivaciones={}).relaciones == ()
