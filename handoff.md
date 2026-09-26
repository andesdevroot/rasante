# rasante — handoff.md

Documento vivo. Estado real, no aspiracional. Se actualiza en **cada** commit.

**Última actualización:** 2026-09-26 · **Iteración:** 0 · **Commit:** 2 — uv.lock (pendiente de aprobación)

---

## Estado

| | |
|---|---|
| Iteración en curso | **0 — Cimientos** |
| Tarea en curso | ninguna — T0.1 cerrada. Siguiente: **T0.2** |
| Código escrito | Esqueleto: `pyproject.toml`, `src/rasante/{dominio,corpus,geo}`, licencias, `README.md` |
| Tests | **6 pasando** en `tests/test_arquitectura.py`. `ruff` y `mypy` limpios |
| Bloqueado por | nada — listo para T0.2 |

### Hecho

- Investigación de fuentes verificada en vivo: servicios ArcGIS REST de MINVU con los PRC de
  todas las regiones (`geoide.minvu.cl/server/rest/services/IPT`), consultables en GeoJSON.
- Verificado que los parámetros numéricos **no** vienen en los atributos ArcGIS: solo
  geometría, `ZONA`, `UPERM`, `UPROH`, `P_DO`. Los números hay que extraerlos de la ordenanza.
- Verificado el formato oficial de salida: Circular DDU 514, con leyenda `(C)/(NC)/(P)/(NP)/(PR)`.
- Verificado el dolor del usuario en la consulta pública de MINVU (31 págs).
- Verificados precios y capacidades de DeepSeek (`deepseek-flash`: 1M contexto, visión,
  $0.15/M input off-peak, $0.003/M cache hit).

### No hecho

Todo el código. Nada de la iteración 0 ni 1.

---

## Decisiones

**Cerradas:** D1–**D11** en `design.md` §2, y **A1**. Nombres: `rasante`. Alcance de iteración 1:
coordenada → zona + `cos`/`cus`/`altura_maxima`. Repo: workspace actual. Se consulta antes de
cada commit.

**Abiertas (requieren tu input):**

- **A2** — Comuna piloto: se decide en T0.3 con datos comparados de Ñuñoa, Las Condes y Providencia.
- **A3** — Tercer parámetro: `altura_maxima` (recomendado) vs `densidad`.
- **Legal** — Verificar el artículo de la Ley 17.336 que excluye textos oficiales del Estado
  de protección, antes de definir la licencia definitiva del corpus.

---

## Cómo correr

`uv 0.12.19` instalado en `~/.local/bin`. Python 3.14.3.

**Dentro del sandbox de DSH**, `uv` necesita su caché dentro del workspace: su default
(`~/.cache/uv`) queda fuera y falla con `Operation not permitted`.

```bash
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR="$PWD/.uv-cache"   # solo necesario dentro del sandbox

uv sync
uv run pytest
uv run ruff check .
uv run mypy src
```

Fuera del sandbox, `UV_CACHE_DIR` no hace falta: `uv sync && uv run pytest` basta.

---

## Convenciones de trabajo

1. **TDD**: el test se escribe y se verifica que falla, antes de implementar.
2. **1 tarea de `task.md` = 1 commit atómico.**
3. **Se consulta antes de cada commit.** No se commitea sin aprobación.
4. `handoff.md` se actualiza en el mismo commit de la tarea.
5. `rasante.dominio` no importa nada fuera de la stdlib. Hay un test que lo vigila.
6. Nunca `float` en rutas normativas.
7. Un dato desconocido se propaga como `(P)`, **nunca** como `(C)`.

---

## Bitácora

| Fecha | Commit | Qué |
|---|---|---|
| 2026-09-26 | — | Investigación de fuentes (ArcGIS MINVU, DDU 514, precios DeepSeek). Plan de mercado en `docs/RASANTE-plan-desarrollo.md` |
| 2026-09-26 | **0** | Spec inicial: `design.md`, `task.md`, `handoff.md`. A1 cerrada (entrada por coordenada) |
| 2026-09-26 | **1** | T0.1: esqueleto del repo. Guardián de D2 en `tests/test_arquitectura.py` (test rojo → verde). 6 tests, ruff y mypy limpios |
| 2026-09-26 | **2** | `uv` instalado (0.12.19) y `uv.lock` versionado. Caché de uv movida dentro del workspace por el sandbox |

---

## Próximo paso

**T0.2 — Ingestor ArcGIS REST** (`geo/arcgis.py`): `listar_capas()` y `descargar_capa()`, con
caché en disco y fixtures HTTP grabadas, para que los tests corran sin red.

Pendiente de tu input: **A2** (se resuelve con datos en T0.3) y **A3** (altura_maxima vs densidad).
