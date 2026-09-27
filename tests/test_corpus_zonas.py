"""Tests del cargador de zonas (T1.7).

Convierte `corpus/prc/.../zonas/*.yaml` en `Zona` del dominio (T1.3 → T1.1).

Dos trampas concretas, las dos verificadas contra la ordenanza real de Ñuñoa:

1. **Coma decimal.** La ordenanza escribe `0,6`. Si el cargador no lo trata, `0,6` se vuelve `6` —
   diez veces el coeficiente, y un `(C)` donde tocaba `(NC)`.
2. **Claves duplicadas.** PyYAML **no** las detecta: se queda con la última y descarta la otra en
   silencio. Con `cos` teniendo variantes, eso pierde una regla sin avisar.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from rasante.corpus.cargador import ErrorCarga, cargar_zona, cargar_zonas, decimal_de
from rasante.dominio.modelos import EstadoRevision, TipoLimite

FIXTURES = Path(__file__).parent / "fixtures" / "zonas"

PROCEDENCIA = """procedencia:
  url_fuente: "https://www.nunoa.cl/ordenanza.pdf"
  hash_fuente: "sha256:%s"
  consolidado_por: "Texto refundido, junio 2025"
  extraido: "2026-09-26"
  estado: revisado""" % ("0" * 64)


def escribir(tmp_path: Path, cuerpo: str) -> Path:
    ruta = tmp_path / "zona.yaml"
    ruta.write_text(cuerpo, encoding="utf-8")
    return ruta


def zona_yaml(parametros: str) -> str:
    return (
        'norma_id: "prc:nunoa"\n'
        'zona: "Z-4"\n'
        'nombre: "Z-4"\n'
        'comuna: "Ñuñoa"\n'
        'region: "RM"\n'
        'cita: "Ordenanza local, articulo Z-4"\n'
        f"parametros:\n{parametros}"
        f"{PROCEDENCIA}\n"
    )


COS = '''  cos.primer_piso:
    id: cos
    calificador: primer_piso
    limites:
      - tipo: base
        valor: "{valor}"
        unidad: adimensional
        cita: {{norma_id: "prc:nunoa", articulo: "Z-4"}}
'''


# --- el caso que importa: la coma decimal ---


def test_la_coma_decimal_no_se_convierte_en_entero() -> None:
    """`0,6` es cero coma seis. Sin esto se leería 6, diez veces el coeficiente."""
    assert decimal_de("0,6") == Decimal("0.6")


def test_un_entero_con_coma_sigue_siendo_entero() -> None:
    assert decimal_de("4") == Decimal("4")


def test_el_punto_tambien_sirve_de_separador_decimal() -> None:
    assert decimal_de("0.6") == Decimal("0.6")
    assert decimal_de("3.50") == Decimal("3.50")
    assert decimal_de("0.600") == Decimal("0.600")


def test_los_miles_con_punto_y_decimal_con_coma() -> None:
    assert decimal_de("1.234,56") == Decimal("1234.56")


def test_un_millar_se_escribe_sin_punto_o_con_coma() -> None:
    """`5.000` cae en el caso ambiguo: hay que escribirlo inequívoco."""
    assert decimal_de("5000") == Decimal("5000")
    assert decimal_de("5.000,00") == Decimal("5000.00")


@pytest.mark.parametrize("ambiguo", ["1.234", "5.000", "12.500"])
def test_rechaza_un_millar_escrito_con_punto(ambiguo: str) -> None:
    """Tres dígitos tras el punto: ¿miles o milésimas? Se exige escribirlo inequívoco.

    `0.600` sí se acepta, porque el entero es cero y nadie escribe `0.600` para decir 600.
    """
    with pytest.raises(ErrorCarga, match="ambiguo"):
        decimal_de(ambiguo)


def test_rechaza_algo_que_no_es_un_numero() -> None:
    with pytest.raises(ErrorCarga):
        decimal_de("no es un numero")


# --- el cargador ---


def test_carga_una_zona_minima(tmp_path: Path) -> None:
    z = cargar_zona(escribir(tmp_path, zona_yaml(COS.format(valor="0,6"))))
    assert z.codigo == "Z-4"
    assert z.comuna == "Ñuñoa"
    assert z.procedencia.estado is EstadoRevision.REVISADO


def test_el_valor_llega_como_decimal_de_la_ordenanza(tmp_path: Path) -> None:
    z = cargar_zona(escribir(tmp_path, zona_yaml(COS.format(valor="0,6"))))
    parametro = z.parametro("cos.primer_piso")
    assert parametro is not None
    assert parametro.base is not None
    assert parametro.base.valor == Decimal("0.6")
    assert isinstance(parametro.base.valor, Decimal)


def test_el_calificador_sobrevive_a_la_carga(tmp_path: Path) -> None:
    z = cargar_zona(escribir(tmp_path, zona_yaml(COS.format(valor="0,6"))))
    assert "cos.primer_piso" in z.parametros


def test_carga_limites_con_tipo_y_condicion(tmp_path: Path) -> None:
    parametros = '''  cus:
    id: cus
    limites:
      - tipo: base
        valor: "4"
        unidad: adimensional
        cita: {norma_id: "prc:nunoa", articulo: "Z-4"}
      - tipo: excepcion
        valor: "6"
        unidad: adimensional
        cuando: [dimension_a]
        cita: {norma_id: oguc, articulo: "2.6.5"}
'''
    z = cargar_zona(escribir(tmp_path, zona_yaml(parametros)))
    cus = z.parametro("cus")
    assert cus is not None
    assert cus.base is not None and cus.base.valor == Decimal("4")
    assert len(cus.excepciones) == 1
    assert cus.excepciones[0].cuando == frozenset({"dimension_a"})
    assert cus.excepciones[0].tipo is TipoLimite.EXCEPCION


def test_una_zona_sin_cita_es_rechazada(tmp_path: Path) -> None:
    cuerpo = zona_yaml(COS.format(valor="0,6")).replace(
        'cita: "Ordenanza local, articulo Z-4"\n', ""
    )
    with pytest.raises(ErrorCarga):
        cargar_zona(escribir(tmp_path, cuerpo))


def test_una_procedencia_incompleta_es_rechazada(tmp_path: Path) -> None:
    cuerpo = zona_yaml(COS.format(valor="0,6")).replace("sha256:" + "0" * 64, "")
    with pytest.raises(ErrorCarga):
        cargar_zona(escribir(tmp_path, cuerpo))


# --- claves duplicadas: PyYAML no las ve ---


def test_rechaza_claves_de_parametro_duplicadas(tmp_path: Path) -> None:
    """`cos` dos veces es YAML válido y pierde una regla en silencio. Debe fallar."""
    parametros = COS.format(valor="0,6") + COS.format(valor="0,4")
    with pytest.raises(ErrorCarga, match="duplicad"):
        cargar_zona(escribir(tmp_path, zona_yaml(parametros)))


def test_rechaza_claves_duplicadas_anidadas(tmp_path: Path) -> None:
    parametros = '''  cus:
    id: cus
    limites:
      - tipo: base
        valor: "4"
        valor: "9"
        unidad: adimensional
        cita: {norma_id: "prc:nunoa", articulo: "Z-4"}
'''
    with pytest.raises(ErrorCarga, match="duplicad"):
        cargar_zona(escribir(tmp_path, zona_yaml(parametros)))


# --- recorrer el corpus ---


def test_cargar_zonas_sobre_una_carpeta_sin_zonas_da_lista_vacia(tmp_path: Path) -> None:
    assert cargar_zonas(tmp_path) == []


def test_las_zonas_del_corpus_son_cargables() -> None:
    """Todavía no hay zonas en el corpus (llegan en T1.11), pero el recorrido no debe fallar."""
    from pathlib import Path as P

    raiz = P(__file__).resolve().parents[1] / "corpus"
    for zona in cargar_zonas(raiz):
        assert zona.codigo
