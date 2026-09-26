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
| T0.5 | Troceador determinista de la OGUC | ✅ | `[T0.5]` |
| T0.6 | Corpus curado: OGUC + DDU 514 | ✅ | `[T0.6]` |

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

**T0.5 — Troceador determinista de la OGUC.** ✅ `corpus/ingesta.py` con `descargar_fuente()`
(cacheada), `extraer_texto()` y `trocear()`. Sin LLM y sin red en los tests. Verificado contra la
OGUC real (4,3 MB, sha256 `64cf1b7c…`): **591 artículos, 582 únicos, 18 ocurrencias `bis`, 5
duplicados preservados**, cero IDs basura y orden documental perfecto. 27 tests.

**T0.6 — Corpus curado: OGUC + DDU 514.** ✅ 8 archivos en `corpus/`, validados por el usuario.
Artículos de cálculo encontrados **buscando**, no asumiendo: `2.1.22` (densidad en **bruta** hab/ha
+ conversión), `2.1.23` (3,50 m por piso), `5.1.10`/`5.1.11` (cómputo del cos), `5.1.12` (el
subterráneo no cuenta para el cus). 8 definiciones extraídas de las 209 de `1.1.2`. Cada archivo
cita con URL, hash y decreto consolidante.

---

## Iteración 1 — Vertical slice: coordenada → zona + 4 parámetros

Alcance en `doc/02-ALCANCE.md`. Parámetros: `cos`, `cus`, `altura_maxima` y **`densidad`**
(A3 = ambas). Sin LLM, sin informes, sin UI.

| # | Tarea | Estado |
|---|---|---|
| T1.1 | Dominio: modelos e invariante de cita | ✅ | `[T1.1]` |
| T1.2 | Dominio: motor de evaluación | ✅ | `[T1.2]` |
| T1.3 | Corpus ejecutable: esquema y migración | ⬜ |
| T1.4 | Dominio: intérprete de reglas | ⬜ |
| T1.5 | Dominio: verificador de factibilidad | ⬜ |
| T1.6 | Corpus: cargador y validación de YAML | ⬜ |
| T1.7 | Geo: reproyección e índice espacial | ⬜ |
| T1.8 | Resolución coordenada → zona | ⬜ |
| T1.9 | CLI | ⬜ |
| T1.10 | Corpus real de la comuna piloto | ⬜ |
| T1.11 | Validación contra predios reales | ⬜ |

> **T1.3–T1.5 se insertaron el 2026-09-26**, tras detectar que el motor no ejecuta el corpus y que
> evalúa parámetros acoplados como si fueran independientes (D14 y D15, `doc/03-DISENO.md` §2.5–2.6).
> Van **antes** de T1.6 y T1.10 porque definen el esquema: si el cargador y el corpus de Ñuñoa nacen
> con la forma vieja, hay que rehacerlos.

**T1.1 — Dominio: modelos e invariante de cita.** ✅ `dominio/modelos.py`: `Cita`, `Parametro` (con
`calificador` y `clave` compuesta), `Zona`, `Proyecto`, `Veredicto`, `Vigencia`, `Procedencia` y los
tres enums. Los tres invariantes son de construcción, no de convención: sin `Cita` no hay
`Veredicto`, un `float` en cualquier valor normativo levanta error, y una clave de `Zona` que no
coincida con su parámetro es rechazada. `LEYENDA` está hardcodeada porque el dominio no puede leer
YAML (D2); un test la contrasta contra `corpus/ddu/514.yaml` para que no se separen. 24 tests.

**T1.2 — Dominio: motor de evaluación.** ✅ `dominio/motor.py` — `evaluar(proyecto, zona)`. Una
**tabla única** (`DERIVACIONES`) dice qué parámetros conocemos y cómo se obtiene su valor: estar en
la tabla significa "sé calcularlo y sé que es un máximo". Un parámetro fuera de la tabla da `P`, no
se asume nada. Tres caminos separados hacia `P`: norma desconocida, dato del proyecto faltante, y
parámetro que no sabemos comparar. 31 tests.

