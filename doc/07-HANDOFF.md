# 07 — Handoff

Documento vivo. Estado **real**, no aspiracional. Se actualiza en el commit que cierra cada tarea
(`00-METODOLOGIA.md`).

---

## Estado actual

**Iteración 0 — Cimientos: CERRADA.** Las cuatro tareas hechas (T0.1, T0.2, T0.3, T0.4).

| | |
|---|---|
| Tarea en curso | ninguna. Siguiente: **T1.1** |
| Código | `src/rasante/geo/arcgis.py` (ingestor ArcGIS con paginación y caché) · frontera de capas · tooling |
| Tests | **15 verdes** offline · **3 de integración** contra la API real, excluidos por defecto |
| Gate | `pytest` verde, sin saltados · `ruff` limpio · `mypy --strict` limpio |
| Árbol git | limpio — todo commiteado |

Reestructuración a `doc/` aplicada el 2026-09-26: `01-VISION.md`, `03-DISENO.md`,
`04-DECISIONES.md` y `07-HANDOFF.md` vienen de `docs/RASANTE-plan-desarrollo.md`, `design.md`,
`docs/decision-comuna.md` y `handoff.md`.

## Último commit

```
[T0.3]    docs: cierra T0.3, registra A2 y A3 y actualiza el alcance a 4 parametros
def1a5d  docs: corrige los hashes invalidados por el squash de T0.1
[T0.4]    test(geo): test de integracion contra la API real de MINVU
c426875  docs: reestructura la documentacion a doc/ y actualiza la metodologia
9538bd1  docs: agrega T0.4 (test de integracion contra la API real)
6420178  feat(geo): ingestor ArcGIS REST con paginacion y cache en disco [T0.2]
64bdcdd  chore(repo): esqueleto, uv, licencias y guardian de arquitectura [T0.1]
e02ff7c  docs: spec inicial (design, task, handoff)
```

Una tarea, un commit: T0.1 quedó consolidada en `64bdcdd` tras el squash.

## Siguiente tarea

**T1.1 — Dominio: modelos e invariante de cita** (`src/rasante/dominio/modelos.py`).

Desbloqueada: **A2 y A3 están cerradas**. Es la primera tarea de la iteración 1 y fija el modelo de
dominio, del que dependen T1.2 a T1.6.

## Blockers

| Blocker | Detalle |
|---|---|
| **Titularidad normativa** | Sin verificar el artículo de la Ley 17.336 que excluye textos oficiales de protección. Bloquea fijar la licencia definitiva del corpus, **no el desarrollo** |

Sin blockers de alcance: A1, A2 y A3 están cerradas.

## Decisiones recientes

| Fecha | Decisión |
|---|---|
| 2026-09-26 | **A1 cerrada:** la iteración 1 entra por **coordenada** (lat/lon), no por rol ni CIP |
| 2026-09-26 | Stack confirmado: **Python 3.14 + `uv` + pytest**. El `go test` de la metodología era boilerplate de plantilla |
| 2026-09-26 | Estructura `doc/` numérica (00–07) fijada. `task.md` pasa a ser cola con estado, en la raíz |
| 2026-09-26 | **`P_DO` no es la vigencia**: es la publicación original del instrumento. Corrige D5 en `03-DISENO.md` |
| 2026-09-26 | **A2 cerrada: comuna piloto = Ñuñoa** — por el texto refundido de la ordenanza (jun 2025) con parámetros extraíbles, no por la antigüedad del PRC |
| 2026-09-26 | **A3 cerrada: ambas.** La iteración 1 evalúa **4 parámetros**. `densidad` es la única regla **derivada** y obliga a que `Proyecto` tenga campos reales y a que `Parametro` lleve `calificador` |
| 2026-09-26 | **La clave de parámetro es compuesta** (`cos.primer_piso`). Con variantes, una clave por `id` produce claves YAML duplicadas y PyYAML descarta una **en silencio**, perdiendo una regla |
| 2026-09-26 | **Squash de T0.1** (`64bdcdd`), pedido por el usuario tras la regla "un commit por tarea". Reescribió todos los hashes posteriores; corregidos en `def1a5d` |
| 2026-09-26 | **Tests de integración excluidos por `addopts`, no por `skip`.** El DoD exige "sin tests saltados": se deseleccionan (`-m 'not integracion'`) en vez de saltarse. El `-m` de la línea de comandos sobreescribe el de `addopts`, verificado |

Detalle completo de cada una en `04-DECISIONES.md`.
