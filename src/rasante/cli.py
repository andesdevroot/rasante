"""La CLI de Rasante (T1.13). Capa de presentación: no decide nada.

Su trabajo es **no perder información por el camino**. Dos decisiones lo gobiernan:

**Los tres errores de T1.12 tienen códigos de salida distintos.** Un `SinZonaError` es un error de
entrada —se arregla corrigiendo la coordenada—, un `ZonaSinCorpusError` es trabajo pendiente de
corpus, y un `ZonaAmbiguaError` necesita que decida una persona. Un script que los trate igual va a
reintentar lo que no se arregla reintentando.

**Los hallazgos van aparte de los veredictos.** Un veredicto es de **un parámetro** y va al Formato
Tipo; un hallazgo es **del proyecto** y puede involucrar varios (D15). Mezclarlos haría ilegible el
informe, y el revisor no sabría qué está firmando.

El corpus y la capa del PRC se leen de `RASANTE_CORPUS` y `RASANTE_GEOJSON`, para que la CLI sea
probable sin red ni rutas clavadas.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import typer

from .corpus.cargador import cargar_reglas, cargar_zonas
from .dominio.cobertura import medir
from .dominio.factibilidad import verificar
from .dominio.modelos import ErrorDominio, Proyecto, Zona
from .dominio.motor import evaluar as evaluar_motor
from .geo.indices import ErrorGeo, IndiceZonas
from .geo.resolver import (
    CorpusZonas,
    SinZonaError,
    ZonaAmbiguaError,
    ZonaSinCorpusError,
    resolver_zona,
)

CODIGO_OK = 0
CODIGO_SIN_ZONA = 1
CODIGO_SIN_CORPUS = 2
CODIGO_AMBIGUA = 3
CODIGO_ERROR = 4

CORPUS_POR_DEFECTO = "corpus"
GEOJSON_POR_DEFECTO = "cache/nunoa.geojson"

app = typer.Typer(
    add_completion=False,
    help="Evalúa el cumplimiento de la OGUC y del plan regulador para un predio.",
)


def _rutas() -> tuple[Path, Path]:
    return (
        Path(os.environ.get("RASANTE_CORPUS", CORPUS_POR_DEFECTO)),
        Path(os.environ.get("RASANTE_GEOJSON", GEOJSON_POR_DEFECTO)),
    )


def _cargar_corpus(raiz: Path) -> CorpusZonas:
    return CorpusZonas.desde_zonas(cargar_zonas(raiz))


def _resolver(lat: float, lon: float) -> Zona:
    """Resuelve la zona, y traduce cada fallo a **su** código de salida."""
    raiz, geojson = _rutas()
    try:
        indice = IndiceZonas.desde_geojson(geojson)
    except ErrorGeo as error:
        typer.echo(f"error: no se pudo leer la capa del PRC en {geojson}: {error}", err=True)
        raise typer.Exit(CODIGO_ERROR) from error
    try:
        return resolver_zona(lat, lon, indice=indice, corpus=_cargar_corpus(raiz))
    except SinZonaError as error:
        typer.echo(f"sin zona: {error}", err=True)
        raise typer.Exit(CODIGO_SIN_ZONA) from error
    except ZonaSinCorpusError as error:
        typer.echo(f"zona sin corpus: {error}", err=True)
        raise typer.Exit(CODIGO_SIN_CORPUS) from error
    except ZonaAmbiguaError as error:
        typer.echo(f"zona ambigua: {error}", err=True)
        raise typer.Exit(CODIGO_AMBIGUA) from error


def _zona_como_json(zona: Zona) -> dict[str, Any]:
    return {
        "zona": zona.codigo,
        "nombre": zona.nombre,
        "comuna": zona.comuna,
        "parametros": len(zona.parametros),
        "revisada": zona.procedencia.revisada,
    }


@app.command()
def zona(
    lat: float = typer.Option(..., "--lat", help="Latitud en grados decimales (WGS84)."),
    lon: float = typer.Option(..., "--lon", help="Longitud en grados decimales (WGS84)."),
    salida_json: bool = typer.Option(False, "--json", help="Salida en JSON."),
) -> None:
    """En qué zona del plan regulador cae una coordenada."""
    z = _resolver(lat, lon)
    if salida_json:
        typer.echo(json.dumps(_zona_como_json(z), ensure_ascii=False))
        return
    typer.echo(f"{z.codigo} — {z.nombre} ({z.comuna})")
    typer.echo(f"parámetros declarados: {len(z.parametros)}")
    if not z.procedencia.revisada:
        typer.echo(
            "AVISO: la zona no tiene revisión humana (D18). Los veredictos saldrán pendientes.",
            err=True,
        )


def _proyecto(
    predio: str, viviendas: int, edificada: str | None, primer_piso: str | None,
    altura: str | None, pisos: int | None,
) -> Proyecto:
    def decimal(texto: str | None) -> Decimal | None:
        if texto is None:
            return None
        try:
            return Decimal(texto)
        except InvalidOperation as error:
            raise typer.BadParameter(f"{texto!r} no es un número") from error

    try:
        return Proyecto(
            superficie_predio_m2=decimal(predio) or Decimal(0),
            numero_viviendas=viviendas,
            superficie_edificada_m2=decimal(edificada),
            superficie_primer_piso_m2=decimal(primer_piso),
            altura_m=decimal(altura),
            numero_pisos=pisos,
        )
    except ErrorDominio as error:
        raise typer.BadParameter(str(error)) from error


@app.command()
def evaluar(
    lat: float = typer.Option(..., "--lat"),
    lon: float = typer.Option(..., "--lon"),
    predio: str = typer.Option(..., "--predio", help="Superficie del predio, en m²."),
    viviendas: int = typer.Option(0, "--viviendas", help="Número de unidades de vivienda."),
    edificada: str | None = typer.Option(None, "--edificada", help="Superficie edificada total."),
    primer_piso: str | None = typer.Option(
        None, "--primer-piso", help="Superficie del primer piso."
    ),
    altura: str | None = typer.Option(
        None, "--altura", help="Altura de edificación, en metros."
    ),
    pisos: int | None = typer.Option(None, "--pisos", help="Número de pisos."),
    salida_json: bool = typer.Option(False, "--json"),
) -> None:
    """Evalúa un proyecto contra la zona en que cae."""
    z = _resolver(lat, lon)
    raiz, _ = _rutas()
    reglas = cargar_reglas(raiz)
    p = _proyecto(predio, viviendas, edificada, primer_piso, altura, pisos)

    veredictos = evaluar_motor(p, z, reglas)
    hallazgos = verificar(p, z, reglas)
    cobertura = medir(veredictos)

    if salida_json:
        typer.echo(
            json.dumps(
                {
                    "zona": _zona_como_json(z),
                    "veredictos": [
                        {
                            "clave": v.clave,
                            "codigo": v.codigo.value,
                            "norma": v.cita.norma_id,
                            "articulo": v.cita.articulo,
                            "motivo": v.motivo,
                        }
                        for v in veredictos
                    ],
                    "hallazgos": [
                        {
                            "codigo": h.codigo.value,
                            "severidad": h.severidad.value,
                            "mensaje": h.mensaje,
                        }
                        for h in hallazgos
                    ],
                    "cobertura": {
                        "total": cobertura.total,
                        "concluidos": cobertura.concluidos,
                        "pendientes": cobertura.pendientes,
                        "por_motivo": {k: list(v) for k, v in cobertura.por_motivo.items()},
                    },
                },
                ensure_ascii=False,
            )
        )
        return

    typer.echo(f"Zona {z.codigo} — {z.nombre} ({z.comuna})")
    typer.echo("")
    typer.echo("VEREDICTOS")
    for v in veredictos:
        motivo = f"  [{v.motivo}]" if v.motivo else ""
        typer.echo(f"  {v.clave:26} {v.codigo.value:3}  {v.cita.articulo}{motivo}")
    typer.echo("")
    typer.echo("HALLAZGOS")
    if not hallazgos:
        typer.echo("  (ninguno)")
    for h in hallazgos:
        typer.echo(f"  {h.severidad.value:11} {h.codigo.value}: {h.mensaje}")
    typer.echo("")
    typer.echo(
        f"cobertura: {cobertura.concluidos} de {cobertura.total} parámetros "
        f"({cobertura.proporcion:.0%})"
    )
