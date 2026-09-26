# rasante — task.md

**v0.1 · 2026-09-26**

Convenciones y alcance en `design.md`. Cada tarea = **1 commit atómico**, con **TDD**
(test que falla primero).

## Definition of Done (toda tarea)

1. Test escrito **antes** de la implementación, y se verificó que falla.
2. `uv run pytest` en verde, sin tests saltados.
3. `uv run ruff check` y `uv run mypy src` limpios.
4. Sin `float` en rutas normativas.
5. `handoff.md` actualizado (bitácora + próximo paso).
6. **Consultado y aprobado antes de commitear.**

Formato de commit: `tipo(ámbito): descripción [T<n>.<m>]`
Ámbitos: `dominio`, `corpus`, `geo`, `cli`, `repo`, `docs`.

---

## Iteración 0 — Cimientos

### T0.1 — Esqueleto del repositorio
- **Objetivo:** repo instalable con `uv`, layout `src/`, licencias, tooling de calidad.
- **Test primero:** `test_arquitectura.py` — falla si algún módulo de `rasante.dominio`
  importa algo fuera de la stdlib. Es el guardián de D2.
- **Entregable:** `pyproject.toml`, `src/rasante/{dominio,corpus,geo}/__init__.py`,
  `LICENSE` (Apache-2.0), `LICENSE-CORPUS` (CC-BY-4.0), config de ruff/mypy/pytest.
- **Aceptación:** `uv run pytest` ejecuta y el test de arquitectura pasa.
- **Commit:** `chore(repo): esqueleto, uv, licencias y guardián de arquitectura [T0.1]`

### T0.2 — Ingestor ArcGIS REST
- **Objetivo:** bajar catálogo y capas PRC de MINVU a GeoJSON en disco, cacheado.
- **Test primero:** con respuestas HTTP **grabadas** en `tests/fixtures/` (no red en tests):
  parsear el catálogo, extraer capas, y verificar que el GeoJSON cacheado se relee idéntico.
- **Entregable:** `src/rasante/geo/arcgis.py` — `listar_capas()`, `descargar_capa()`.
- **Aceptación:** descarga real de `IPT/PRC_RM_Norte` capa 11 a `cache/`, y los tests corren
  sin red.
- **Nota:** los fixtures se graban una vez contra la API real; los tests quedan offline (D9).
- **Commit:** `feat(geo): ingestor ArcGIS REST con caché en disco [T0.2]`

### T0.3 — Comparación de comunas candidatas → decisión (A2)
- **Objetivo:** elegir la comuna piloto con datos, no por intuición.
- **No lleva test** (tarea de análisis). Rompe el patrón TDD a propósito y se documenta así.
- **Método:** para Ñuñoa, Las Condes y Providencia: nº de zonas, % con `UPERM`/`UPROH`
  utilizables, si `P_DO` está poblado, y si la ordenanza con los parámetros numéricos es
  obtenible y legible.
- **Entregable:** `docs/decision-comuna.md` con la tabla y la decisión + justificación.
- **Aceptación:** decisión tomada y registrada. **Se te consulta antes de fijarla.**
- **Commit:** `docs(repo): comparación de comunas candidatas y decisión [T0.3]`

---

## Iteración 1 — Vertical slice: coordenada → zona + 3 parámetros

Alcance: `cos`, `cus`, `altura_maxima` (A3). Sin LLM, sin informes, sin UI.

### T1.1 — Dominio: modelos e invariante de cita
- **Test primero:** (a) construir un `Veredicto` sin `Cita` levanta error; (b) `Decimal` se
  preserva sin pérdida en roundtrip; (c) `CodigoVeredicto` expone exactamente
  `C|NC|P|NP|PR` con los textos de la DDU 514.
- **Entregable:** `dominio/modelos.py`.
- **Commit:** `feat(dominio): modelos de dominio e invariante de cita obligatoria [T1.1]`

### T1.2 — Dominio: motor de evaluación
- **Test primero:** tabla de casos por parámetro — valor proyecto < norma → `C`; > norma →
  `NC`; parámetro en `desconocido`/`no_aplica` → `P`/`NP` **nunca `C`**; dato de proyecto
  faltante → `P`. Un test por artículo citado.
