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
| T1.10 | El puente: de las preguntas a los hechos | ✅ | `[T1.10]` |
| T1.10b | Excepciones de aplicación general: factor y acogerse | ✅ | `[T1.10b]` |
| T1.11 | Geo: índice espacial de zonas (sin reproyección) | ✅ | `[T1.11]` |
| T1.17 | Motor: caché de AST, procedencia de `None` y orden documentado | ✅ | `[T1.17]` |
| T1.12 | Resolución coordenada → zona | ⬜ |
| T1.13 | CLI | ⬜ |
| T1.14a | Corpus real: Zona Z-2 de Ñuñoa (primera zona transcrita) | ✅ | `[T1.14a]` |
| T1.14b | La prosa normativa del cuadro (decisión de diseño) | ⬜ |
| T1.14c | Hechos de agrupamiento (la altura cambia según el tipo) | ⬜ |
| T1.14 | Corpus real: resto de las zonas de la comuna piloto | ⬜ |
| T1.15 | Validación contra predios reales | ⬜ |
| T1.16 | CI en GitHub Actions (barato, fuera del camino crítico) | ⬜ |

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
dato faltante dan `None`, nunca excepción: eso es `P`, no un fallo. Lo que quedaba hardcodeado era solo
`MAXIMOS` (el sentido de la comparación): **cerrado en T1.9**, cuando el `sentido` pasó a declararlo
el corpus con el esquema exigiéndolo. Un test verifica sobre el código
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

### ✅ T1.10 — El puente: de las preguntas a los hechos

La capa de clasificación existía y estaba probada, pero **no estaba conectada a nada** (D19 quedaba
a medias). `2.6.4` declara tres `hechos_pendientes` —`dimension_b`: ¿es una manzana existente?,
`dimension_c`: ¿es una fusión predial del art. 63?, `condicion_uso`— que el motor no puede
calcular. Ahora el corpus declara **preguntas tipadas** para ellos y `rasante/puente.py` las
resuelve contra el expediente.

- `motor.evaluar/clasificar` y `factibilidad.verificar` aceptan `hechos_externos`. Un hecho externo
  **no puede sobrescribir** uno del corpus (`ErrorHechoDuplicado`): con dos fuentes, cuál gana sería
  una decisión implícita, y un hecho decide **cuál límite rige**.
- `corpus` gana `preguntas:` por hecho, con `cita` obligatoria y `verdadero_si` para las
  categóricas. Sin `verdadero_si`, una respuesta `choice` no tiene forma determinista de volverse
  booleana.
- Tres invariantes del puente, cada uno con su test: **sin documento no se consulta al proveedor**
  (no se gasta una llamada para que un modelo adivine sobre la nada); **lo que no se resuelve queda
  `None`** —y por lo tanto `P`—, nunca en el límite permisivo; **una respuesta categórica se traduce
  por el `verdadero_si` del corpus**, nunca por la opción más probable.
- El circuito completo queda probado de punta a punta: `cos` base 0,5 con excepción 0,8 condicionada
  a `dimension_c`, sobre un proyecto de 0,6 → `C` con el hecho en `True`, `NC` en `False`, `P` en
  `None`.

**El puente no emite hallazgos a propósito.** El único lugar que reporta `CLASIFICACION_INDETERMINADA`
es `factibilidad`, por parámetro y por límite; si el puente emitiera además uno por hecho, el mismo
dato faltante aparecería dos veces en el informe. El puente expone `motivos()` —**por qué** quedó
pendiente— y `factibilidad` dice **qué** falta.

**Dos huecos que aparecieron al conectar** — **ambos cerrados en T1.10b**:

1. El bloque `excepcion:` de `corpus/oguc/2.6.5.yaml` **no lo lee ningún código**. El "+50 % de cus
   por Conjunto Armónico" está escrito en el corpus y nunca llega a ser un `Limite`. `cargar_reglas`
   lee `derivaciones`, `hechos` y `relaciones`, y nada más.
2. `Proyecto.clasificaciones` se **valida** (`modelos.py` rechaza lo que no esté en `CONDICIONES`)
   pero **no se consume** en ninguna parte. Es un segundo mecanismo para lo mismo que
   `hechos_externos`, y peor: un `frozenset` no puede expresar "no se sabe", así que no puede
   alimentar un `P`. `hechos_externos` lo supersede.

### ✅ T1.14a — Primera zona real: Z-2 de Ñuñoa

