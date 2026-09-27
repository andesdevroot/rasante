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
| T1.3 | Corpus ejecutable: esquema y migración | ✅ | `[T1.3]` |
| T1.4 | Dominio: intérprete de reglas | ✅ | `[T1.4]` |
| T1.5 | Dominio: verificador de factibilidad | ✅ | `[T1.5]` |
| T1.6 | Hechos y selección de límites condicionales | ✅ | `[T1.6]` |
| T1.7 | Corpus: cargador y validación de YAML | ✅ | `[T1.7]` |
| T1.7b | Un dato sin revisar no aprueba (D18) | ✅ | `[T1.7b]` |
| T1.8 | Capa de clasificación con contrato tipado | ✅ | `[T1.8]` |
| T1.9 | El sentido lo declara el corpus, no el motor | ✅ | `[T1.9]` |
| T1.10 | Conectar la capa de clasificación al motor | ⬜ |
| T1.11 | Geo: reproyección e índice espacial | ⬜ |
| T1.12 | Resolución coordenada → zona | ⬜ |
| T1.13 | CLI | ⬜ |
| T1.14 | Corpus real de la comuna piloto | ⬜ |
| T1.15 | Validación contra predios reales | ⬜ |

> **T1.3–T1.6 se insertaron el 2026-09-26**, al detectar tres gaps encadenados: el motor no
> ejecutaba el corpus (D14), evaluaba parámetros acoplados como si fueran independientes (D15), y no
> podía elegir entre límites condicionales (D16). Van **antes** de T1.7 y T1.14 porque definen el
> esquema: nacer con la forma vieja significa rehacerlos.

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

**T1.3 — Corpus ejecutable: esquema y migración.** ✅ `dominio/vocabulario.py` (el vocabulario
cerrado: 6 primitivas, 8 parámetros, 4 condiciones) y `corpus/esquema.py` (el validador).
`corpus/oguc/1.1.2.yaml` gana `derivaciones` — **el corpus ya dice cómo calcular cada parámetro**, que
es el corazón de D14 — y `relaciones` con el acoplamiento del `cus`. `2.1.22` y `2.1.23` llevan su
conversión como expresión ejecutable. Las expresiones se validan contra el vocabulario y la sintaxis
con `ast`: se rechazan llamadas, atributos fuera del vocabulario, comprensiones, lambdas,
condicionales y potencias. `Proyecto` gana `numero_pisos` y `clasificaciones`. 33 tests.

**T1.4 — Dominio: intérprete de reglas.** ✅ `dominio/reglas.py` (intérprete con `ast` y lista
blanca) y `corpus/cargador.py` (`cargar_reglas`). **D14 cerrado:** el motor ya no tiene tabla
hardcodeada — lee `derivaciones` del corpus. `evaluar(proyecto, zona, reglas)`. División por cero y
dato faltante dan `None`, nunca excepción: eso es `P`, no un fallo. Lo que sigue hardcodeado es solo
`MAXIMOS` (el sentido de la comparación, que el esquema aún no expresa), en un sitio explícito y con
un test que falla si el corpus deriva algo sin sentido declarado. Un test verifica sobre el código
fuente que no hay `eval`, `exec` ni `compile`. 35 tests.

**T1.5 — Dominio: verificador de factibilidad.** ✅ `dominio/factibilidad.py` y el tipo `Hallazgo`
(con `CodigoHallazgo` y `Severidad`) en `modelos.py`. **D15 cerrado:** el caso que antes aprobaba
—cada parámetro en `C` y el proyecto imposible— ahora emite un `BLOQUEANTE`. Dos chequeos distintos:
factibilidad del proyecto (`superficie_edificada_m2 > huella × pisos`) y consistencia del conjunto
normativo (`cus` que excede el máximo alcanzable con `cos`, `cos` de pisos superiores y altura, a
3,50 m/piso de la OGUC `2.1.23`). Sin `numero_pisos`, sin superficies o sin altura, **no se afirma
nada** — igual que el `P` del motor. Sin cita no se emite hallazgo. 19 tests.

**T1.7 — Corpus: cargador de zonas.** ✅ `cargar_zona()`, `cargar_zonas()` y `decimal_de()`.
Pasa el YAML al esquema de T1.3 y de ahí al dominio.

