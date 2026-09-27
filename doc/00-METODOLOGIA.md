# 00 — Metodología de trabajo

**v1.0 · 2026-09-26**

## Spec-Driven Development

- **`doc/` es la fuente de verdad del proyecto**: qué se construye, por qué y con qué criterios.
- **`task.md` es la cola de trabajo**: las tareas pendientes y su estado.
- El código se escribe para cumplir la especificación. Si la spec cambia, se actualiza `doc/` en el
  mismo commit (o en un commit previo).

## TDD estricto: RED → GREEN → REFACTOR

1. **RED** — escribir un test que falle y demuestre la carencia.
2. **GREEN** — implementar el código mínimo que hace pasar el test.
3. **REFACTOR** — limpiar el código manteniendo la suite en verde.

## Flujo por tarea

```
leer doc/ → escribir test → uv run pytest (RED) → implementar
          → uv run pytest (GREEN) → refactor → commit
```

> El flujo original dice `go test`; es boilerplate de plantilla. El stack es **Python 3.14 + `uv`**,
> así que el comando es `uv run pytest`. Confirmado el 2026-09-26.

## Commits atómicos

- **Un commit por tarea completada.**
- Si una tarea no cabe en un commit, **se divide en tareas más pequeñas** — no se parte el commit.
- La spec puede ir en el mismo commit o en uno previo.

## Verificación

**El gate es un solo comando: `./gate.sh`.** Corre pytest, ruff y mypy con `set -euo pipefail`, y o
sale en verde o no sale. **No se commitea si el gate no pasa.**

`set -o pipefail` no es decorativo: sin él, `ruff | tail` devuelve el código de salida de `tail`, y
un gate en rojo pasa desapercibido. Ya ocurrió dos veces.

**`mypy` cubre `src` y `tests`.** Los tests también se type-chequean: un `.valor` que dejó de existir
tras cambiar el modelo debe ser **un** error de mypy, no cuatro fallos de test descubiertos de a uno.

**Antes de un cambio transversal, se leen los puntos de uso.** Renombrar un atributo o cambiar la
forma de un modelo exige buscar todos los llamadores *antes* de tocar. Suponer la forma del código
existente es la causa más frecuente de reintentos.

**Toda afirmación normativa cita la fuente, y las citas son literales.** `tests/test_realidad_corpus.py`
comprueba que cada `cita` del corpus aparezca **literalmente** en el artículo real y hash-verificado.
Una cita parafraseada no respalda nada; ya cazó tres. Un corpus que no se contrasta con su fuente es
un corpus que se cree a sí mismo — y en T0.5 un bug que fusionaba dos artículos distintos pasó los
27 tests sintéticos.

**Los invariantes transversales viven en `tests/test_consistencia.py`**, no dispersos por tarea.

## Regla de oro

> **Nunca hacer commit con tests rojos.** El verde es requisito previo de cada commit.

## Handoff entre sesiones

**Al iniciar una sesión:** leer `task.md` (cola de trabajo) y `doc/07-HANDOFF.md` (estado, blockers
y decisiones recientes) **antes** de escribir código.

**Al cerrar una sesión:** actualizar

- `task.md` — marcar lo completado y señalar la siguiente tarea.
- `doc/07-HANDOFF.md` — Estado actual · Último commit · Siguiente tarea · Blockers · Decisiones
  recientes.

**El handoff viaja en el commit que cierra la tarea.** No se deja para un commit aparte.

**No citar el hash del propio commit.** Un commit no puede contener su propio hash: escribirlo
cambia el hash, y corregirlo lo cambia otra vez — nunca converge. En `task.md` y en el handoff, la
tarea que cierra el commit en curso se referencia por su **tag** (`[T0.4]`). Los hashes se listan
solo para commits **anteriores**, que ya son inmutables.

## Definición de terminado

1. El test se escribió antes y se verificó en **rojo**.
2. `uv run pytest` en verde, sin tests saltados.
3. `uv run ruff check .` y `uv run mypy src` limpios.
4. **REFACTOR** hecho; la suite sigue en verde.
5. `task.md` y `doc/07-HANDOFF.md` actualizados **en el mismo commit**.
6. Sin `float` en rutas normativas.