### ⬜ T1.3 — Corpus ejecutable: esquema y migración

- **Objetivo:** que el corpus pueda expresar lo que la ordenanza realmente dice (D14). Hoy
  `DERIVACIONES` hardcodea lo que `corpus/oguc/*.yaml` describe como texto: dos fuentes de verdad.
- **Qué debe poder expresar:** varios límites **simultáneos** en un parámetro (`"44,00 m y 15
  pisos"`), variantes por **clasificación** del proyecto (`continua` vs `aislada`), **excepciones
  condicionales** (OGUC `2.6.5`: Conjunto Armónico +50 % cus) y **relaciones** entre parámetros.
- **Test primero:** recorrer `corpus/**/*.yaml` y validar el esquema nuevo. Es inválido un
  `limites` vacío, un límite sin `cita`, o una `expresion` que use un nombre fuera del vocabulario
  declarado.
- **Entregable:** esquema definitivo en `doc/03-DISENO.md` §2.5, `corpus/esquema.py` con el
  vocabulario cerrado, y los 6 archivos de `corpus/oguc/` migrados.
- **Aceptación:** los archivos migrados validan, y el esquema **rechaza** una expresión que use un
  nombre no declarado.
- **Nota:** sin intérprete todavía. Esta tarea fija la forma; T1.4 la ejecuta.
- **Commit:** `feat(corpus): esquema ejecutable con limites multiples y variantes [T1.3]`

### ⬜ T1.4 — Dominio: intérprete de reglas

- **Objetivo:** que el motor lea el corpus en vez de hardcodear. `dominio/reglas.py`.
- **Test primero:** evaluar expresiones del vocabulario cerrado; **rechazar** `__import__`,
  atributos (`x.y`), llamadas, comprensiones y cualquier nodo del AST fuera de la lista blanca;
  nombre desconocido levanta error; división por cero da `P`, no una excepción.
- **Ojo (seguridad):** el corpus es **dato que llega de fuera**. Se evalúa con `ast` y lista blanca,
  nunca con `eval`: `eval` sobre un YAML de la comunidad es ejecución de código arbitrario.
- **Aceptación:** `eval` no se usa en ningún camino, y hay un test que lo verifica sobre el código
  fuente. Un corpus malicioso no puede ejecutar nada.
- **Ojo (honestidad):** lo que el corpus aún no sepa expresar sigue hardcodeado, y esa lista queda
  explícita en el código en vez de dispersa.
- **Commit:** `feat(dominio): interprete de reglas del corpus con lista blanca [T1.4]`

### ⬜ T1.5 — Dominio: verificador de factibilidad

- **Objetivo:** cazar el proyecto imposible que hoy aprueba (D15). Los parámetros están acoplados
  geométricamente; chequeados por separado, todos pueden dar `C`.
- **Test primero:** conjunto normativo alcanzable → sin hallazgos; `cus` normado mayor que
  `cos + (n−1)·cos_sup` → hallazgo citado; proyecto que declara `cus`/`cos` incompatibles con su
  altura → hallazgo; proyecto coherente → sin hallazgos. Un test por relación.
- **Entregable:** `dominio/factibilidad.py` y el tipo `Hallazgo` en `dominio/modelos.py`
  (severidad, cita, parámetros involucrados).
- **Aceptación:** el caso *"todos los parámetros dan `C` pero el proyecto es imposible"* produce un
  hallazgo. Es el motivo de existir de la tarea.
- **Commit:** `feat(dominio): verificador de factibilidad geometrica [T1.5]`

### ⬜ T1.6 — Corpus: cargador YAML

- **Test primero:** cargar una zona de fixture; esquema inválido (falta `procedencia`, falta `cita`,
  `unidad` desconocida) levanta error con mensaje claro.
- **Ojo (hallazgo de T0.3):** las ordenanzas escriben **coma decimal** (`0,6`, `3,6`). Si el cargador
  no lo maneja, `0,6` se vuelve `6`. Debe exigir separador decimal explícito y tener un test para
  `"0,6"` y `"0.6"`.
