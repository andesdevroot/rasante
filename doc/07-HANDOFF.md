# 07 — Handoff

Documento vivo. Estado **real**, no aspiracional. Se actualiza en el commit que cierra cada tarea
(`00-METODOLOGIA.md`).

---

## Estado actual

**Iteración 1 — Vertical slice, en curso.** T1.1–T1.8 cerradas (más T1.7b) (iteración 0 completa: T0.1–T0.6).

| | |
|---|---|
| Tarea en curso | ninguna. Siguiente: **T1.9** (índice espacial) |
| Código | `clasificacion/` (nueva) · `dominio/{modelos,motor,reglas,vocabulario,factibilidad}.py` · `corpus/{ingesta,esquema,cargador}.py` · `geo/arcgis.py` |
| Tests | **297 verdes** offline · **3 de integración** contra la API real, excluidos por defecto |
| Gate | **`./gate.sh`** en verde (`set -euo pipefail`): pytest, ruff y mypy sobre `src` **y** `tests` |
| Árbol git | limpio — todo commiteado |

Reestructuración a `doc/` aplicada el 2026-09-26: `01-VISION.md`, `03-DISENO.md`,
`04-DECISIONES.md` y `07-HANDOFF.md` vienen de `docs/RASANTE-plan-desarrollo.md`, `design.md`,
`docs/decision-comuna.md` y `handoff.md`.

## Último commit