`corpus/prc/RM/nunoa/zonas/Z-2.yaml`: los 12 renglones del cuadro normativo del Artículo 26, cada uno con su
cita literal. El fixture `tests/fixtures/nunoa_zonas.json` guarda el texto tal como salió de `pypdf`
más el sha256 del PDF, y `tests/test_corpus_nunoa.py` exige que **cada cita sea un fragmento literal**
de ese texto: si alguien inventa un número, ese test lo caza.

**La extracción automática queda descartada con datos.** El cuadro sale limpio, pero con las notas al
pie inyectadas dentro (`92 Modifíquese el Artículo 26º…`) y los rótulos partidos en cuatro líneas con
el valor lejos de su etiqueta —el `60%` de un renglón aparece cuatro líneas después de su rótulo—. Un
parser heurístico se equivoca en silencio. La transcripción a mano de iteración 1 queda validada.

**Cuatro cosas que el esquema no sabía**, ninguna visible en tests sintéticos:

1. **La altura se escribe con un "y"**: `"10 pisos y 28,00 m"`. Dos cotas superiores simultáneas en
   unidades distintas, y `_limite_vigente` elige **una**. El "y" no es un operador lógico: son dos
   parámetros, `altura_maxima` y `pisos_maximos`, y ambos deben cumplirse. El informe gana precisión,
   porque dice **cuál** de las dos se incumplió.
2. **Una celda puede contener una remisión**: `"Adosamiento: Según OGUC"`. El esquema ahora admite un
   parámetro sin límites **si y solo si** declara `estado: desconocido`. Omitirlo lo hacía desaparecer
   del informe en silencio.
3. **`NORMADOS` desapareció**: una zona real declara `superficie_predial_minima` como parámetro, así
   que el conjunto de un elemento que lo separaba no tenía razón de ser.
4. **`1.600` no se puede transcribir literal**: `decimal_de` lo rechaza como ambiguo y obliga a
   `1600`. El corpus guarda la cita literal y el valor sin ambigüedad.

**Estado del cálculo.** Firmada, Z-2 da `C`/`NC` en 6 de sus 12 parámetros —superficie predial mínima,
`cos`, `cus`, altura, pisos y densidad— y `P` en los otros 6, **nombrados**: rasante, antejarín,
distanciamiento, cuerpos salientes, adosamiento y agrupamiento. Sin firmar da todo `P` más un
`FUENTE_SIN_REVISAR`: la zona viaja en `borrador` porque la transcribió un programa con supervisión
humana, y eso no es una firma.

**Deuda de proceso.** `T1.14` pide presentar cada extracción para validación **antes** del commit, y
esta se commiteó primero. Se cerró la parte mecánica: el test de literalidad **no bastaba** —verificaba
que la cita fuera literal, no que el valor saliera de ella, así que `valor: "0,6"` con la cita del
`0,5` pasaba igual—. Ahora `test_el_valor_sale_del_texto_que_la_cita_convoca` extrae los números de la
cita y exige que el valor sea uno de los asociados a su unidad. Demostrado con una prueba negativa.

Lo que **no** cierra un test es leer bien el renglón cuando la cita trae varios números de la misma
unidad: la **revisión humana de Z-2 sigue pendiente**.

### ⬜ T1.14b — La prosa normativa del cuadro (decidir antes de transcribir)

Z-2 no termina en el cuadro. Debajo hay dos párrafos que **no son filas**:

> *"En todos los Conjuntos Habitacionales cuya altura sean mayores a tres pisos, deberá destinarse un
> 30% del total del terreno a Área Libre de Esparcimiento…"*
> *"Los espacios a ocuparse en el subsuelo, podrán acercarse hasta una distancia de 2,5 m del deslinde
> predial…"*

No caben en `parametros:` con `limites:`: son **condiciones sobre el proyecto** que no son un tope.
Hay que decidir si se modelan como hechos, como un tipo nuevo de regla, o como parámetros derivados
—área libre como `superficie_libre_m2 / superficie_predio_m2`—.

**Por qué antes de la zona 3:** la misma prosa se repite en casi todas las zonas. Decidirlo en la
zona 20 obliga a rehacer 19 transcripciones.

### ⬜ T1.14c — Hechos de agrupamiento

`Z-1` no tiene una altura máxima: tiene **tres**, según el tipo de agrupamiento.

