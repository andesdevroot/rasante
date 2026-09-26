# task.md — cola de trabajo

**Metodología:** `doc/00-METODOLOGIA.md` · **Estado y blockers:** `doc/07-HANDOFF.md`

**Leyenda:** ⬜ pendiente · 🟦 en curso · ✅ hecha · ⛔ bloqueada

**Reglas.** Un commit por tarea completada. Si una tarea no cabe en un commit, **se divide en tareas
más pequeñas** — no se parte el commit. Nunca commitear con tests rojos. El handoff viaja en el
commit que cierra la tarea.

Las tareas completadas quedan resumidas en una línea; las pendientes llevan el detalle completo.

---

## Iteración 0 — Cimientos

| # | Tarea | Estado | Commit |
|---|---|---|---|
| T0.1 | Esqueleto del repositorio | ✅ | `6c55cd3` + `d8064b8` |
| T0.2 | Ingestor ArcGIS REST | ✅ | `20871c3` |
| T0.3 | Comparación de comunas → decisión A2 | 🟦 en curso | — |
| T0.4 | Test de integración contra la API real | ⬜ pendiente | — |

**T0.1 — Esqueleto del repositorio.** ✅ `pyproject.toml` con `uv`, layout `src/`, licencias
Apache-2.0 y CC-BY-4.0, ruff y mypy `--strict`, y el guardián de arquitectura
(`tests/test_arquitectura.py`) que verifica que `rasante.dominio` solo importa stdlib.

**T0.2 — Ingestor ArcGIS REST.** ✅ `geo/arcgis.py` con `listar_capas()` y `descargar_geojson()`,
paginación por `resultOffset` siguiendo `exceededTransferLimit`, y caché en disco. 9 tests con
fixtures grabadas, sin red.

### 🟦 T0.3 — Comparación de comunas candidatas → decisión A2

- **Objetivo:** elegir la comuna piloto con datos, no por intuición.
- **No lleva test** (tarea de análisis). Rompe el patrón TDD a propósito y se documenta así.
- **Método:** para Ñuñoa, Las Condes y Providencia: nº de zonas, calidad de `UPERM`/`UPROH`,
  `P_DO` poblado, y si la ordenanza con los parámetros numéricos es obtenible y legible.
- **Entregable:** `doc/04-DECISIONES.md`.
- **Estado:** análisis **hecho** y escrito. Recomendación: **Ñuñoa**. Falta que se confirme **A2**.
- **Hallazgo colateral:** `P_DO` es la publicación original, no la vigencia → corrige D5.
- **Commit:** `docs(repo): comparacion de comunas y decision A2 [T0.3]`

### ⬜ T0.4 — Test de integración contra la API real de MINVU

- **Objetivo:** detectar si MINVU cambia el esquema, mueve un servicio o altera `maxRecordCount`.
  Los 9 tests de T0.2 son offline (D9) y por diseño no pueden detectarlo.
- **Entregable:** `tests/integracion/test_arcgis_real.py`, marcado `@pytest.mark.integracion` y
  **excluido de la corrida por defecto**.
- **Qué verifica:** que `listar_capas` devuelve capas, y que el número de features descargados de
  una capa conocida coincide con el `count` que reporta la API.
- **Ojo con la fragilidad:** **no** comparar contra un literal fijo (1718). El PRC de una comuna
  cambia y el test se rompería sin que nada esté mal. Se compara contra el `count` consultado en el
  momento — así detecta truncamiento, que es lo que importa.
- **Aceptación:** `RASANTE_INTEGRACION=1 uv run pytest -m integracion` pasa; `uv run pytest` no lo
  ejecuta y sigue 100% offline.
- **Commit:** `test(geo): test de integracion contra la API real de MINVU [T0.4]`

---

## Iteración 1 — Vertical slice: coordenada → zona + 3 parámetros

Alcance en `doc/02-ALCANCE.md`. Parámetros: `cos`, `cus`, `altura_maxima`. Sin LLM, sin informes,
sin UI.

| # | Tarea | Estado |
|---|---|---|
| T1.1 | Dominio: modelos e invariante de cita | ⬜ |
| T1.2 | Dominio: motor de evaluación | ⬜ |
| T1.3 | Corpus: cargador y validación de YAML | ⬜ |
| T1.4 | Geo: reproyección e índice espacial | ⬜ |
| T1.5 | Resolución coordenada → zona | ⬜ |
| T1.6 | CLI | ⬜ |
| T1.7 | Corpus real de la comuna piloto | ⬜ |
| T1.8 | Validación contra predios reales | ⬜ |

### ⬜ T1.1 — Dominio: modelos e invariante de cita

- **Test primero:** (a) construir un `Veredicto` sin `Cita` levanta error; (b) `Decimal` se preserva
  sin pérdida en roundtrip; (c) `CodigoVeredicto` expone exactamente `C|NC|P|NP|PR` con los textos
  de la DDU 514.