- **Entregable:** `dominio/motor.py` — `evaluar(proyecto, zona) -> list[Veredicto]`.
- **Aceptación:** el caso "norma desconocida" da `P`, jamás `C`. Es el invariante más importante.
- **Commit:** `feat(dominio): motor de evaluación de parámetros urbanísticos [T1.2]`

### T1.3 — Corpus: cargador YAML
- **Test primero:** cargar una zona de fixture; esquema inválido (falta `procedencia`,
  falta `cita`, `unidad` desconocida) levanta error con mensaje claro.
- **Entregable:** `corpus/cargador.py` + `corpus/esquema.py`.
- **Aceptación:** un YAML sin `hash_fuente` o sin `cita` por parámetro es rechazado.
- **Commit:** `feat(corpus): cargador y validación de esquema de zonas [T1.3]`

### T1.4 — Geo: reproyección e índice espacial
- **Test primero:** punto dentro de polígono sintético conocido → código de zona; punto fuera
  → `None`; verificar que EPSG:4326 → 3857 ubica un punto de Santiago en el rango esperado
  (test de cordura con tolerancia).
- **Entregable:** `geo/indices.py` — `IndiceZonas.buscar(lat, lon) -> str | None`.
- **Commit:** `feat(geo): reproyección e índice espacial point-in-polygon [T1.4]`

### T1.5 — Resolución de zona
- **Test primero:** coordenada conocida → `Zona` con parámetros del corpus; coordenada sin
  zona → error explícito `SinZonaError`; zona en el PRC pero ausente del corpus → `ZonaSinCorpusError`
  (distinto de "sin zona": son dos fallos operacionales diferentes).
- **Entregable:** `geo/resolver.py`.
- **Commit:** `feat(geo): resolución coordenada → zona del corpus [T1.5]`

### T1.6 — CLI
- **Test primero:** invocación con `typer.testing.CliRunner`. `rasante zona --lat --lon`
  imprime código y nombre de zona; salida `--json` con esquema estable; código de salida
  distinto de cero en los dos errores de T1.5.
- **Entregable:** `cli.py`.
- **Aceptación:** `uv run rasante zona --lat -33.45 --lon -70.61 --json` devuelve JSON válido.
- **Commit:** `feat(cli): comandos zona y evaluar con salida JSON [T1.6]`

### T1.7 — Corpus real de la comuna piloto
- **Test primero:** test de integración que carga las zonas reales del corpus y verifica que
  cada parámetro tiene cita y que la procedencia tiene `hash_fuente`.
- **Entregable:** 3–5 zonas de la comuna piloto con parámetros extraídos a mano de la
  ordenanza, revisados y citados.
- **Aceptación:** cada valor trazable a un artículo de la ordenanza. `estado: revisado` con
  `revisado_por` poblado. **Se te presenta cada extracción para que la valides antes del commit.**
- **Commit:** `feat(corpus): zonas iniciales de <comuna> con parámetros citados [T1.7]`

---

## Cierre de iteración 1

- **T1.8 — Validación contra predios reales:** correr el CLI sobre N predios conocidos y
  contrastar zona/parámetros contra el CIP real. Entregable: `docs/validacion-iter1.md`.
  Sin esto la iteración no se declara cerrada.

---

## Backlog (iteración 2+)

| Iteración | Contenido |
|---|---|
| 2 | Ingesta de CIP y Formularios Únicos Nacionales · extracción con `deepseek-flash` visión · citas por ID de regla |
| 3 | Emisión del Formato Tipo DOCX/PDF (DDU 514) con veredictos y narrativa del Art. 116 Ley 21.718 |
| 4 | Checklist de admisibilidad Ley 21.826 (5 días hábiles) |
| 5 | UI local SvelteKit · instaladores Nuitka/Briefcase · demo pública FastAPI |
| 6 | Rasantes, densidad, estacionamientos, distanciamientos · 2ª y 3ª comuna |
