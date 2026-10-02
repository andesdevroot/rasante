"""La CLI: coordenada → zona → veredictos, desde una terminal (T1.13).

La CLI es la última pieza de la cadena y su trabajo es **no perder información por el camino**. Los
tres errores de T1.12 tienen responsables distintos, así que tienen **códigos de salida distintos**:
un script que los trate igual va a reintentar lo que no se arregla reintentando. Y los hallazgos de
T1.5 van **aparte** de los veredictos, porque un hallazgo es del proyecto y un veredicto es de un
parámetro: mezclarlos haría ilegible el informe.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rasante.cli import (
    CODIGO_AMBIGUA,
    CODIGO_OK,
    CODIGO_SIN_CORPUS,
    CODIGO_SIN_ZONA,
    app,
)

RAIZ = Path(__file__).resolve().parents[1]
GEOJSON = RAIZ / "tests" / "fixtures" / "arcgis_geom.geojson"
CORPUS = RAIZ / "corpus"

# El centroide del primer polígono del fixture real, que es Z-2.
LAT_Z2, LON_Z2 = -33.472219, -70.621721
# Un punto en Santiago que no cae en ningún polígono del fixture.
LAT_FUERA, LON_FUERA = -33.4000, -70.5000

runner = CliRunner()


@pytest.fixture(autouse=True)
def _entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RASANTE_CORPUS", str(CORPUS))
    monkeypatch.setenv("RASANTE_GEOJSON", str(GEOJSON))


def test_zona_imprime_codigo_y_nombre() -> None:
    r = runner.invoke(app, ["zona", "--lat", str(LAT_Z2), "--lon", str(LON_Z2)])
    assert r.exit_code == CODIGO_OK, r.output
    assert "Z-2" in r.output


def test_zona_json_tiene_esquema_estable() -> None:
    r = runner.invoke(app, ["zona", "--lat", str(LAT_Z2), "--lon", str(LON_Z2), "--json"])
    assert r.exit_code == CODIGO_OK, r.output
    datos = json.loads(r.output)
    assert set(datos) == {"zona", "nombre", "comuna", "parametros", "revisada"}
    assert datos["zona"] == "Z-2"
    assert datos["revisada"] is False, "la zona transcrita viaja en borrador: nadie la ha firmado"
    assert datos["parametros"] == 12


def test_zona_sin_revisar_lo_advierte_en_json() -> None:
    """D18 llega a la CLI: la zona está en borrador y el usuario tiene que enterarse."""
    r = runner.invoke(app, ["zona", "--lat", str(LAT_Z2), "--lon", str(LON_Z2), "--json"])
    assert json.loads(r.output)["revisada"] is False


# --- los tres errores, con códigos distintos ---


def test_coordenada_sin_zona_tiene_su_propio_codigo() -> None:
    r = runner.invoke(app, ["zona", "--lat", str(LAT_FUERA), "--lon", str(LON_FUERA)])
    assert r.exit_code == CODIGO_SIN_ZONA
    assert "no cae en ninguna zona" in r.output


def test_zona_sin_corpus_tiene_otro_codigo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El corpus de prueba tiene solo `Z-9`; el punto cae en `Z-2`."""
    from decimal import Decimal

    from rasante.dominio.modelos import (
        Cita,
        EstadoParametro,
        EstadoRevision,
        Limite,
        Parametro,
        Procedencia,
        Sentido,
        TipoLimite,
        Vigencia,
        Zona,
    )

    cita = Cita(norma_id="prc:nunoa", articulo="26", texto="cuadro")
    z = Zona(
        codigo="Z-9",
        nombre="Z-9",
        comuna="Ñuñoa",
        parametros={
            "cus": Parametro(
                id="cus",
                limites=(Limite(TipoLimite.BASE, Decimal("2"), "adimensional", cita),),
                sentido=Sentido.MAXIMO,
                estado=EstadoParametro.APLICABLE,
                cita=cita,
            )
        },
        vigencia=Vigencia(),
        procedencia=Procedencia(
            url_fuente="https://x.cl/o.pdf",
            hash_fuente="sha256:" + "0" * 64,
            consolidado_por="refundido",
            extraido="2026-09-27",
            estado=EstadoRevision.BORRADOR,
        ),
    )
    from rasante.geo.resolver import CorpusZonas

    monkeypatch.setattr(
        "rasante.cli._cargar_corpus", lambda _: CorpusZonas.desde_zonas([z])
    )
    r = runner.invoke(app, ["zona", "--lat", str(LAT_Z2), "--lon", str(LON_Z2)])
    assert r.exit_code == CODIGO_SIN_CORPUS
    assert "Z-2" in r.output


def test_los_tres_codigos_son_distintos() -> None:
    """Si dos coincidieran, un script no distinguiría un error de entrada de trabajo pendiente."""
    assert len({CODIGO_OK, CODIGO_SIN_ZONA, CODIGO_SIN_CORPUS, CODIGO_AMBIGUA}) == 4


# --- evaluar: veredictos y hallazgos, separados ---


def test_evaluar_json_trae_veredictos_y_hallazgos_aparte() -> None:
    r = runner.invoke(
        app,
        [
            "evaluar",
            "--lat", str(LAT_Z2), "--lon", str(LON_Z2),
            "--predio", "600", "--viviendas", "20",
            "--json",
        ],
    )
    assert r.exit_code == CODIGO_OK, r.output
    datos = json.loads(r.output)
    assert set(datos) == {"zona", "veredictos", "hallazgos", "cobertura"}
    assert datos["cobertura"]["total"] == 12
    assert isinstance(datos["veredictos"], list)
    assert isinstance(datos["hallazgos"], list)


def test_cada_veredicto_lleva_su_cita_y_su_motivo() -> None:
    """Sin la cita el veredicto no es auditable; sin el motivo, un `P` no dice qué falta."""
    r = runner.invoke(
        app,
        ["evaluar", "--lat", str(LAT_Z2), "--lon", str(LON_Z2), "--predio", "600",
         "--viviendas", "20", "--json"],
    )
    for v in json.loads(r.output)["veredictos"]:
        assert {"clave", "codigo", "norma", "articulo", "motivo"} == set(v)
        assert v["norma"] and v["articulo"]
        if v["codigo"] == "P":
            assert v["motivo"], f"{v['clave']} quedó pendiente sin decir por qué"


def test_evaluar_muestra_los_hallazgos_aparte_de_los_veredictos() -> None:
    """Una zona en borrador no aprueba nada y emite `FUENTE_SIN_REVISAR` (D18)."""
    r = runner.invoke(
        app,
        ["evaluar", "--lat", str(LAT_Z2), "--lon", str(LON_Z2), "--predio", "600",
         "--viviendas", "20", "--json"],
    )
    datos = json.loads(r.output)
    assert [h["codigo"] for h in datos["hallazgos"]] == ["fuente_sin_revisar"]
    assert all(v["codigo"] == "P" for v in datos["veredictos"])


def test_evaluar_en_texto_no_mezcla_las_dos_secciones() -> None:
    r = runner.invoke(
        app,
        ["evaluar", "--lat", str(LAT_Z2), "--lon", str(LON_Z2), "--predio", "600",
         "--viviendas", "20"],
    )
    assert r.exit_code == CODIGO_OK, r.output
    salida = r.output.upper()
    assert "VEREDICTOS" in salida
    assert "HALLAZGOS" in salida
    assert salida.index("VEREDICTOS") < salida.index("HALLAZGOS")
