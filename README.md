# rasante

Copiloto open source para revisores independientes y Direcciones de Obras Municipales.

Computa normas urbanísticas de forma **determinística** (OGUC + plan regulador comunal) y emite
el Formato Tipo oficial de informe del revisor independiente (Circular DDU 514).

- `design.md` — arquitectura y decisiones (D1–D11)
- `task.md` — tareas atómicas, 1 tarea = 1 commit, con TDD
- `handoff.md` — estado vivo del proyecto
- `docs/RASANTE-plan-desarrollo.md` — antecedentes, fuentes verificadas y plan de mercado

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
