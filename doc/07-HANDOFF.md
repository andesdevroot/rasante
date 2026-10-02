# 07 — Handoff

Documento vivo. Estado **real**, no aspiracional. Se actualiza en el commit que cierra cada tarea
(`00-METODOLOGIA.md`).

---

## Estado actual

**Iteración 1 — Vertical slice, en curso.** T1.1–T1.13, T1.16 y T1.17 cerradas (más T1.7b, T1.14a, T1.14b, E1, E4 y P6) (iteración 0 completa: T0.1–T0.6).

| | |
|---|---|
| Tarea en curso | ninguna. Siguiente: **T1.14b** (prosa normativa) o **E2** (traza) |
| Código | `corpus/prc/RM/nunoa/zonas/Z-2.yaml` (nuevo) · `puente.py` · `clasificacion/{contrato,porteria,proveedor}.py` · `dominio/{modelos,motor,reglas,vocabulario,factibilidad}.py` · `corpus/{ingesta,esquema,cargador}.py` · `geo/arcgis.py` |
| Tests | **514 verdes** offline · **3 de integración** contra la API real, excluidos por defecto |
| Gate | **`./gate.sh`** en verde local **y en CI** (`.github/workflows/gate.yml` corre el mismo script; primera corrida `success`, 2026-10-02) |
| Árbol git | limpio — todo commiteado |

Reestructuración a `doc/` aplicada el 2026-09-26: `01-VISION.md`, `03-DISENO.md`,
`04-DECISIONES.md` y `07-HANDOFF.md` vienen de `docs/RASANTE-plan-desarrollo.md`, `design.md`,
`docs/decision-comuna.md` y `handoff.md`.

## Último commit

El más reciente es el que trae este archivo. **Un archivo no puede contener su propio hash**:
lo invalida el mismo `commit` que lo guarda, y un `amend` lo deja mintiendo. Por eso la lista
arranca en el commit anterior.

Historia completa (**35 commits**), del más nuevo al más viejo:

```
c7f0ab4 feat(geo): indice espacial de zonas, sin pyproj [T1.11]
5ef357f docs: alinea el arbol de zonas con el diseno y reescribe el esquema obsoleto
26aa067 fix(corpus): cierra el agujero de verificacion de la zona Z-2
c8d7b3f docs(task): cierra T1.14a y abre los huecos que dejo la primera zona real
9880c69 feat(corpus): primera zona real, Z-2 de Nunoa, con citas verificadas [T1.14a]
62e5664 feat(dominio): excepciones de aplicacion general con factor (D20, D21)
b4395cd docs(readme): README real para el repositorio open source
e704415 docs: sincroniza los md con el estado real y elimina referencias muertas
597b70f feat(puente): el corpus pregunta y el motor recibe hechos externos [T1.10]
7db9c13 refactor(dominio): el sentido lo declara el corpus, no MAXIMOS [T1.9]
c6a1486 docs: sincroniza todos los md con la capa de clasificacion (D19)
12123af feat(clasificacion): capa con contrato tipado y portero de confianza [D19]
0489bd9 fix(dominio): un dato sin revisar no aprueba [D18]
a77228b test: gate unico, mypy sobre tests y suites de realidad y consistencia
700fc3f feat(corpus): cargador de zonas con coma decimal y sin claves duplicadas [T1.7]
020ec15 feat(dominio): hechos y seleccion de limites condicionales [T1.6]
de0bd07 docs: inserta T1.6 (hechos y seleccion de limites) y agrega D16
c457421 feat(dominio): verificador de factibilidad geometrica [T1.5]
df1124a feat(dominio): interprete de reglas del corpus con lista blanca [T1.4]
f3e0d6f feat(corpus): esquema ejecutable con limites multiples y variantes [T1.3]
b144137 docs: inserta T1.3-T1.5 (corpus ejecutable y factibilidad) y renumera la cola
06ea9eb feat(dominio): motor de evaluacion de parametros urbanisticos [T1.2]
0c507f2 feat(dominio): modelos de dominio e invariante de cita obligatoria [T1.1]
b081f4c feat(corpus): corpus curado de OGUC y DDU 514 con citas [T0.6]
deb942c feat(corpus): troceador determinista de la OGUC por articulo [T0.5]
2f29632 docs: registra T0.5 y T0.6, D13 y el esquema del corpus normativo
b63a0f5 docs: cierra T0.3, registra A2 y A3 y actualiza el alcance a 4 parametros [T0.3]
f82846e docs: corrige los hashes invalidados por el squash de T0.1
fee7c98 test(geo): test de integracion contra la API real de MINVU [T0.4]
5307095 docs: reestructura la documentacion a doc/ y actualiza la metodologia
a111a3c docs: agrega T0.4 (test de integracion contra la API real)
9d826bd feat(geo): ingestor ArcGIS REST con paginacion y cache en disco [T0.2]
a98dd5d chore(repo): esqueleto, uv, licencias y guardian de arquitectura [T0.1]
af56aa8 docs: spec inicial (design, task, handoff)
```

