"""Suite de realidad del corpus de Ñuñoa (T1.14).

`tests/test_realidad_corpus.py` verifica la OGUC contra el PDF de MINVU. Acá se hace lo mismo con el
**primer documento municipal** del corpus: la Zona Z-2 del PRC de Ñuñoa.

**Por qué existe.** El cuadro normativo se transcribió a mano, y una transcripción a mano puede
inventar un número sin que ningún test sintético lo note. El fixture `nunoa_zonas.json` guarda el
texto literal del bloque tal como salió de `pypdf`, con el sha256 del PDF, y estos tests exigen que
**cada cita sea un fragmento literal** de ese texto.

La extracción automática se descartó a propósito: el texto trae notas al pie inyectadas dentro del
cuadro (`92 Modifíquese el Artículo 26º…`) y etiquetas partidas en cuatro líneas, con el valor
apareciendo lejos de su rótulo. Un parser heurístico se equivocaría en silencio, que es el modo de
falla que este proyecto no admite.
"""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from rasante.corpus.cargador import ErrorCarga, cargar_reglas, cargar_zona, decimal_de
from rasante.corpus.esquema import validar_corpus
from rasante.dominio import factibilidad
from rasante.dominio.modelos import (
    CodigoHallazgo,
    CodigoVeredicto,
    EstadoRevision,
    Procedencia,
    Proyecto,
    Zona,
)
from rasante.dominio.motor import clasificar, evaluar

RAIZ = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((RAIZ / "tests" / "fixtures" / "nunoa_zonas.json").read_text(encoding="utf-8"))
REALES: dict[str, str] = FIXTURE["zonas"]
ARCHIVO = RAIZ / "corpus" / "zonas" / "nunoa" / "Z-2.yaml"
REGLAS = cargar_reglas(RAIZ / "corpus")


def normalizar(texto: str) -> str:
    return " ".join(str(texto).split())


def zona() -> Zona:
    return cargar_zona(ARCHIVO)


def zona_firmada() -> Zona:
    """La misma zona, pero con un revisor que la firmó.

    El corpus viaja en `borrador` porque **nadie la ha revisado**: la transcribió un programa con
    supervisión humana, y eso no es una firma. D18 dice que sin firma el motor no afirma nada, así
    que para probar el cálculo hay que firmarla explícitamente acá.
    """
    return replace(
        zona(),
        procedencia=Procedencia(
            url_fuente=zona().procedencia.url_fuente,
            hash_fuente=zona().procedencia.hash_fuente,
            consolidado_por=zona().procedencia.consolidado_por,
            extraido=zona().procedencia.extraido,
            revisado_por="Revisor de prueba",
            estado=EstadoRevision.REVISADO,
        ),
    )


def proyecto(**extra: object) -> Proyecto:
    base: dict[str, object] = {
        "superficie_predio_m2": Decimal("600"),
        "numero_viviendas": 20,
        "superficie_primer_piso_m2": Decimal("300"),
        "superficie_edificada_m2": Decimal("900"),
        "altura_m": Decimal("20"),
        "numero_pisos": 8,
    }
    base.update(extra)
    return Proyecto(**base)  # type: ignore[arg-type]


def veredictos(p: Proyecto, z: Zona) -> dict[str, CodigoVeredicto]:
    return {v.clave: v.codigo for v in evaluar(p, z, REGLAS)}


# --- 1. el fixture ---


def test_el_fixture_declara_su_fuente_y_su_hash() -> None:
    assert FIXTURE["sha256"] and len(FIXTURE["sha256"]) == 64
    assert FIXTURE["fuente"].startswith("https://")
    assert "Z-2" in REALES


def test_el_corpus_valida_entero() -> None:
    assert validar_corpus(RAIZ / "corpus")


# --- 2. cada cita es literal ---


def test_la_cita_del_documento_es_literal() -> None:
    """La cita del documento también se verifica: es la que heredan las reglas sin cita propia."""
    datos = yaml.safe_load(ARCHIVO.read_text(encoding="utf-8"))
    assert normalizar(datos["cita"]) in real_de_z2()