```
edificación continua .................. 17,50 m y 6 pisos
aislada sobre continua ................ 25,50 m y 9 pisos
edificación (general) ................. 44,00 m y 15 pisos
```

El mecanismo existe (`cuando: [hecho]`), pero el hecho no: `agrupamiento` es hoy un parámetro
`desconocido` en Z-2, porque el modelo no sabe expresar "uno de estos tipos". Hay que decidir si el
agrupamiento se **clasifica** (JEV, como `dimension_b`) o se **declara** en el expediente.

Confirma que borrar `CONDICIONES` en T1.10b fue correcto —era un `frozenset` decorativo— pero que el
caso de uso es real y necesita hechos del corpus.

### ✅ T1.11 — Geo: índice espacial de zonas

`geo/indices.py`: `IndiceZonas.buscar(lat=..., lon=...)` responde la pregunta que separa una
coordenada de un veredicto. Con `shapely` (y `STRtree`, no un barrido lineal).

**`pyproj` se descartó, y eso es lo importante de esta tarea.** El diseño pedía reproyectar
EPSG:4326 → 3857, pero al mirar el dato: el servicio de MINVU **devuelve GeoJSON en 4326** y el
ingestor no pide `outSR`, así que el polígono y el punto ya están en el mismo CRS. Point-in-polygon
es exacto en cualquier CRS —no hay áreas ni distancias— así que reproyectar era una dependencia
pesada a cambio de nada. Si alguna capa llega proyectada, se reproyecta en la **ingesta**, no en cada
consulta.

**Tres decisiones que el código deja escritas:**

1. **`lat`/`lon` son keyword-only.** GeoJSON escribe `(lon, lat)` y esta API pide `(lat, lon)`.
   Invertirlos **no se puede atrapar con validación**: `-70,6` es una latitud válida (la Antártida),
   así que la consulta devolvería `None` y parecería que el predio está fuera del PRC. La única
   defensa real es obligar a nombrarlos.
2. **El índice no decide en los bordes.** Un punto sobre el límite entre dos zonas intersecta las
   dos: `buscar` devuelve una en orden determinista y `buscar_todas` expone la ambigüedad. Quien
   deba resolverla es T1.12.
3. **La reparación de geometría se registra.** Un anillo inválido es común en datos municipales;
   `make_valid` lo arregla pero **descarta área**. `IndiceZonas.reparadas` dice qué zonas se
   tocaron, para que no se pierda cobertura en silencio.

**Verificado sobre datos reales:** el fixture grabado de la API, y para cada polígono su propio
centro cae en su propia zona.

**Hallazgo para T1.12:** el servicio devuelve **3 de 40 códigos de zona con espaciado irregular**
(`'MH- 1'`, `'ZCH- 1'`). El índice los devuelve tal cual —normalizarlos escondería que el corpus y el
servicio no coinciden— y la reconciliación es de T1.12, con su propio test.

### ✅ T1.17 — Motor: caché de AST, procedencia de `None` y orden documentado

Tanda de mejora del core pedida para la base del paper. **Primero se midió**, porque dos de las
cuatro tareas se justificaban con afirmaciones sobre el costo que resultaron incompletas.

**T1 — caché de árboles sintácticos. Hecha, medida.** La justificación decía "el parseo `ast.parse()`
se repite"; medido, `ast.parse` es el **37 %** de `arbol()` y el **63 %** es el recorrido de la lista
blanca `_revisar`. Memorizar `arbol()` cubre los dos. `lru_cache(maxsize=1024)`, **no** un `dict` del
módulo: uno sin cota es una fuga en un proceso de vida larga.

| parámetros | antes | después | mejora |
|---|---|---|---|
| 12 (Z-2 real) | 209,2 µs | 67,9 µs | **3,1×** |
| 50 (sintética) | 985,5 µs | 255,7 µs | **3,9×** |
| 200 (sintética) | 3.652,2 µs | 960,3 µs | **3,8×** |

Corpus real: 9 expresiones distintas, 9 *misses*, 1,59 M *hits*. Firma de `evaluar()` sin cambios.

**T2 — pre-cálculo de `valores_normados`. Rechazada, con datos.** El mecanismo propuesto no es
implementable: `Zona` es un dataclass congelado cuyo `parametros` es un `MappingProxyType`, o sea
**no es hasheable**, así que `lru_cache` levanta `TypeError`. Y hashear la zona entera en cada
llamada costaría más que el bucle que evita. Medido, `valores_normados` es el **5,5 %** de `evaluar()`
con 200 parámetros. Se documenta en vez de implementarse.