Una tarea, un commit, y **nunca con tests en rojo**. T0.1 se consolidó en `64bdcdd` tras el squash; los commits de documentación de la iteración 1 se agruparon en cadenas de `amend`, así que la historia es lineal en `main`.

## Siguiente tarea

**T1.10b — El `excepcion` del corpus nunca llega a `Limite`.**

`corpus/oguc/2.6.5.yaml` declara el +50 % de `cus` por Conjunto Armónico, pero `cargar_reglas` solo
lee `derivaciones`, `hechos` y `relaciones`: el bloque `excepcion:` **no lo consume ningún código**.
El corpus afirma algo que el motor no puede aplicar, y eso es peor que no tenerlo — parece cubierto.

Lo mismo con `Proyecto.clasificaciones`: se valida contra `CONDICIONES` y **no se consume** en
ninguna parte. Es un segundo mecanismo para lo que ahora hace `hechos_externos`, y con una
limitación de fondo: un `frozenset` no puede expresar «no se sabe», así que nunca podría alimentar
un `P`. La decisión es **eliminarlo**, no mantenerlo.

Después: **T1.12 — Resolución coordenada → zona** (`src/rasante/geo/resolver.py`).
T1.11 ya deja `IndiceZonas.buscar(lat=..., lon=...)` funcionando; falta unir el código de zona que
devuelve el índice con la `Zona` del corpus, distinguiendo **dos fallos operacionales distintos**:
coordenada sin zona (`SinZonaError`) y zona del PRC que no está en el corpus (`ZonaSinCorpusError`).

**Ojo, hallazgo de T1.11:** el servicio devuelve 3 de 40 códigos con espaciado irregular (`'MH- 1'`,
`'ZCH- 1'`). El índice los devuelve tal cual, a propósito. Decidir cómo se reconcilian con el corpus
es de T1.12 y necesita su propio test: normalizar en silencio escondería que el servicio y el corpus
no coinciden.

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
| `tests/test_consistencia.py` | invariantes transversales en un sitio: vocabulario, `sentido` declarado por parámetro, `cuando` vs hechos, leyenda, y que nada afirme cumplimiento sin norma ni cita |

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

**T1.10b cerró los dos huecos (2026-09-27).** El bloque `excepcion:` de `2.6.5.yaml` **sí llega al
motor** ahora, como `Excepcion` en `Reglas`: la zona aporta el valor y la OGUC el factor (D20). Y
`Proyecto.clasificaciones` + `CONDICIONES` se **eliminaron**: eran un segundo origen de verdad, menos
expresivo que `hechos_externos` porque un `frozenset` no puede expresar «no se sabe».

Cargar `2.6.5` destapó dos cosas que ninguna prueba sintética habría mostrado:

1. **Acogerse al Conjunto Armónico es una facultad del titular** (art. 107 LGUC), no una consecuencia
   del tamaño del predio. Sin `Proyecto.acoge_conjunto_armonico` (default `False`), el `cus` de
   *todos* los proyectos quedaba `P`. Es D21, y **es la única lectura del proyecto que no se apoya en
   texto literal**: conviene que la confirmes.