```
[T1.6]    feat(dominio): hechos y seleccion de limites condicionales
[T1.5]    feat(dominio): verificador de factibilidad geometrica
[T1.4]    feat(dominio): interprete de reglas del corpus con lista blanca
[T1.3]    feat(corpus): esquema ejecutable con limites multiples y variantes
[T1.2]    feat(dominio): motor de evaluacion de parametros urbanisticos
[T1.1]    feat(dominio): modelos de dominio e invariante de cita obligatoria
[T0.6]    feat(corpus): corpus curado de OGUC y DDU 514 con citas
[T0.5]    feat(corpus): troceador determinista de la OGUC por articulo
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

**T1.8 — Geo: reproyección e índice espacial** (`src/rasante/geo/indices.py`).

`IndiceZonas.buscar(lat, lon) -> str | None` sobre las capas PRC cacheadas en T0.2: reproyectar
EPSG:4326 → 3857 con `pyproj` y point-in-polygon con `shapely`.

**Ojo:** `shapely` y `pyproj` entran como dependencias nuevas. Van en `rasante.geo`, nunca en
`rasante.dominio` (D2).

**Deuda registrada:** `Proyecto.clasificaciones` existe y se valida, pero **nadie lo usa todavía**:
`clasificar` evalúa hechos por expresión. Es el mecanismo previsto para lo que no se deduce de
números, como la fusión predial de la condición 1.c) del 2.6.4.

## Blockers

| Blocker | Detalle |
|---|---|
| **Titularidad normativa** | **No resuelto.** Intenté tres fuentes de la Ley 17.336: BCN devuelve 401, el archivo de la UNESCO devuelve HTML, y LeyChile se renderiza por JS (solo devuelve el título). Mitigación adoptada: el corpus guarda **citas, no texto íntegro** — artículo, URL, hash y fecha. Eso baja el riesgo a algo asumible. Verificado que **MINVU publica la OGUC consolidada para descarga abierta** |

Sin blockers de alcance: A1, A2 y A3 están cerradas.

**Deudas registradas, no bloqueantes:**

- **La DDU 514 pública está escaneada con OCR** (`texto_extraible: false` en el corpus). No se
  derivan reglas de su texto. Cualquier regla que se necesite de ahí exige verificación visual.
- **La leyenda de veredictos viene de la respuesta ministerial a la consulta pública**, no del
  Formato Tipo oficial. Aceptada como provisional por el usuario; reemplazar cuando se obtenga el
  oficial de MINVU.
- **`Veredicto.cita` es singular, pero D13 pide dos citas.** La OGUC da la regla y el PRC el valor:
  un veredicto de densidad debería citar las dos. Hoy lleva solo la norma que fija el valor. Añadir
  la cita de la regla es aditivo, y toca hacerlo cuando el informe la necesite (iteración 3).
- **`Decimal` sale en notación científica al dividir** (`1E+2` en vez de `100`). La comparación es
  correcta porque `Decimal` compara numéricamente, pero el informe necesita formatearlo.

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
| 2026-09-26 | **D13: la OGUC aporta reglas, el PRC aporta valores.** La OGUC define *cómo se computa* (Art. `1.1.2`, `2.1.23`); los números los fija cada plan regulador |
| 2026-09-26 | **El corpus normativo va en `corpus/`, no en `doc/`.** `doc/` es la spec (prosa); el texto normativo es dato. Además la OGUC son 577 págs / 4,4 MB: no se commitea |
| 2026-09-26 | **Corpus curado (~10-15 artículos), no la OGUC completa.** Se guardan **citas, no texto íntegro**: resuelve el riesgo de titularidad y reduce el mantenimiento |
| 2026-09-26 | **"Entrenar" es la palabra equivocada.** D4 sigue: nada de fine-tuning. El motor **recupera y cita**, no aprende |
| 2026-09-26 | **La extracción de la ordenanza por comuna sigue a mano en iteración 1.** Automatizarla es LLM, o sea iteración 2. Antes hay que fijar el esquema del YAML |
| 2026-09-26 | **Mis números de artículo de la OGUC estaban mal.** `2.6.2` es adosamiento, `2.6.3` distanciamientos y rasantes, `2.6.4` Conjunto Armónico. Las definiciones reales están en `1.1.2` |
| 2026-09-26 | **El patrón de troceado exige tres cosas, cada una verificada contra el texto real.** (1) `A` mayúscula obligatoria: con IGNORECASE pleno entran 82 falsos positivos por saltos de línea. (2) El número exige un punto: descarta `Artículo 116` de la LGUC. (3) Anclaje a inicio de línea: sin él, las referencias del cuerpo cuentan como encabezados |
| 2026-09-26 | **El sufijo `bis` va DESPUÉS del punto.** El formato real es `Artículo  2.1.3. bis.` (dos espacios, punto intermedio). Implementé el grupo `BIS` antes del punto: detectaba **0 de 18** `bis` y los etiquetaba con su número base, **colisionando con el artículo base**. Lo cazó la verificación contra datos reales, no los tests sintéticos |
| 2026-09-26 | **La densidad bruta deja de ser una suposición: el art. `2.1.22` la hace obligatoria.** Los IPT *"deberán expresarla en densidad bruta en habitantes por hectárea"*, con conversión a viviendas dividiendo por el coeficiente 4. Cierra A3 con fuente |
| 2026-09-26 | **La obligación del revisor está en el art. 116 bis de la LGUC**, no en "art. 116 de la Ley 21.718" como yo había escrito. La Ley 21.718 lo modificó. Corregido en `01-VISION.md` (×3) y `02-ALCANCE.md` |
| 2026-09-26 | **La OGUC se compone de reglas, no de valores** (D13), confirmado al curar el corpus: `2.1.23` da la conversión 3,50 m/piso, pero la altura máxima la fija cada PRC. Un veredicto de altura cita **las dos** fuentes |
| 2026-09-26 | **`factor_habitantes_por_vivienda: "4"` es inferencia mía, no texto literal.** La OGUC dice "el coeficiente 4". Es la única lectura con dimensiones correctas, pero queda señalado como interpretación |
| 2026-09-26 | **Los invariantes del dominio son de construcción, no de convención.** `Veredicto` sin `Cita` levanta `ErrorDominio`; un `float` en cualquier valor normativo levanta error; una clave de `Zona` que no coincida con su `Parametro.clave` es rechazada. No se puede construir un modelo inválido |
| 2026-09-26 | **`LEYENDA` está hardcodeada en el dominio porque no puede leer YAML (D2).** Un test la contrasta contra `corpus/ddu/514.yaml`, que es lo que impide que las dos se separen en silencio |
| 2026-09-26 | **`clave_compuesta()` es la única definición de la clave.** `Parametro`, `Veredicto` y (en T1.6) el cargador del corpus deben coincidir, o dos reglas se pisan en el mapping |
| 2026-09-26 | **El motor usa UNA tabla, no dos listas.** `DERIVACIONES` dice a la vez qué parámetros conocemos y cómo se deriva su valor: estar en la tabla significa "sé calcularlo y sé que es un máximo". Antes tenía `_derivar` y `_MAXIMOS` por separado, y podían divergir en silencio |
| 2026-09-26 | **Un parámetro fuera de la tabla da `P`, no se asume que sea un máximo.** Suponerlo y compararlo produciría un `(C)` o `(NC)` sin fundamento |
| 2026-09-26 | **T1.2 encontró un hueco en el modelo de T1.1:** `Proyecto` no tenía la superficie del primer piso, sin la cual `cos` no se puede derivar. Se agregó `superficie_primer_piso_m2` de forma **aditiva** (T1.1 no se rompió) |
| 2026-09-26 | **`Parametro.id` rechaza el punto.** Bug real de T1.2: pasar `"densidad.bruta"` como `id` *y* `"bruta"` como calificador producía la clave `densidad.bruta.bruta`. El modelo lo aceptaba en silencio; ahora lo rechaza |
| 2026-09-26 | **El motor no redondea antes de comparar.** Redondear en el límite puede convertir un `(NC)` en un `(C)`. El redondeo es del informe, no del veredicto |
| 2026-09-26 | **D14: el corpus es ejecutable.** `DERIVACIONES` hardcodea lo que `corpus/oguc/2.1.22.yaml` describe como texto. Dos fuentes de verdad para el mismo cálculo, y pueden divergir sin que ningún test lo note |
| 2026-09-26 | **El corpus actual no puede expresar lo que la ordenanza dice.** Evidencia de Ñuñoa: *"44,00 m **y** 15 pisos"* (límites simultáneos), *"continua"* vs *"aislada"* (variantes por clasificación), OGUC `2.6.5` (excepción condicional +50 % cus) |
| 2026-09-26 | **D15: el motor verifica factibilidad, no solo parámetros sueltos.** Con cos 0,6 y cos_sup 0,4, un `cus` de 4 exige ≥7 pisos ≈24,5 m. Un proyecto con altura menor es imposible y hoy da `C` en cada parámetro |
| 2026-09-26 | **La `expresion` del corpus se evalúa con `ast` y lista blanca, nunca con `eval`.** El corpus es dato que llega de fuera: `eval` sobre un YAML de la comunidad es ejecución de código arbitrario |
| 2026-09-26 | **La factibilidad no es un `Veredicto`, es un `Hallazgo`.** Un veredicto es de un parámetro; un acoplamiento geométrico involucra varios. Se registran y se rinden por caminos distintos |
| 2026-09-26 | **No hay gap de rendimiento.** El motor evalúa 8 escalares: O(n) con n≈8, microsegundos. El gap es de **corrección**: el motor aprueba proyectos imposibles |

Detalle completo de cada una en `04-DECISIONES.md`.

## Proceso (2026-09-26)

Se incorporaron tres arreglos que **reducen fallos y tiempo a la vez**, más dos suites:

| | |
|---|---|
| `./gate.sh` | gate único con `pipefail`. Los dos commits con gate en rojo de esa tarde fueron por leer `ruff \| tail` |
| `mypy` sobre `tests` | los errores mecánicos (`.valor` tras cambiar el modelo, `id_` vs `id`) pasan a ser **una** corrida de mypy en vez de cuatro fallos de test |
| Leer antes de renombrar | buscar los llamadores antes de un cambio transversal |
| `tests/test_realidad_corpus.py` | contrasta cada cita contra el artículo real y hash-verificado. **Ya cazó tres citas parafraseadas** (`1.1.2`, `2.6.4`, `2.6.5`) |
| `tests/test_consistencia.py` | invariantes transversales en un sitio: vocabulario, derivaciones vs `MAXIMOS`, `cuando` vs hechos, leyenda, y que nada afirme cumplimiento sin norma ni cita |

El detalle y el porqué están en `00-METODOLOGIA.md`.

## Agujero cerrado (2026-09-26)

**El motor no leía `EstadoRevision`.** Una zona en `borrador`, sin `revisado_por`, producía los
mismos `(C)` que una validada. Lo detectó el usuario al proponer un evaluador probabilístico; su
instinto apuntó a un agujero real, aunque el mecanismo propuesto no era el correcto.

Cerrado con **D18**: sin firma humana no hay `C` ni `NC`, solo `P` y un `Hallazgo`
(`FUENTE_SIN_REVISAR`). Vale en las dos direcciones: un `(NC)` sin fundamento también haría daño.

**D17** registra JEV (Choice/Score/Noul) donde sí corresponde: **contrato de la capa de extracción**,
iteración 2. La confianza decide si un dato está listo, no cuánto cumple. El razonamiento completo
—incluido por qué el veredicto no puede ser probabilístico— está en `03-DISENO.md` §2.8.

## Capa de clasificación (2026-09-26, D19)

El usuario señaló un segundo gap real: **el motor solo sabe comparar números**. Verificado contra
nuestro propio corpus: usos de suelo (`UPERM`/`UPROH`) y `dimension_b`/`dimension_c` —parkeadas en
`hechos_pendientes` del `2.6.4`— no son aritmética sobre el proyecto, son juicios sobre texto.

Se implementó `rasante/clasificacion` con el contrato de JEV (TypeSafe): `choice`/`noul`/`score`,
una pasada, respuestas tipadas con confianza, y un **portero** que manda a revisión humana lo que no
supera el umbral. **Nunca se resuelve a la opción más probable.**

La guía oficial de JEV recomienda literalmente nuestra arquitectura: *"route with Jev, **compute in
code**, write with an LLM"*, y advierte que **no es confiable en aritmética, conteo ni fechas** — que
es exactamente lo que hace el motor. Detalle en `03-DISENO.md` §2.9.

**Pendiente de T1.9 en adelante:** la capa existe y está probada con un proveedor guionizado, pero
**no está conectada al motor todavía**. Falta que el corpus declare preguntas `choice`/`noul` y que
sus resoluciones alimenten los `hechos_pendientes`.