**T3 — procedencia de `None`. Hecha, con el vocabulario corregido.** El propuesto mezclaba dos causas
distintas bajo `"corpus_indeterminado"` y no cubría un cuarto caso. Los reales, derivados del código:

| valor | cuándo | cómo se arregla |
|---|---|---|
| `dato_faltante` | la expresión nombra algo que no está | consiguiendo el dato |
| `expresion_no_calculable` | están todos los nombres y no dio número | **en el corpus** (división por cero) |
| `externo_indeterminado` | vino de `hechos_externos` en `None` | revisando el expediente |
| `hecho_no_declarado` | nadie lo declaró | defensivo; `validar_corpus` ya lo bloquea |

Tres estados, no dos: ausente en `procedencia` significa "se determinó". Y el invariante que lo hace
seguro: **`_decidir()` no lee la procedencia**, verificado con un test sobre el código fuente —si el
veredicto leyera un campo de diagnóstico, el diagnóstico empezaría a decidir.

**T4 — orden de verificación documentado. Hecho.** Seis pasos con su porqué y su decisión (D16, D18,
D20) en el docstring de `_decidir`, más dos tests: que el orden esté escrito y que **ningún `P` ni
`NO_PROCEDE` aparezca después de una comparación** en el código.

**Riesgo que queda anotado:** el "bucle de aprendizaje offline" que justifica T3 debe alimentar la
**priorización del corpus**, nunca el veredicto ni un ajuste de modelo (D3, D4).

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

### ⬜ T1.14 — Corpus real: el resto de las zonas de Ñuñoa

- **Desbloqueada: A2 = Ñuñoa.** Entregable: 3–5 zonas transcritas **a mano** de la ordenanza,
  citadas y revisadas. Z-2 ya está (T1.14a); seguir con las que el texto refundido expone limpiamente
  (`Z-3`, `Z-3A`, `Z-4`, `Z-5`, `Z-6`).
- **Ojo (T1.14b):** decidir la prosa normativa **antes** de la tercera zona, o se rehacen las
  transcripciones.
- **Ojo (T1.14c):** `Z-1` y sus variantes necesitan los hechos de agrupamiento. Se puede esquivar
  transcribiendo primero las zonas de un solo régimen de altura.
- **Ojo (A3):** para `densidad` hay que declarar si la zona usa densidad **bruta** o **neta**. Sin
  eso el cálculo es ambiguo y el veredicto queda sin fundamento. Lo mismo con el calificador de `cos`.
- **Resuelto en T1.14a:** los límites simultáneos (`"10 pisos y 28,00 m"`) se modelan como **dos
  parámetros**, no como un operador. El esquema ya no lo tiene pendiente; el agrupamiento sí
  (T1.14c).
- **Test primero:** test de integración que carga las zonas reales y verifica que cada parámetro
  tiene cita y que la procedencia tiene `hash_fuente`.
- **Aceptación:** cada valor trazable a un artículo de la ordenanza. `estado: revisado` con
  `revisado_por` poblado. **Se presenta cada extracción para validación antes del commit.**
- **Commit:** `feat(corpus): zonas iniciales de <comuna> con parametros citados [T1.14]`

### ⬜ T1.16 — CI en GitHub Actions

`gate.sh` ya existe; el workflow son diez líneas. El repo es público y hoy **no hay ninguna señal de
que los tests pasen**: sin CI ni badge, un visitante no tiene cómo saberlo. No está en el camino
crítico y no desbloquea nada, pero es lo más barato del proyecto y protege todo lo demás.

**Ojo:** `cache/` está en `.gitignore`, así que el CI corre **solo offline** — que es exactamente lo
que ya hace `pytest` por defecto (`-m 'not integracion'`).

- **Entregable:** `.github/workflows/gate.yml` que corre `./gate.sh`.
- **Commit:** `ci: corre gate.sh en cada push y pull request [T1.16]`

### ⬜ T1.15 — Validación contra predios reales

- **Objetivo:** cerrar la iteración 1 con evidencia. Metodología y métrica en `doc/05-VALIDACION.md`.
- **Entregable:** `doc/` con precisión y recall sobre N expedientes reales ya aprobados.
- **Nota:** sin esto la iteración **no se declara cerrada**.
- **Commit:** `docs: validacion de la iteracion 1 contra predios reales [T1.15]`