2. **`Clasificacion.aplica` e `indeterminados` no implementaban `X and False = False`.** Con una
   sola condición por límite nunca se notó; con una conjunción, un hecho ya descartado se reportaba
   como duda y generaba hallazgos pidiéndole al revisor un dato que ya no cambiaba el veredicto.

15 tests existentes se cayeron al cargar `2.6.5`, y los 15 por la razón correcta.

## Primera zona real (2026-09-27, T1.14a)

`corpus/prc/RM/nunoa/zonas/Z-2.yaml`: los 12 renglones del cuadro normativo de la Zona Z-2, cada uno con su
cita literal verificada contra el PDF de la ordenanza (fixture `nunoa_zonas.json` + sha256).

**Los parámetros numéricos sí están en el texto extraído.** El spike previo fue concluyente:
`pypdf` saca el cuadro limpio, pero con las notas al pie inyectadas dentro y los rótulos partidos en
cuatro líneas, con el valor lejos de su etiqueta. **La extracción automática queda descartada con
datos**, y la decisión de transcribir a mano en iteración 1 queda validada.

Cargar una zona real rompió el esquema en cuatro sitios — y los cuatro eran hallazgos, no fricción:

1. **La altura se escribe con un "y"**: *"10 pisos y 28,00 m"*. Dos cotas simultáneas en unidades
   distintas, y el motor elige **un** límite. El "y" no es un operador: son dos parámetros.
2. **Una celda puede contener una remisión**: *"Adosamiento: Según OGUC"*. El esquema ahora admite un
   parámetro sin límites solo si declara `estado: desconocido` — antes lo omitía en silencio.
3. **`NORMADOS` desapareció**: una zona real declara `superficie_predial_minima` como parámetro, así
   que el conjunto de un elemento que lo separaba no tenía razón de ser.
4. **`1.600` no se puede transcribir literal**: `decimal_de` lo rechaza como ambiguo y obliga a
   `1600`. El corpus guarda la cita literal y el valor sin ambigüedad.

La zona viaja en `borrador`: la transcribió un programa con supervisión humana, y **eso no es una
firma**. D18 hace que de ahí salga todo `P` más un `FUENTE_SIN_REVISAR`. Hay tests que la firman
explícitamente para probar el cálculo, y tests que verifican que sin firma no afirma nada.

**Lo que un revisor vería hoy en Z-2, firmada:** `C` o `NC` en superficie predial mínima, `cos`,
`cus`, altura, pisos y densidad; y `P` en rasante, antejarín, distanciamiento, cuerpos salientes,
adosamiento y agrupamiento — porque el proyecto todavía no declara esos datos. Seis de doce
evaluables, y **los seis `P` nombrados**, no desaparecidos.

### La verificación tenía un agujero, y era el que importaba

El test de literalidad comprobaba que **la cita** fuera un fragmento del texto. No comprobaba que **el
valor saliera de la cita**: `valor: "0,6"` con la cita `"Coeficiente de ocupación de suelo 0,5"` habría
pasado. Es decir, la defensa contra inventar un número no existía.

Cerrado con `test_el_valor_sale_del_texto_que_la_cita_convoca`: extrae de la cita los números
**asociados a la unidad del límite** (un patrón por unidad: `m`, `m²`, `pisos`, `hab/ha`, `grados`, y
para `adimensional` el número suelto) y exige que el valor sea uno de ellos. Comprobado con una prueba
negativa: con la cita del `0,5`, un valor `0,6` ahora falla.

**Lo que sigue sin cubrir un test:** cuando la cita trae varios números de la misma unidad —el
distanciamiento cita `"4 pisos y altura 12 m o más. 5 m"`, y `12` y `5` son los dos metros—. Eso exige
leer el renglón. La revisión humana de Z-2 sigue pendiente y no la puede cerrar un test.

**Y de paso:** el cargador corregía en silencio un `aplicable` sin límites convirtiéndolo en
`DESCONOCIDO`. Desde que el esquema lo rechaza, ese código quedó inalcanzable y se eliminó — una
corrección muda es peor que un error, porque nadie se entera de que su YAML estaba mal.
