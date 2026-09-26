# rasante

Copiloto open source para revisores independientes y Direcciones de Obras Municipales.

Computa normas urbanísticas de forma **determinística** (OGUC + plan regulador comunal) y emite
el Formato Tipo oficial de informe del revisor independiente (Circular DDU 514).

## Documentación

`doc/` es la **fuente de verdad** del proyecto. `task.md` es la cola de trabajo.

| | |
|---|---|
| `doc/00-METODOLOGIA.md` | Cómo se trabaja: SDD, TDD estricto, commits atómicos, handoff |
| `doc/01-VISION.md` | Problema, mercado, fuentes verificadas y plan |
| `doc/02-ALCANCE.md` | Qué entra en cada iteración y qué queda fuera |
| `doc/03-DISENO.md` | Arquitectura, decisiones D1–D12, modelo de dominio, corpus |
| `doc/04-DECISIONES.md` | Registro de decisiones (A1–A3) y su fundamento |
| `doc/05-VALIDACION.md` | Estrategia de tests, invariantes, riesgos |
| `doc/06-OPERACION.md` | Entorno, cómo correr, licencias |
| `doc/07-HANDOFF.md` | Estado actual, último commit, siguiente tarea, blockers |
| `task.md` | Cola de trabajo con estado por tarea |

## Principio

> El LLM redacta y extrae. **Nunca calcula ni dictamina.**

Un veredicto `(NC)` es un acto profesional firmado bajo responsabilidad civil y penal: no puede
ser una muestra de un modelo. El motor de reglas es determinista y auditable; la capa de LLM
(iteración 2+) solo compila normativa a reglas, extrae datos y redacta.

## Estado

Iteración 0. Sin funcionalidad todavía.

## Desarrollo

```bash
uv sync
uv run pytest
uv run ruff check
uv run mypy src
```

## Licencias

- Código: Apache-2.0 (`LICENSE`)
- Corpus normativo: CC-BY-4.0 (`LICENSE-CORPUS`), con atribución a la fuente municipal
