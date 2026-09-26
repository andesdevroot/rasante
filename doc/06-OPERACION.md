# 06 — Operación

## Entorno verificado

| | |
|---|---|
| Python | 3.14.3 |
| `uv` | 0.12.19 (`~/.local/bin`) |
| Gestor de deps | `uv` con `pyproject.toml` + `uv.lock` versionado |
| Calidad | `ruff` (E, F, I, UP, B, SIM) · `mypy --strict` sobre `src` · `pytest` |

## Correr

```bash
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR="$PWD/.uv-cache"   # solo dentro del sandbox de DSH

uv sync
uv run pytest
uv run ruff check .
uv run mypy src
```

**Nota del sandbox.** `uv` usa `~/.cache/uv` por defecto; dentro del sandbox de DSH esa ruta queda
fuera del workspace y `uv run` falla con `Operation not permitted`. Se fija `UV_CACHE_DIR` dentro
del proyecto (`.uv-cache/`, ignorado por git). **Fuera del sandbox no hace falta**: basta
`uv sync && uv run pytest`.

## Tests de integración

```bash
RASANTE_INTEGRACION=1 uv run pytest -m integracion
```

Ver `05-VALIDACION.md`.

## Fuentes externas

| Fuente | Uso |
|---|---|
| `https://geoide.minvu.cl/server/rest/services/IPT` | PRC de todas las regiones como ArcGIS REST, consultable en GeoJSON |
| `https://www.minvu.gob.cl/elementos-tecnicos/decretos/d-s-n47-1992-ordenanza-general-de-urbanismo-y-construccione/` | **OGUC consolidada** (D.S. N°47). El PDF vigente declara el decreto que lo consolida: hoy *D.D. N°5, D.O. 22-05-2026* (rev. 15.09.2026). **577 págs / 4,4 MB** |
| `https://www.bcn.cl/leychile` | LGUC (DFL 458), Ley 21.826, Ley 21.718, Ley 17.336. Ojo: las páginas se renderizan por JS, `web_fetch` devuelve solo el título |
| `https://www.minvu.gob.cl/elementos-tecnicos/formularios/grupo-15-...` | Formato Tipo del informe del revisor independiente (Circular DDU 514) |
| `https://api.deepseek.com` | LLM (iteración 2+). `deepseek-flash`: 1M contexto, visión, cache hit $0.003/M |

## Licencias

- **Código:** Apache-2.0 (`LICENSE`)
- **Corpus normativo:** CC-BY-4.0 (`LICENSE-CORPUS`), con atribución a la fuente municipal

**Pendiente legal:** verificar el artículo de la Ley 17.336 que excluye los textos oficiales del
Estado de protección, antes de fijar la licencia definitiva del corpus.

**Trampa conocida:** PyMuPDF es **AGPL-3.0** y contamina Apache-2.0 (su cláusula *affero* alcanza
también a servicios en red). Usar `pypdf` (BSD-3) o `pdfminer.six` (MIT).

## Distribución (iteraciones 4–5, no implementado)

Instaladores vía Nuitka + Briefcase · `uv tool install rasante` · demo pública sin instalación
servida por un FastAPI chico y con límite de tasa.
