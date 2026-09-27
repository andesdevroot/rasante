"""Tests del esquema ejecutable del corpus (T1.3).

D14: el corpus deja de ser decorativo. Sus reglas pasan a ser interpretables, y el esquema tiene que
poder expresar cuatro cosas que la ordenanza real trae y el esquema viejo no:

- varios límites **simultáneos** en un parámetro (`"44,00 m y 15 pisos"`)
- variantes por **clasificación** del proyecto (`continua` vs `aislada`)
- **excepciones condicionales** (OGUC `2.6.5`: Conjunto Armónico +50 % cus)
- **relaciones** geométricas entre parámetros

El invariante de la validación: una `expresion` solo puede nombrar cosas del
**vocabulario cerrado**.
El corpus es dato que llega de fuera; si una expresión pudiera nombrar lo que quiera, el intérprete
de T1.4 tendría que ejecutar código arbitrario.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from rasante.corpus.cargador import cargar_reglas
from rasante.corpus.esquema import ErrorEsquema, validar_archivo, validar_corpus, validar_documento
from rasante.dominio.motor import MAXIMOS
from rasante.dominio.vocabulario import CONDICIONES, PARAMETROS, PRIMITIVAS, nombres_de_expresion

RAIZ = Path(__file__).resolve().parents[1]
CORPUS = RAIZ / "corpus"

PROCEDENCIA: dict[str, Any] = {
    "url_fuente": "https://www.nunoa.cl/ordenanza.pdf",
    "hash_fuente": "sha256:" + "0" * 64,
    "consolidado_por": "Texto refundido, junio 2025",
    "extraido": "2026-09-26",
    "estado": "borrador",
}
CITA: dict[str, str] = {"norma_id": "prc:nunoa", "articulo": "Z-4"}


def zona(**parametros: Any) -> dict[str, Any]:
    """Documento de zona mínimo válido, al que cada test le cambia una pieza."""
    return {
        "norma_id": "prc:nunoa",
        "zona": "Z-4",
        "nombre": "Z-4",
        "comuna": "Ñuñoa",
        "region": "RM",
        "cita": "Ordenanza local, artículo Z-4",
        "parametros": parametros
        or {
            "cus": {
                "id": "cus",
                "unidad": "adimensional",
                "limites": [{"valor": "4", "cita": CITA}],
            }
        },
        "procedencia": PROCEDENCIA,
    }


def normativa(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "norma_id": "oguc",
        "articulo": "2.1.23",
        "cita": "3,50 m por el número de pisos",
        "procedencia": PROCEDENCIA,
    }
    base.update(extra)
    return base


# --- el vocabulario cerrado ---


def test_las_primitivas_incluyen_lo_que_las_reglas_necesitan() -> None:
    """Sin `numero_pisos` no se puede expresar ni el acoplamiento geométrico ni la conversión."""
    assert "numero_pisos" in PRIMITIVAS
    assert "superficie_predio_m2" in PRIMITIVAS
    assert "altura_m" in PRIMITIVAS


def test_las_derivaciones_del_corpus_caben_en_el_vocabulario() -> None:
    """Si el corpus deriva un parámetro que el vocabulario no declara, el corpus miente."""
    assert set(cargar_reglas(CORPUS).derivaciones) <= PARAMETROS


def test_toda_derivacion_del_corpus_tiene_sentido_declarado() -> None:
    """Sin sentido, el motor daría `P` para siempre en vez de fallar. Que falle el test."""
    assert set(cargar_reglas(CORPUS).derivaciones) <= MAXIMOS


def test_el_corpus_solo_usa_unidades_conocidas() -> None:
    """Las unidades del corpus deben ser las que el dominio sabe manejar."""
    unidades = set()
    for archivo in CORPUS.rglob("*.yaml"):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        for parametro in (datos.get("parametros") or {}).values():
            for limite in parametro.get("limites", []):
                unidades.add(limite.get("unidad") or parametro.get("unidad"))
    assert unidades <= {"adimensional", "m", "pisos", "hab/ha", None}


def test_hay_condiciones_para_las_variantes_reales() -> None:
    assert "conjunto_armonico" in CONDICIONES
    assert any(c.startswith("agrupamiento_") for c in CONDICIONES)


@pytest.mark.parametrize(
    "expresion",
    ["numero_pisos * 3.50", "cos.primer_piso + (numero_pisos - 1) * cos.pisos_superiores"],
)
def test_extrae_los_nombres_de_una_expresion(expresion: str) -> None:
    nombres = nombres_de_expresion(expresion)
    assert nombres <= (PRIMITIVAS.keys() | PARAMETROS)


# --- el corpus real valida ---


def test_todo_el_corpus_valida() -> None:
    validadas = validar_corpus(CORPUS)
    assert len(validadas) >= 8, f"solo se validaron {len(validadas)} normas"


def test_el_corpus_no_esta_vacio() -> None:
    assert list(CORPUS.rglob("*.yaml"))


# --- validación de la forma ---


def test_acepta_una_zona_minima() -> None:
    validar_documento(zona())


def test_rechaza_limites_vacios() -> None:
    documento = zona(cos={"id": "cos", "unidad": "adimensional", "limites": []})
    with pytest.raises(ErrorEsquema, match="limites"):
        validar_documento(documento)


def test_rechaza_un_limite_sin_cita() -> None:
    documento = zona(cos={"id": "cos", "unidad": "adimensional", "limites": [{"valor": "0.6"}]})
    with pytest.raises(ErrorEsquema, match="cita"):
        validar_documento(documento)


def test_rechaza_un_limite_sin_valor() -> None:
    documento = zona(cos={"id": "cos", "unidad": "adimensional", "limites": [{"cita": CITA}]})
    with pytest.raises(ErrorEsquema, match="valor"):
        validar_documento(documento)


def test_rechaza_una_clave_de_parametro_que_no_coincide_con_su_id() -> None:
    documento = zona(**{"densidad.bruta": {"id": "densidad", "unidad": "hab/ha",
                                           "limites": [{"valor": "50", "cita": CITA}]}})
    with pytest.raises(ErrorEsquema, match="clave"):
        validar_documento(documento)


def test_rechaza_una_procedencia_incompleta() -> None:
    documento = zona()
    documento["procedencia"] = {"url_fuente": "https://x.cl/o.pdf"}
    with pytest.raises(ErrorEsquema, match="procedencia"):
        validar_documento(documento)


def test_rechaza_un_valor_en_float() -> None:
    """Decimal, nunca float (D6): un float en el YAML reintroduce el error binario."""
    documento = zona(cos={"id": "cos", "unidad": "adimensional",
                          "limites": [{"valor": 0.6, "cita": CITA}]})
    with pytest.raises(ErrorEsquema, match="texto"):
        validar_documento(documento)


# --- límites múltiples y condicionales ---


def test_acepta_limites_simultaneos_en_unidades_distintas() -> None:
    """El caso real de Ñuñoa: `44,00 m y 15 pisos`. Los dos ligan."""
    documento = zona(altura_maxima={"id": "altura_maxima", "unidad": "m", "limites": [
        {"valor": "44.00", "unidad": "m", "cita": CITA},
        {"valor": "15", "unidad": "pisos", "cita": CITA},
    ]})
    validar_documento(documento)
    assert len(documento["parametros"]["altura_maxima"]["limites"]) == 2


def test_acepta_un_limite_condicional() -> None:
    """La excepción del Conjunto Armónico (OGUC 2.6.5): +50 % de cus."""
    documento = zona(cus={"id": "cus", "unidad": "adimensional", "limites": [
        {"valor": "4", "cita": CITA},
        {"valor": "6", "cuando": ["conjunto_armonico"], "cita": {"norma_id": "oguc",
                                                                 "articulo": "2.6.5"}},
    ]})
    validar_documento(documento)


def test_validar_corpus_rechaza_un_cuando_sin_hecho_definido(tmp_path: Path) -> None:
    """`cuando` nombra **hechos** (D16). Si ningun articulo los define, ese limite nunca aplicaria.

    La comprobacion es **entre archivos**: un articulo nacional no puede saber que hechos define
    otro. Por eso no la hace `validar_documento` sino `validar_corpus`.
    """
    documento = zona(
        cus={
            "id": "cus",
            "unidad": "adimensional",
            "limites": [
                {"tipo": "base", "valor": "4", "cita": CITA},
                {
                    "tipo": "excepcion",
                    "valor": "6",
                    "cuando": ["hecho_que_nadie_define"],
                    "cita": CITA,
                },
            ],
        }
    )
    (tmp_path / "zona.yaml").write_text(
        yaml.safe_dump(documento, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(ErrorEsquema, match="hecho"):
        validar_corpus(tmp_path)


def test_acepta_un_cuando_cuyo_hecho_esta_definido(tmp_path: Path) -> None:
    """El mismo `cuando`, con su hecho definido en el corpus, se acepta."""
    cita_hecho = {"norma_id": "oguc", "articulo": "2.6.4"}
    (tmp_path / "hechos.yaml").write_text(
        yaml.safe_dump(
            {
                "norma_id": "oguc",
                "articulo": "2.6.4",
                "cita": "condicion de dimension",
                "hechos": {"un_hecho": {"expresion": "numero_pisos >= 1", "cita": cita_hecho}},
                "procedencia": PROCEDENCIA,
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    documento = zona(
        cus={
            "id": "cus",
            "unidad": "adimensional",
            "limites": [
                {"tipo": "base", "valor": "4", "cita": CITA},
                {"tipo": "excepcion", "valor": "6", "cuando": ["un_hecho"], "cita": CITA},
            ],
        }
    )
    (tmp_path / "zona.yaml").write_text(
        yaml.safe_dump(documento, allow_unicode=True), encoding="utf-8"
    )
    validar_corpus(tmp_path)


def test_acepta_una_expresion_con_nombres_del_vocabulario() -> None:
    validar_documento(normativa(regla={"tipo": "conversion",
                                       "expresion": "numero_pisos * 3.50"}))


def test_rechaza_una_expresion_con_nombre_fuera_del_vocabulario() -> None:
    """Criterio de aceptación de T1.3: sintaxis válida, nombre inventado."""
    documento = normativa(regla={"tipo": "conversion", "expresion": "superficie_inventada * 2"})
    with pytest.raises(ErrorEsquema, match="vocabulario"):
        validar_documento(documento)


def test_rechaza_una_expresion_que_intenta_ejecutar_codigo() -> None:
    """`os.system(...)` no llega ni al vocabulario: la lista blanca de sintaxis lo corta antes."""
    documento = normativa(regla={"tipo": "conversion", "expresion": "os.system('rm -rf /')"})
    with pytest.raises(ErrorEsquema, match="no permitida"):
        validar_documento(documento)


@pytest.mark.parametrize(
    "expresion",
    [
        "__import__('os')",           # llamada
        "cos.__class__",              # atributo
        "[x for x in range(3)]",      # comprensión
        "lambda: 1",                  # lambda
        "superficie_predio_m2 if True else 0",  # condicional
        "superficie_predio_m2 ** 2",  # operador fuera de la lista
    ],
)
def test_rechaza_sintaxis_fuera_de_la_lista_blanca(expresion: str) -> None:
    with pytest.raises(ErrorEsquema):
        validar_documento(normativa(regla={"tipo": "calculo", "expresion": expresion}))


def test_rechaza_una_expresion_que_no_se_puede_parsear() -> None:
    with pytest.raises(ErrorEsquema, match="sintaxis"):
        validar_documento(normativa(regla={"tipo": "calculo", "expresion": "2 +"}))


# --- relaciones entre parámetros ---


def test_acepta_una_relacion_geometrica() -> None:
    documento = normativa(
        relaciones=[
            {
                "tipo": "cota_superior",
                "objetivo": "cus",
                "expresion": "cos.primer_piso + (numero_pisos - 1) * cos.pisos_superiores",
                "cita": {"norma_id": "oguc", "articulo": "1.1.2"},
            }
        ]
    )
    validar_documento(documento)


def test_rechaza_una_relacion_con_objetivo_fuera_del_vocabulario() -> None:
    documento = normativa(relaciones=[{"tipo": "cota_superior", "objetivo": "inventado",
                                       "expresion": "1", "cita": CITA}])
    with pytest.raises(ErrorEsquema, match="objetivo"):
        validar_documento(documento)


def test_rechaza_una_primitiva_como_objetivo_de_relacion() -> None:
    """`numero_pisos` es un valor del proyecto, no un parámetro que una relación pueda acotar."""
    documento = normativa(relaciones=[{"tipo": "cota_superior", "objetivo": "numero_pisos",
                                       "expresion": "1", "cita": CITA}])
    with pytest.raises(ErrorEsquema, match="objetivo"):
        validar_documento(documento)


def test_rechaza_una_relacion_sin_cita() -> None:
    documento = normativa(relaciones=[{"tipo": "cota_superior", "objetivo": "cus",
                                       "expresion": "1"}])
    with pytest.raises(ErrorEsquema, match="cita"):
        validar_documento(documento)


# --- el archivo real de 1.1.2 debe traer ya la relación geométrica ---


def test_el_archivo_de_definiciones_declara_el_acoplamiento_geometrico() -> None:
    """Sin esta relación, el verificador de T1.5 no tiene de dónde sacarla."""
    datos = yaml.safe_load((CORPUS / "oguc" / "1.1.2.yaml").read_text(encoding="utf-8"))
    relaciones = datos.get("relaciones", [])
    assert any(r.get("objetivo") == "cus" for r in relaciones), "falta el acoplamiento del cus"


def test_validar_archivo_da_el_nombre_del_archivo_en_el_error(tmp_path: Path) -> None:
    malo = tmp_path / "malo.yaml"
    malo.write_text("norma_id: x\n", encoding="utf-8")
    with pytest.raises(ErrorEsquema, match="malo.yaml"):
        validar_archivo(malo)