**La coma decimal, que era la trampa anunciada:** `0,6` → `Decimal("0.6")`. La regla es explícita:
con coma, la coma es decimal y los puntos son de miles (`1.234,56` → 1234.56); sin coma, el punto es
decimal (`0.6`, `3.50`) **salvo** que le sigan exactamente 3 dígitos con entero distinto de cero
(`1.234`, `5.000`), que es **ambiguo y se rechaza**. Se exige escribirlo inequívoco: `1234` o
`1,234`. `0.600` sí se acepta, porque nadie escribe 0.600 para decir 600.

**Claves duplicadas:** un `SafeLoader` propio falla ante una clave repetida. PyYAML se queda con la
última y descarta la otra **en silencio** — con `cos` teniendo variantes, eso perdía una regla.

**Corrección al esquema:** `cuando` nombra **hechos** desde D16, no las condiciones de clasificación
de T1.3; la validación quedó vieja. Ahora `validar_documento` solo comprueba la forma, y
`validar_corpus` comprueba entre archivos que el hecho exista. 21 tests.

**T1.8 — Capa de clasificación con contrato tipado.** ✅ `rasante/clasificacion/`: contrato
(`choice`/`noul`/`score`), portero de confianza y dos proveedores (`ProveedorGuionizado` offline y
`ProveedorJev` por OpenRouter, probado con transporte simulado).

Cierra el hueco que el motor no podía cubrir: **usos de suelo** (`UPERM`/`UPROH` como texto sucio) y
las condiciones **no aritméticas** parkeadas en `hechos_pendientes` del `2.6.4` —`dimension_b` ("¿es
una manzana?") y `dimension_c` ("¿es una fusión predial del art. 63?"). No son cuentas sobre números
del proyecto: son juicios sobre texto.

El **portero** es la pieza que importa: una respuesta bajo el umbral **no se resuelve**, va a revisión
humana. Nunca se redondea una duda hacia el lado permisivo. Es D18 aguas arriba. 24 tests.

**T1.9 — El sentido lo declara el corpus.** ✅ `MAXIMOS` **eliminado del motor**: era lo último
hardcodeado en Python. Cada `Parametro` declara su `sentido` (`maximo`/`minimo`) y el esquema lo
exige, **sin valor por defecto** — un mínimo tratado como máximo daría el veredicto invertido en
silencio. Con eso el motor no hardcodea nada: `derivaciones` dice cómo se calcula, los hechos cuál
límite rige, y el `sentido` hacia dónde compara. Habilita parámetros de mínimo (densidad mínima, área
verde mínima) sin tocar código. 13 tests.

### ⬜ T1.11 — Geo: reproyección e índice espacial

### ⬜ T1.12 — Resolución de zona

- **Test primero:** coordenada conocida → `Zona` con parámetros del corpus; coordenada sin zona →
  `SinZonaError`; zona en el PRC pero ausente del corpus → `ZonaSinCorpusError`. Son dos fallos
  operacionales **distintos** y no deben confundirse.
- **Entregable:** `geo/resolver.py`.
- **Commit:** `feat(geo): resolucion coordenada -> zona del corpus [T1.12]`

### ⬜ T1.13 — CLI

- **Test primero:** invocación con `typer.testing.CliRunner`. `rasante zona --lat --lon` imprime
  código y nombre de zona; salida `--json` con esquema estable; código de salida distinto de cero en
  los dos errores de T1.12. Los hallazgos de T1.5 se muestran aparte de los veredictos.
- **Entregable:** `cli.py`.
- **Aceptación:** `uv run rasante zona --lat -33.45 --lon -70.61 --json` devuelve JSON válido.
- **Commit:** `feat(cli): comandos zona y evaluar con salida JSON [T1.13]`

### ⬜ T1.14 — Corpus real de la comuna piloto

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
- **Commit:** `feat(corpus): zonas iniciales de <comuna> con parametros citados [T1.14]`

### ⬜ T1.15 — Validación contra predios reales

- **Objetivo:** cerrar la iteración 1 con evidencia. Metodología y métrica en `doc/05-VALIDACION.md`.
- **Entregable:** `doc/` con precisión y recall sobre N expedientes reales ya aprobados.
- **Nota:** sin esto la iteración **no se declara cerrada**.
- **Commit:** `docs: validacion de la iteracion 1 contra predios reales [T1.15]`