- **Ojo (A3 cerrada):** debe **rechazar claves de parámetro duplicadas**. Con `cos` y `densidad`
  teniendo variantes, un YAML con dos claves `cos` es válido sintácticamente y pierde una regla sin
  avisar. Test explícito para eso — PyYAML no lo detecta por defecto.
- **Entregable:** `corpus/cargador.py`. Carga al esquema de T1.3, no al viejo.
- **Aceptación:** un YAML sin `hash_fuente` o sin `cita` por límite es rechazado.
- **Commit:** `feat(corpus): cargador y validacion de esquema de zonas [T1.6]`

### ⬜ T1.7 — Geo: reproyección e índice espacial

- **Test primero:** punto dentro de polígono sintético conocido → zona; punto fuera → `None`;
  verificar que EPSG:4326 → 3857 ubica un punto de Santiago en el rango esperado (cordura con
  tolerancia).
- **Entregable:** `geo/indices.py` — `IndiceZonas.buscar(lat, lon) -> str | None`.
- **Commit:** `feat(geo): reproyeccion e indice espacial point-in-polygon [T1.7]`

### ⬜ T1.8 — Resolución de zona

- **Test primero:** coordenada conocida → `Zona` con parámetros del corpus; coordenada sin zona →
  `SinZonaError`; zona en el PRC pero ausente del corpus → `ZonaSinCorpusError`. Son dos fallos
  operacionales **distintos** y no deben confundirse.
- **Entregable:** `geo/resolver.py`.
- **Commit:** `feat(geo): resolucion coordenada -> zona del corpus [T1.8]`

### ⬜ T1.9 — CLI

- **Test primero:** invocación con `typer.testing.CliRunner`. `rasante zona --lat --lon` imprime
  código y nombre de zona; salida `--json` con esquema estable; código de salida distinto de cero en
  los dos errores de T1.8. Los hallazgos de T1.5 se muestran aparte de los veredictos.
- **Entregable:** `cli.py`.
- **Aceptación:** `uv run rasante zona --lat -33.45 --lon -70.61 --json` devuelve JSON válido.
- **Commit:** `feat(cli): comandos zona y evaluar con salida JSON [T1.9]`

### ⬜ T1.10 — Corpus real de la comuna piloto

- **Desbloqueada: A2 = Ñuñoa.** Entregable: 3–5 zonas con los **4 parámetros** extraídos **a mano**
  de la ordenanza, revisados y citados, **en el esquema de T1.3**. Empezar por las zonas que el texto
  refundido expone limpiamente (`Z-1`…`Z-8` y variantes).
- **Ojo (A3):** para `densidad` hay que declarar si la zona usa densidad **bruta** o **neta**. Sin
  eso el cálculo es ambiguo y el veredicto queda sin fundamento. Lo mismo con el calificador de `cos`.
- **Ojo (T1.3):** Ñuñoa tiene límites **simultáneos** (`"44,00 m y 15 pisos"`) y variantes por
  `continua`/`aislada`. Es el primer corpus real que ejercita el esquema nuevo.
- **Test primero:** test de integración que carga las zonas reales y verifica que cada parámetro
  tiene cita y que la procedencia tiene `hash_fuente`.
- **Aceptación:** cada valor trazable a un artículo de la ordenanza. `estado: revisado` con
  `revisado_por` poblado. **Se presenta cada extracción para validación antes del commit.**
- **Commit:** `feat(corpus): zonas iniciales de <comuna> con parametros citados [T1.10]`

### ⬜ T1.11 — Validación contra predios reales

- **Objetivo:** cerrar la iteración 1 con evidencia. Metodología y métrica en `doc/05-VALIDACION.md`.
- **Entregable:** `doc/` con precisión y recall sobre N expedientes reales ya aprobados.
- **Nota:** sin esto la iteración **no se declara cerrada**.
- **Commit:** `docs: validacion de la iteracion 1 contra predios reales [T1.11]`
