"""Tests del troceador determinista de la OGUC (T0.5).

Corren **sin red** y sin LLM: el troceado es una función pura sobre texto (D9 y D13).
La verificación contra el texto real de la OGUC (577 págs) se hace aparte, contra `cache/`.

`extraer_texto` es un envoltorio delgado sobre `pypdf` y no se unit-testea con un PDF real —
eso se verifica contra la fuente. Lo que sí se testea es que falle de forma explícita ante
una entrada que no es un PDF.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from rasante.corpus.ingesta import (
    Articulo,
    ErrorIngesta,
    descargar_fuente,
    extraer_texto,
    indexar,
    trocear,
)

# Texto sintético que imita el formato real: encabezados a INICIO DE LÍNEA.
OGUC = """TÍTULO 1. DISPOSICIONES GENERALES

Artículo 1.1.1. Las disposiciones de esta Ordenanza se aplicarán en todo el territorio nacional.

Artículo 1.1.2. Definiciones. Los siguientes vocablos tienen en esta Ordenanza el significado
que se expresa:
"Altura de edificación": la distancia vertical, expresada en metros.

Artículo 1.1.3. Otro artículo cualquiera, con su cuerpo propio.

Artículo 2.1.23. Si el instrumento fija altura en pisos, se multiplicará 3,50 m por el número
de pisos.
"""


# --- trocear: lo básico ---


def test_trocear_devuelve_los_articulos_en_orden_documental() -> None:
    arts = trocear(OGUC)
    assert [a.numero for a in arts] == ["1.1.1", "1.1.2", "1.1.3", "2.1.23"]


def test_indexar_permite_buscar_por_numero() -> None:
    idx = indexar(trocear(OGUC))
    assert idx["1.1.2"].texto.startswith("Definiciones.")
    assert idx["2.1.23"].texto.startswith("Si el instrumento fija altura")


def test_articulo_ausente_no_esta_en_el_indice() -> None:
    idx = indexar(trocear(OGUC))
    assert "9.9.9" not in idx
    assert idx.get("9.9.9") is None


# --- la corrección que importa: las fronteras ---


def test_el_cuerpo_no_se_come_al_siguiente() -> None:
    """El fallo silencioso más grave: un artículo que absorbe al siguiente."""
    idx = indexar(trocear(OGUC))
    cuerpo = idx["1.1.2"].texto
    assert "Artículo 1.1.3" not in cuerpo
    assert "Otro artículo cualquiera" not in cuerpo


def test_el_ultimo_articulo_llega_hasta_el_final() -> None:
    idx = indexar(trocear(OGUC))
    assert "número" in idx["2.1.23"].texto
    assert "de pisos." in idx["2.1.23"].texto


# --- variantes reales del vocablo ---


@pytest.mark.parametrize("vocablo", ["Artículo", "Articulo", "ARTÍCULO", "ARTICULO"])
def test_tolera_variantes_de_caso_y_tilde(vocablo: str) -> None:
    arts = trocear(f"{vocablo} 3.4.5. Cuerpo del artículo.\n")
    assert [a.numero for a in arts] == ["3.4.5"]


def test_tolera_espaciado_irregular() -> None:
    arts = trocear("Artículo    7.8.9.   Cuerpo.\n")
    assert [a.numero for a in arts] == ["7.8.9"]


def test_tolera_encabezado_sin_punto_tras_el_numero() -> None:
    arts = trocear("Artículo 4.5.6 Cuerpo sin punto.\n")
    assert [a.numero for a in arts] == ["4.5.6"]


# --- falsos positivos que SÍ aparecen en el texto real ---


def test_referencia_en_minuscula_al_inicio_de_linea_no_es_encabezado() -> None:
    """Caso real: un salto de línea deja 'artículo 116 Bis A)' al inicio de línea."""
    texto = (
        "Artículo 5.1.1. Se refiere a las infraestructuras sanitarias a que se refiere el\n"
        "artículo 116 Bis A) de la Ley General, en los que podrá actuar el arquitecto.\n"
    )
    assert [a.numero for a in trocear(texto)] == ["5.1.1"]


def test_referencia_en_linea_no_es_encabezado() -> None:
    texto = "Artículo 1.2.3. Conforme a lo dispuesto en el Artículo 4.5.6. de esta Ordenanza.\n"
    assert [a.numero for a in trocear(texto)] == ["1.2.3"]


def test_numero_sin_punto_no_es_articulo_de_la_oguc() -> None:
    """'Artículo 116' es de la LGUC, no de la OGUC: sus artículos siempre llevan punto."""
    assert trocear("Artículo 116. Texto de la Ley General.\n") == []


# --- artículos 'bis' (hay 18 en la OGUC real) ---


@pytest.mark.parametrize("sufijo", ["bis", "BIS", "Bis"])
def test_detecta_articulos_bis(sufijo: str) -> None:
    arts = trocear(f"Artículo 2.2.4 {sufijo}. Cuerpo del bis.\n")
    assert [a.numero for a in arts] == ["2.2.4 bis"]


def test_detecta_bis_en_el_formato_real_de_la_oguc() -> None:
    """El formato real lleva punto ANTES de bis y espacios dobles: `Artículo  2.1.3. bis.`"""
    arts = trocear("Artículo  2.1.3. bis.  En los nuevos planes reguladores.\n")
    assert [a.numero for a in arts] == ["2.1.3 bis"]
    assert arts[0].texto == "En los nuevos planes reguladores."


def test_un_bis_y_su_base_son_articulos_distintos() -> None:
    arts = trocear("Artículo 2.1.3. Base.\n\nArtículo 2.1.3. bis. El bis.\n")
    assert [a.numero for a in arts] == ["2.1.3", "2.1.3 bis"], (
        "si el bis se etiqueta como su base, colisiona con el articulo base y se pierde una regla"
    )


# --- duplicados: no perder nada en silencio ---


def test_trocear_preserva_los_duplicados() -> None:
    arts = trocear("Artículo 2.1.3. Primero.\n\nArtículo 2.1.3. Repetido.\n")
    assert len(arts) == 2, "un duplicado no debe desaparecer sin dejar rastro"


def test_indexar_se_queda_con_el_primero() -> None:
    idx = indexar(trocear("Artículo 2.1.3. Primero.\n\nArtículo 2.1.3. Repetido.\n"))
    assert idx["2.1.3"].texto.startswith("Primero.")


def test_articulo_guarda_su_offset() -> None:
    arts = trocear(OGUC)
    assert all(isinstance(a, Articulo) for a in arts)
    assert [a.inicio for a in arts] == sorted(a.inicio for a in arts)


# --- descarga de la fuente ---


def test_descargar_fuente_escribe_el_archivo(tmp_path: Path) -> None:
    transporte = httpx.MockTransport(lambda _: httpx.Response(200, content=b"%PDF-1.7 falso"))
    destino = tmp_path / "oguc.pdf"
    with httpx.Client(transport=transporte) as cliente:
        resultado = descargar_fuente("https://ejemplo.cl/oguc.pdf", destino, cliente=cliente)
    assert resultado == destino
    assert destino.read_bytes().startswith(b"%PDF")


def test_descargar_fuente_usa_la_cache(tmp_path: Path) -> None:
    llamadas: list[str] = []

    def handler(peticion: httpx.Request) -> httpx.Response:
        llamadas.append(str(peticion.url))
        return httpx.Response(200, content=b"%PDF-1.7")

    destino = tmp_path / "ya.pdf"
    destino.write_bytes(b"%PDF-1.7 cacheado")
    with httpx.Client(transport=httpx.MockTransport(handler)) as cliente:
        descargar_fuente("https://ejemplo.cl/oguc.pdf", destino, cliente=cliente)

    assert llamadas == [], "no debe tocar la red si el destino ya existe"
    assert destino.read_bytes() == b"%PDF-1.7 cacheado"


def test_descargar_fuente_falla_con_error_explicito(tmp_path: Path) -> None:
    transporte = httpx.MockTransport(lambda _: httpx.Response(404))
    with (
        httpx.Client(transport=transporte) as cliente,
        pytest.raises(ErrorIngesta, match="404"),
    ):
        descargar_fuente("https://ejemplo.cl/oguc.pdf", tmp_path / "x.pdf", cliente=cliente)


def test_descargar_fuente_no_deja_archivo_a_medias(tmp_path: Path) -> None:
    transporte = httpx.MockTransport(lambda _: httpx.Response(500))
    destino = tmp_path / "parcial.pdf"
    with httpx.Client(transport=transporte) as cliente, pytest.raises(ErrorIngesta):
        descargar_fuente("https://ejemplo.cl/oguc.pdf", destino, cliente=cliente)
    assert not destino.exists()


# --- extraccion de texto ---


def test_extraer_texto_falla_explicito_si_no_es_pdf(tmp_path: Path) -> None:
    falso = tmp_path / "no-es-pdf.pdf"
    falso.write_text("esto no es un PDF", encoding="utf-8")
    with pytest.raises(ErrorIngesta, match="PDF"):
        extraer_texto(falso)