def real_de_z2() -> str:
    return REALES["Z-2"]


@pytest.mark.parametrize("clave", sorted(cargar_zona(ARCHIVO).parametros))
def test_cada_cita_de_parametro_es_texto_literal_de_la_ordenanza(clave: str) -> None:
    """Una cita parafraseada no es una cita: si el texto no está en el cuadro, no lo respalda."""
    parametro = cargar_zona(ARCHIVO).parametros[clave]
    limites = parametro.limites or (parametro,)
    for limite in limites:
        assert normalizar(limite.cita.texto) in real_de_z2(), (
            f"{clave}: la cita no aparece literalmente en el cuadro de Z-2: "
            f"{limite.cita.texto!r}"
        )


def test_todas_las_citas_apuntan_al_articulo_26() -> None:
    z = cargar_zona(ARCHIVO)
    for parametro in z.parametros.values():
        for limite in parametro.limites or (parametro,):
            assert limite.cita.norma_id == "prc:nunoa"
            assert limite.cita.articulo == "26"


# --- 3. la transcripción completa ---


def test_la_zona_declara_los_doce_renglones_del_cuadro() -> None:
    assert sorted(cargar_zona(ARCHIVO).parametros) == [
        "adosamiento",
        "agrupamiento",
        "altura_maxima",
        "antejarin",
        "cos",
        "cuerpos_salientes",
        "cus",
        "densidad.bruta",
        "distanciamiento",
        "pisos_maximos",
        "rasante",
        "superficie_predial_minima",
    ]


def test_las_dos_mitades_del_renglon_y_salen_del_mismo_texto() -> None:
    """La ordenanza escribe *"10 pisos **y** 28,00 m"*: dos cotas superiores simultáneas.

    El motor elige **un** límite vigente, así que el "y" no puede ser un operador: son dos
    parámetros, y los dos tienen que cumplirse.
    """
    z = cargar_zona(ARCHIVO)
    altura = z.parametros["altura_maxima"].base
    pisos = z.parametros["pisos_maximos"].base
    assert altura is not None and pisos is not None
    assert (altura.valor, altura.unidad) == (Decimal("28.00"), "m")
    assert (pisos.valor, pisos.unidad) == (Decimal("10"), "pisos")
    assert altura.cita.texto == pisos.cita.texto


def test_el_distanciamiento_solo_tiene_el_tramo_con_valor() -> None:
    """El otro tramo remite al Art. 2.6.3 de OGUC, así que no hay límite que emitir."""
    parametro = cargar_zona(ARCHIVO).parametros["distanciamiento"]
    assert parametro.base is None
    assert len(parametro.excepciones) == 1
    unica = parametro.excepciones[0]
    assert unica.valor == Decimal("5")
    assert unica.cuando == frozenset({"edificio_de_4_pisos_o_mas"})


def test_las_remisiones_quedan_visibles_y_sin_limite() -> None:
    """*"Adosamiento: Según OGUC"* no es un número. Se declara, no se omite.

    Omitirlo lo haría desaparecer del informe en silencio; declararlo `desconocido` lo deja visible
    y citado, con un `P` que le dice al revisor exactamente qué no se evaluó.
    """
    z = cargar_zona(ARCHIVO)
    for clave in ("adosamiento", "agrupamiento"):
        parametro = z.parametros[clave]
        assert parametro.limites == ()
        assert parametro.cita.texto.strip()


def test_la_densidad_se_transcribe_sin_el_punto_de_miles() -> None:
    """La ordenanza escribe `1.600`. `decimal_de` lo rechaza como ambiguo y hay que desambiguar."""
    with pytest.raises(ErrorCarga, match="ambiguo"):
        decimal_de("1.600")
    assert decimal_de("1600") == Decimal("1600")


# --- 4. el hecho del distanciamiento ---


