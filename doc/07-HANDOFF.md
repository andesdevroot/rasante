# 07 — Handoff

Documento vivo. Estado **real**, no aspiracional. Se actualiza en el commit que cierra cada tarea
(`00-METODOLOGIA.md`).

---

## Estado actual

**Iteración 0 — Cimientos.** Tres tareas cerradas (T0.1, T0.2, T0.4). T0.3 abierta esperando A2.

| | |
|---|---|
| Tarea en curso | **T0.3** — análisis hecho, registrado en `04-DECISIONES.md` y commiteado. **Solo falta tu confirmación de A2** |
| Código | `src/rasante/geo/arcgis.py` (ingestor ArcGIS con paginación y caché) · frontera de capas · tooling |
| Tests | **15 verdes** offline · **3 de integración** contra la API real, excluidos por defecto |
| Gate | `pytest` verde, sin saltados · `ruff` limpio · `mypy --strict` limpio |
| Árbol git | limpio — todo commiteado |

Reestructuración a `doc/` aplicada el 2026-09-26: `01-VISION.md`, `03-DISENO.md`,
`04-DECISIONES.md` y `07-HANDOFF.md` vienen de `docs/RASANTE-plan-desarrollo.md`, `design.md`,
`docs/decision-comuna.md` y `handoff.md`.

## Último commit

```
[T0.4]    test(geo): test de integracion contra la API real de MINVU
c426875  docs: reestructura la documentacion a doc/ y actualiza la metodologia
9538bd1  docs: agrega T0.4 (test de integracion contra la API real)
6420178  feat(geo): ingestor ArcGIS REST con paginacion y cache en disco [T0.2]
64bdcdd  chore(repo): esqueleto, uv, licencias y guardian de arquitectura [T0.1]
e02ff7c  docs: spec inicial (design, task, handoff)
```

`64bdcdd` y `64bdcdd` son ambos T0.1 y **violan la regla "un commit por tarea"**. Pendiente decidir
si se squashan.

## Siguiente tarea

**Confirmar A2 y cerrar T0.3.** Con eso la iteración 0 queda cerrada y empieza la iteración 1.

**T1.1 está bloqueada por A3** (tercer parámetro: `altura_maxima` vs `densidad`): el modelo de
dominio depende de esa decisión.

## Blockers

| Blocker | Detalle |
|---|---|
| **A2 sin confirmar** | La comuna piloto está recomendada (Ñuñoa) pero **no fijada**. Bloquea T1.7 |
| **A3 sin confirmar** | Tercer parámetro: `altura_maxima` (recomendado) vs `densidad`. **Bloquea T1.1**, o sea el arranque de la iteración 1 |
| **Titularidad normativa** | Sin verificar el artículo de la Ley 17.336 que excluye textos oficiales de protección. Bloquea fijar la licencia definitiva del corpus, no el desarrollo |

**Deuda de higiene:** T0.1 quedó en dos commits (`64bdcdd`), lo que viola la regla "un
commit por tarea" de `00-METODOLOGIA.md`. Pendiente decidir si se squashan.

## Decisiones recientes

| Fecha | Decisión |
|---|---|
| 2026-09-26 | **A1 cerrada:** la iteración 1 entra por **coordenada** (lat/lon), no por rol ni CIP |
| 2026-09-26 | Stack confirmado: **Python 3.14 + `uv` + pytest**. El `go test` de la metodología era boilerplate de plantilla |
| 2026-09-26 | Estructura `doc/` numérica (00–07) fijada. `task.md` pasa a ser cola con estado, en la raíz |
| 2026-09-26 | **`P_DO` no es la vigencia**: es la publicación original del instrumento. Corrige D5 en `03-DISENO.md` |
| 2026-09-26 | **Comuna piloto recomendada: Ñuñoa** — por el texto refundido de la ordenanza (jun 2025) con parámetros extraíbles, no por la antigüedad del PRC |
| 2026-09-26 | **Tests de integración excluidos por `addopts`, no por `skip`.** El DoD exige "sin tests saltados": se deseleccionan (`-m 'not integracion'`) en vez de saltarse. El `-m` de la línea de comandos sobreescribe el de `addopts`, verificado |

Detalle completo de cada una en `04-DECISIONES.md`.