- **Ojo (hallazgo de T0.3):** `cos` tiene **dos variantes** en las ordenanzas — "ocupación de suelo"
  y "ocupación de suelo **pisos superiores**". El modelo necesita un calificador, no un `cos` único.
  Resolver **A3** antes de cerrar esta tarea.
- **Entregable:** `dominio/modelos.py`.
- **Commit:** `feat(dominio): modelos de dominio e invariante de cita obligatoria [T1.1]`

### ⬜ T1.2 — Dominio: motor de evaluación

- **Test primero:** tabla de casos por parámetro — valor proyecto < norma → `C`; > norma → `NC`;
  parámetro en `desconocido`/`no_aplica` → `P`/`NP` **nunca `C`**; dato de proyecto faltante → `P`.
  Un test por artículo citado.
- **Entregable:** `dominio/motor.py` — `evaluar(proyecto, zona) -> list[Veredicto]`.
- **Aceptación:** el caso "norma desconocida" da `P`, jamás `C`. Es el invariante más importante.
- **Commit:** `feat(dominio): motor de evaluacion de parametros urbanisticos [T1.2]`

### ⬜ T1.3 — Corpus: cargador YAML

- **Test primero:** cargar una zona de fixture; esquema inválido (falta `procedencia`, falta `cita`,
  `unidad` desconocida) levanta error con mensaje claro.
- **Ojo (hallazgo de T0.3):** las ordenanzas escriben **coma decimal** (`0,6`, `3,6`). Si el cargador
  no lo maneja, `0,6` se vuelve `6`. Debe exigir separador decimal explícito y tener un test para
  `"0,6"` y `"0.6"`.
- **Entregable:** `corpus/cargador.py` + `corpus/esquema.py`.
- **Aceptación:** un YAML sin `hash_fuente` o sin `cita` por parámetro es rechazado.
- **Commit:** `feat(corpus): cargador y validacion de esquema de zonas [T1.3]`

### ⬜ T1.4 — Geo: reproyección e índice espacial

- **Test primero:** punto dentro de polígono sintético conocido → zona; punto fuera → `None`;
  verificar que EPSG:4326 → 3857 ubica un punto de Santiago en el rango esperado (cordura con
  tolerancia).
- **Entregable:** `geo/indices.py` — `IndiceZonas.buscar(lat, lon) -> str | None`.
- **Commit:** `feat(geo): reproyeccion e indice espacial point-in-polygon [T1.4]`

### ⬜ T1.5 — Resolución de zona

- **Test primero:** coordenada conocida → `Zona` con parámetros del corpus; coordenada sin zona →
  `SinZonaError`; zona en el PRC pero ausente del corpus → `ZonaSinCorpusError`. Son dos fallos
  operacionales **distintos** y no deben confundirse.
- **Entregable:** `geo/resolver.py`.
- **Commit:** `feat(geo): resolucion coordenada -> zona del corpus [T1.5]`

### ⬜ T1.6 — CLI

- **Test primero:** invocación con `typer.testing.CliRunner`. `rasante zona --lat --lon` imprime
  código y nombre de zona; salida `--json` con esquema estable; código de salida distinto de cero en
  los dos errores de T1.5.
- **Entregable:** `cli.py`.
- **Aceptación:** `uv run rasante zona --lat -33.45 --lon -70.61 --json` devuelve JSON válido.
- **Commit:** `feat(cli): comandos zona y evaluar con salida JSON [T1.6]`

### ⬜ T1.7 — Corpus real de la comuna piloto

- **Bloqueada por A2.** Entregable: 3–5 zonas de la comuna piloto con parámetros extraídos **a mano**
  de la ordenanza, revisados y citados. Empezar por las zonas que el texto de Ñuñoa ya expone
  limpiamente (`Z-1`…`Z-8` y variantes).
- **Test primero:** test de integración que carga las zonas reales y verifica que cada parámetro
  tiene cita y que la procedencia tiene `hash_fuente`.
- **Aceptación:** cada valor trazable a un artículo de la ordenanza. `estado: revisado` con
  `revisado_por` poblado. **Se presenta cada extracción para validación antes del commit.**
- **Commit:** `feat(corpus): zonas iniciales de <comuna> con parametros citados [T1.7]`

### ⬜ T1.8 — Validación contra predios reales

- **Objetivo:** cerrar la iteración 1 con evidencia. Metodología y métrica en `doc/05-VALIDACION.md`.
- **Entregable:** `doc/` con precisión y recall sobre N expedientes reales ya aprobados.
- **Nota:** sin esto la iteración **no se declara cerrada**.
- **Commit:** `docs: validacion de la iteracion 1 contra predios reales [T1.8]`