def test_el_hecho_del_tramo_alto_exige_pisos_y_altura() -> None:
    z = zona()
    assert clasificar(proyecto(), z, REGLAS).hechos["edificio_de_4_pisos_o_mas"] is True
    assert clasificar(proyecto(numero_pisos=3), z, REGLAS).hechos["edificio_de_4_pisos_o_mas"] is (
        False
    )
    # 8 pisos pero 10 m de altura: la norma pide las dos cosas.
    pocos = clasificar(proyecto(altura_m=Decimal("10")), z, REGLAS)
    assert pocos.hechos["edificio_de_4_pisos_o_mas"] is False


# --- 5. el motor sobre datos reales ---


def test_sin_firma_el_motor_no_afirma_nada() -> None:
    """D18 sobre el primer documento municipal: el corpus viaja en borrador y no aprueba."""
    z = zona()
    assert z.procedencia.revisada is False
    assert set(veredictos(proyecto(), z).values()) == {CodigoVeredicto.PENDIENTE}
    hallazgos = factibilidad.verificar(proyecto(), z, REGLAS)
    assert [h.codigo for h in hallazgos] == [CodigoHallazgo.FUENTE_SIN_REVISAR]


def test_firmada_la_zona_los_parametros_con_dato_proyecto_se_evaluan() -> None:
    z = zona_firmada()
    codigos = veredictos(proyecto(), z)
    assert codigos["superficie_predial_minima"] is CodigoVeredicto.CUMPLE
    assert codigos["cos"] is CodigoVeredicto.CUMPLE
    assert codigos["cus"] is CodigoVeredicto.CUMPLE
    assert codigos["altura_maxima"] is CodigoVeredicto.CUMPLE
    assert codigos["pisos_maximos"] is CodigoVeredicto.CUMPLE
    assert codigos["densidad.bruta"] is CodigoVeredicto.CUMPLE


def test_firmada_la_zona_rechaza_lo_que_excede() -> None:
    z = zona_firmada()
    assert veredictos(proyecto(altura_m=Decimal("32")), z)["altura_maxima"] is (
        CodigoVeredicto.NO_CUMPLE
    )
    assert veredictos(proyecto(numero_pisos=12), z)["pisos_maximos"] is CodigoVeredicto.NO_CUMPLE
    assert veredictos(proyecto(superficie_predio_m2=Decimal("400")), z)[
        "superficie_predial_minima"
    ] is CodigoVeredicto.NO_CUMPLE


def test_lo_que_el_proyecto_no_declara_da_pendiente_y_no_cumple_por_defecto() -> None:
    """El límite del antejarín existe y se cita, pero el proyecto no declara su antejarín."""
    codigos = veredictos(proyecto(), zona_firmada())
    for clave in ("antejarin", "rasante", "cuerpos_salientes", "distanciamiento"):
        assert codigos[clave] is CodigoVeredicto.PENDIENTE, clave
    for clave in ("adosamiento", "agrupamiento"):
        assert codigos[clave] is CodigoVeredicto.PENDIENTE, clave


def test_el_renglon_de_altura_se_puede_incumplir_por_cualquiera_de_las_dos_mitades() -> None:
    """Es la razón de partir el "y" en dos parámetros: fallar una basta, y el informe lo dice."""
    z = zona_firmada()
    metros_ok_pisos_mal = veredictos(proyecto(altura_m=Decimal("25"), numero_pisos=14), z)
    assert metros_ok_pisos_mal["altura_maxima"] is CodigoVeredicto.CUMPLE
    assert metros_ok_pisos_mal["pisos_maximos"] is CodigoVeredicto.NO_CUMPLE
    metros_mal_pisos_ok = veredictos(proyecto(altura_m=Decimal("30"), numero_pisos=9), z)
    assert metros_mal_pisos_ok["altura_maxima"] is CodigoVeredicto.NO_CUMPLE
    assert metros_mal_pisos_ok["pisos_maximos"] is CodigoVeredicto.CUMPLE
