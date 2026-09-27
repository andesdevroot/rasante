"""El sentido de la comparación lo declara el corpus, no el motor.

`MAXIMOS` era **lo último hardcodeado** en `motor.py`: una lista en Python diciendo qué
parámetros son cotas superiores. El resto del conocimiento ya venía del corpus (D14), así que era
una incoherencia — y peor: agregar un parámetro de mínimo (densidad mínima, área verde mínima)
exigía editar código.

Ahora el `Parametro` declara su `sentido`, y es **obligatorio**. Un valor por defecto sería peor que
la lista: un mínimo tratado como máximo daría el veredicto invertido **en silencio**.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from rasante.corpus.cargador import cargar_reglas, cargar_zona
from rasante.dominio import motor
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

REGLAS = cargar_reglas(Path(__file__).resolve().parents[1] / "corpus")
CITA = Cita(norma_id="prc:nunoa", articulo="Z-4", texto="ordenanza local")


def procedencia() -> Procedencia:
    return Procedencia(
        url_fuente="https://www.nunoa.cl/ordenanza.pdf",
        hash_fuente="sha256:" + "0" * 64,
        consolidado_por="Texto refundido, junio 2025",
        extraido="2026-09-26",
        revisado_por="Revisor de prueba",
        estado=EstadoRevision.REVISADO,
    )


def parametro(clave: str, valor: str, sentido: Sentido) -> Parametro:
    id_, _, calificador = clave.partition(".")
    return Parametro(
        id=id_,
        limites=(Limite(TipoLimite.BASE, Decimal(valor), "adimensional", CITA),),
        sentido=sentido,
        estado=EstadoParametro.APLICABLE,
        cita=CITA,
        calificador=calificador or None,
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


def veredicto_de(p: Proyecto, z: Zona, clave: str) -> CodigoVeredicto:
    return next(v for v in evaluar(p, z, REGLAS) if v.clave == clave).codigo


def proyecto(cus: str, densidad: str) -> Proyecto:
    # predio 1.000 m²; cus = edificada/1.000; densidad = viviendas/0,1 ha
    return Proyecto(
        superficie_predio_m2=Decimal("1000"),
        numero_viviendas=int(Decimal(densidad) * Decimal("0.1")),
        superficie_edificada_m2=Decimal(cus) * Decimal("1000"),
    )


# --- el motor ya no tiene la lista ---


def test_el_motor_no_tiene_una_lista_de_maximos() -> None:
    assert not hasattr(motor, "MAXIMOS"), "el sentido tiene que venir del corpus, no de Python"


def test_el_sentido_es_obligatorio() -> None:
    """Un default silencioso invertiría el veredicto de un mínimo sin que nadie se entere."""
    with pytest.raises(TypeError):
        Parametro(  # type: ignore[call-arg]
            id="cus",
            limites=(Limite(TipoLimite.BASE, Decimal("4"), "adimensional", CITA),),
            estado=EstadoParametro.APLICABLE,
            cita=CITA,
        )


def test_un_sentido_inventado_no_se_puede_construir() -> None:
    with pytest.raises((ErrorDominio, ValueError)):
        parametro("cus", "4", "mas_o_menos")  # type: ignore[arg-type]


# --- un máximo no se excede ---


def test_un_maximo_cumple_por_debajo() -> None:
    z = zona(parametro("cus", "4", Sentido.MAXIMO))
    assert veredicto_de(proyecto(cus="3", densidad="10"), z, "cus") is CodigoVeredicto.CUMPLE


def test_un_maximo_no_cumple_por_encima() -> None:
    z = zona(parametro("cus", "4", Sentido.MAXIMO))
    assert veredicto_de(proyecto(cus="5", densidad="10"), z, "cus") is CodigoVeredicto.NO_CUMPLE


# --- un mínimo no se queda corto, y es el caso que la lista no cubría ---


def test_un_minimo_cumple_por_encima() -> None:
    z = zona(parametro("densidad", "20", Sentido.MINIMO))
    assert veredicto_de(proyecto(cus="1", densidad="50"), z, "densidad") is CodigoVeredicto.CUMPLE


def test_un_minimo_no_cumple_por_debajo() -> None:
    """Con un default de máximo, este caso habría dado `C` — el veredicto invertido."""
    z = zona(parametro("densidad", "20", Sentido.MINIMO))
    assert veredicto_de(proyecto(cus="1", densidad="5"), z, "densidad") is CodigoVeredicto.NO_CUMPLE


def test_justo_en_el_limite_cumple_en_los_dos_sentidos() -> None:
    """El límite exacto se cumple: no se excede un máximo, ni se queda corto un mínimo."""
    p = proyecto(cus="4", densidad="20")
    assert veredicto_de(p, zona(parametro("cus", "4", Sentido.MAXIMO)), "cus") is (
        CodigoVeredicto.CUMPLE
    )
    assert veredicto_de(p, zona(parametro("densidad", "20", Sentido.MINIMO)), "densidad") is (
        CodigoVeredicto.CUMPLE
    )


# --- el corpus lo declara y el cargador lo lee ---


def test_el_esquema_exige_el_sentido(tmp_path: Path) -> None:
    from rasante.corpus.esquema import ErrorEsquema, validar_documento

    documento = {
        "norma_id": "prc:nunoa",
        "zona": "Z-4",
        "cita": "ordenanza",
        "parametros": {
            "cus": {
                "id": "cus",
                "limites": [
                    {
                        "tipo": "base",
                        "valor": "4",
                        "cita": {"norma_id": "prc:nunoa", "articulo": "Z-4"},
                    }
                ],
            }
        },
        "procedencia": {
            "url_fuente": "https://x.cl/o.pdf",
            "hash_fuente": "sha256:" + "0" * 64,
            "consolidado_por": "refundido",
            "extraido": "2026-09-26",
        },
    }
    with pytest.raises(ErrorEsquema, match="sentido"):
        validar_documento(documento)


def test_el_cargador_lee_el_sentido(tmp_path: Path) -> None:
    ruta = tmp_path / "zona.yaml"
    ruta.write_text(
        'norma_id: "prc:nunoa"\n'
        'zona: "Z-4"\n'
        'cita: "ordenanza local"\n'
        "parametros:\n"
        "  densidad:\n"
        "    id: densidad\n"
        "    sentido: minimo\n"
        "    limites:\n"
        "      - tipo: base\n"
        '        valor: "20"\n'
        "        unidad: hab/ha\n"
        '        cita: {norma_id: "prc:nunoa", articulo: "Z-4"}\n'
        "procedencia:\n"
        '  url_fuente: "https://x.cl/o.pdf"\n'
        f'  hash_fuente: "sha256:{"0" * 64}"\n'
        '  consolidado_por: "refundido"\n'
        '  extraido: "2026-09-26"\n',
        encoding="utf-8",
    )
    z = cargar_zona(ruta)
    parametro_cargado = z.parametro("densidad")
    assert parametro_cargado is not None
    assert parametro_cargado.sentido is Sentido.MINIMO
