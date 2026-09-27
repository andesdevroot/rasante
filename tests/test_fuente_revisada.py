"""Un dato que nadie revisó no puede aprobar (agujero verificado el 2026-09-26).

El motor **no leía** `Procedencia.estado`: una zona en `borrador`, con `revisado_por=None`, producía
los mismos `(C)` que una validada. Es la misma clase de fallo que el proyecto viene cerrando —
aprobación silenciosa desde entrada no confiable.

El razonamiento es el mismo que ya rige para `DESCONOCIDO`: **lo que no está validado no afirma**. Y
vale en las dos direcciones: un `(NC)` desde una fuente sin revisar también rechazaría un proyecto
sin fundamento.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from rasante.corpus.cargador import cargar_reglas
from rasante.dominio.factibilidad import verificar
from rasante.dominio.modelos import (
    Cita,
    CodigoHallazgo,
    CodigoVeredicto,
    EstadoParametro,
    EstadoRevision,
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
from rasante.dominio.motor import evaluar

REGLAS = cargar_reglas(Path(__file__).resolve().parents[1] / "corpus")
CITA = Cita(norma_id="prc:nunoa", articulo="Z-4", texto="ordenanza local")


def procedencia(estado: EstadoRevision, revisado_por: str | None) -> Procedencia:
    return Procedencia(
        url_fuente="https://www.nunoa.cl/ordenanza.pdf",
        hash_fuente="sha256:" + "0" * 64,
        consolidado_por="Texto refundido, junio 2025",
        extraido="2026-09-26",
        revisado_por=revisado_por,
        estado=estado,
    )


def zona(estado: EstadoRevision = EstadoRevision.BORRADOR, revisado_por: str | None = None) -> Zona:
    return Zona(
        codigo="Z-4",
        nombre="Z-4",
        comuna="Ñuñoa",
        parametros={
            "cus": Parametro(
                id="cus",
                limites=(Limite(TipoLimite.BASE, Decimal("4"), "adimensional", CITA),),
                sentido=Sentido.MAXIMO,
                estado=EstadoParametro.APLICABLE,
                cita=CITA,
            ),
            "densidad": Parametro(
                id="densidad",
                limites=(Limite(TipoLimite.BASE, Decimal("50"), "hab/ha", CITA),),
                sentido=Sentido.MAXIMO,
                estado=EstadoParametro.APLICABLE,
                cita=CITA,
            ),
        },
        vigencia=Vigencia(),
        procedencia=procedencia(estado, revisado_por),
    )


# Cumple con holgura: cus 3,5 <= 4 y 20 viv/ha <= 50.
CUMPLE = Proyecto(
    superficie_predio_m2=Decimal("1000"),
    numero_viviendas=10,
    superficie_edificada_m2=Decimal("3500"),
)


def codigos(z: Zona, p: Proyecto = CUMPLE) -> set[CodigoVeredicto]:
    return {v.codigo for v in evaluar(p, z, REGLAS)}


def test_la_procedencia_sabe_si_alguien_la_reviso() -> None:
    assert not procedencia(EstadoRevision.BORRADOR, None).revisada
    assert procedencia(EstadoRevision.REVISADO, "J. Pérez").revisada


def test_una_zona_sin_revisar_no_aprueba() -> None:
    assert CodigoVeredicto.CUMPLE not in codigos(zona())


def test_una_zona_sin_revisar_tampoco_rechaza() -> None:
    """Un `(NC)` sin fundamento también haría daño: rechazaría un proyecto que quizá cumple."""
    assert CodigoVeredicto.NO_CUMPLE not in codigos(zona())


def test_una_zona_sin_revisar_da_pendiente() -> None:
    assert codigos(zona()) == {CodigoVeredicto.PENDIENTE}


def test_una_zona_revisada_si_aprueba() -> None:
    z = zona(EstadoRevision.REVISADO, "J. Pérez")
    assert CodigoVeredicto.CUMPLE in codigos(z)


def test_declararse_validado_sin_firma_no_basta() -> None:
    """`estado` es una etiqueta; la firma es `revisado_por`. Sin firma no hay revisión."""
    assert CodigoVeredicto.CUMPLE not in codigos(zona(EstadoRevision.VALIDADO, None))


def test_una_zona_sin_revisar_emite_hallazgo() -> None:
    hallazgos = verificar(CUMPLE, zona(), REGLAS)
    assert CodigoHallazgo.FUENTE_SIN_REVISAR in {h.codigo for h in hallazgos}


def test_el_hallazgo_dice_que_falta_la_revision() -> None:
    hallazgo = next(
        h for h in verificar(CUMPLE, zona(), REGLAS)
        if h.codigo is CodigoHallazgo.FUENTE_SIN_REVISAR
    )
    assert "revis" in hallazgo.mensaje.lower()
    assert hallazgo.cita.texto
    assert hallazgo.severidad is Severidad.ADVERTENCIA


def test_el_hallazgo_no_se_duplica_por_parametro() -> None:
    """Una zona sin revisar es **un** problema, no uno por cada parámetro."""
    hallazgos = verificar(CUMPLE, zona(), REGLAS)
    assert sum(1 for h in hallazgos if h.codigo is CodigoHallazgo.FUENTE_SIN_REVISAR) == 1


def test_una_zona_revisada_no_emite_ese_hallazgo() -> None:
    hallazgos = verificar(CUMPLE, zona(EstadoRevision.REVISADO, "J. Pérez"), REGLAS)
    assert CodigoHallazgo.FUENTE_SIN_REVISAR not in {h.codigo for h in hallazgos}


def test_verificar_sin_revisar_no_reporta_factibilidad_falsa() -> None:
    """Sin corpus revisado no se afirma que un proyecto sea imposible, ni que una norma lo sea."""
    hallazgos = verificar(CUMPLE, zona(), REGLAS)
    codigos_h = {h.codigo for h in hallazgos}
    assert CodigoHallazgo.PROYECTO_IMPOSIBLE not in codigos_h
