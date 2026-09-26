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
| T0.1 | Esqueleto del repositorio | ✅ | `64bdcdd` |
| T0.2 | Ingestor ArcGIS REST | ✅ | `6420178` |
| T0.3 | Comparación de comunas → decisión A2 | ✅ | `[T0.3]` |
| T0.4 | Test de integración contra la API real | ✅ | `[T0.4]` |

**T0.1 — Esqueleto del repositorio.** ✅ `pyproject.toml` con `uv`, layout `src/`, licencias
Apache-2.0 y CC-BY-4.0, ruff y mypy `--strict`, y el guardián de arquitectura
(`tests/test_arquitectura.py`) que verifica que `rasante.dominio` solo importa stdlib.

**T0.2 — Ingestor ArcGIS REST.** ✅ `geo/arcgis.py` con `listar_capas()` y `descargar_geojson()`,
paginación por `resultOffset` siguiendo `exceededTransferLimit`, y caché en disco. 9 tests con
fixtures grabadas, sin red.

**T0.3 — Comparación de comunas → decisión A2.** ✅ Análisis con datos en vivo de Ñuñoa, Las Condes
y Providencia, registrado en `doc/04-DECISIONES.md`. **A2 cerrada: Ñuñoa**, por el texto refundido
de la ordenanza (jun 2025) con parámetros extraíbles. Hallazgo colateral: `P_DO` es la publicación
original, no la vigencia → nueva D12. No lleva test: es tarea de análisis.

**T0.4 — Test de integración contra la API real.** ✅ `tests/integracion/test_arcgis_real.py`,
marcado `@pytest.mark.integracion` y excluido por defecto vía `addopts`. Verifica que el servicio
expone capas y que el conteo descargado coincide con el `count` de la API — detecta truncamiento.
3 tests contra la API real; la suite por defecto sigue en 15, sin saltados.

---

## Iteración 1 — Vertical slice: coordenada → zona + 4 parámetros

Alcance en `doc/02-ALCANCE.md`. Parámetros: `cos`, `cus`, `altura_maxima` y **`densidad`**
(A3 = ambas). Sin LLM, sin informes, sin UI.

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
- **Ojo (A3 cerrada):** el modelo necesita **`calificador`** en `Parametro`. `cos` tiene dos
  variantes ("ocupación de suelo" `0,6` y "pisos superiores" `0,4`, ambas en la misma zona de
  Ñuñoa), y `densidad` distingue **bruta** de **neta**. Sin calificador, dos reglas colisionan en
  la misma clave.
- **Ojo (diseño):** la **clave del mapping es compuesta** (`cos.primer_piso`). Una clave por `id`
  produce claves duplicadas en el YAML y el parser descarta una **en silencio**, perdiendo una
  regla. Ver `doc/03-DISENO.md`.
- **Entregable:** `dominio/modelos.py`.
- **Commit:** `feat(dominio): modelos de dominio e invariante de cita obligatoria [T1.1]`

### ⬜ T1.2 — Dominio: motor de evaluación

- **Test primero:** tabla de casos por parámetro — valor proyecto < norma → `C`; > norma → `NC`;
  parámetro en `desconocido`/`no_aplica` → `P`/`NP` **nunca `C`**; dato de proyecto faltante → `P`.
  Un test por artículo citado.
- **Ojo (A3 cerrada):** `densidad` es la **única regla derivada**, no una comparación directa:
  `numero_viviendas / (superficie_predio_m2 / 10_000)` en viv/ha. Los casos de test deben cubrir el
  cálculo, no solo la comparación. Es lo que obliga a que `evaluar` reciba el `Proyecto` completo.
- **Entregable:** `dominio/motor.py` — `evaluar(proyecto, zona) -> list[Veredicto]`.
- **Aceptación:** el caso "norma desconocida" da `P`, jamás `C`. Es el invariante más importante.
- **Commit:** `feat(dominio): motor de evaluacion de parametros urbanisticos [T1.2]`

### ⬜ T1.3 — Corpus: cargador YAML

- **Test primero:** cargar una zona de fixture; esquema inválido (falta `procedencia`, falta `cita`,
  `unidad` desconocida) levanta error con mensaje claro.
- **Ojo (hallazgo de T0.3):** las ordenanzas escriben **coma decimal** (`0,6`, `3,6`). Si el cargador
  no lo maneja, `0,6` se vuelve `6`. Debe exigir separador decimal explícito y tener un test para
  `"0,6"` y `"0.6"`.
- **Ojo (A3 cerrada):** debe **rechazar claves de parámetro duplicadas**. Con `cos` y `densidad`
  teniendo variantes, un YAML con dos claves `cos` es válido sintácticamente y pierde una regla sin
  avisar. Test explícito para eso — PyYAML no lo detecta por defecto.
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

- **Desbloqueada: A2 = Ñuñoa.** Entregable: 3–5 zonas con los **4 parámetros** extraídos **a mano**
  de la ordenanza, revisados y citados. Empezar por las zonas que el texto refundido ya expone
  limpiamente (`Z-1`…`Z-8` y variantes).
- **Ojo (A3):** para `densidad` hay que declarar si la zona usa densidad **bruta** o **neta**. Sin
  eso el cálculo es ambiguo y el veredicto queda sin fundamento. Lo mismo con el calificador de `cos`.
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
