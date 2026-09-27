# RASANTE

**Copiloto open source para revisores independientes y Direcciones de Obras Municipales (DOM).**

Computa el cumplimiento de la OGUC y del plan regulador comunal de forma **determinística y
auditable**, y apunta a emitir el Formato Tipo oficial de informe del revisor independiente
(Circular DDU 514). El LLM **clasifica y redacta; nunca calcula ni dictamina.**

> ⚠️ **Estado: iteración 1 en curso.** El motor, el corpus ejecutable y la capa de clasificación
> están construidos y probados (432 tests). **Todavía no emite el Formato Tipo de punta a punta**:
> faltan el índice espacial, la CLI y el corpus real de la comuna piloto. Ver [Estado](#estado).

---

## El problema

En Chile, el informe del revisor independiente es un **acto profesional firmado bajo responsabilidad
civil y penal**. Un `(NC)` puede costarle a alguien meses y millones; un `(C)` mal puesto, una
edificación que no debería haberse aprobado.

Ese cálculo se hace hoy a mano, artículo por artículo, comuna por comuna: `cus`, `cos`, altura,
densidad, rasantes, agrupamiento. Es lento, es caro y **no es reproducible**: dos revisores
competentes llegan a números distintos porque la ordenanza se lee distinto.

La causa no es falta de inteligencia. Es que el trabajo consiste en aplicar reglas escritas a datos
que hay que ir a buscar, y el 100 % de la variación está en cuáles reglas y con qué datos — no en la
aritmética.

## La idea

Separar lo que **se puede demostrar** de lo que **hay que interpretar**, y no dejar que lo segundo
contamine lo primero.

| | Quién | Por qué |
|---|---|---|
| **Calcular** | Motor determinista (`Decimal`, sin `float`) | La aritmética normativa no admite una muestra de un modelo |
| **Decidir qué regla rige** | Corpus ejecutable (YAML) | La norma es pública y debe poder auditarse línea por línea |
| **Clasificar** (¿es una manzana? ¿es una fusión predial? ¿qué destino tiene?) | Modelo tipado, con **portero de confianza** | No es aritmética: es un juicio sobre texto. Y cuando no alcanza el umbral, **no se resuelve** |
| **Redactar** | LLM (iteración 2) | Prosa, no veredictos |

Un dato que no tenemos da **`P` (pendiente)**. Jamás `C` (cumple).

## El invariante que sostiene el producto

> **Lo que no se puede verificar no se afirma, en ninguna dirección.**

Un `P` no es una aprobación tibia: es un revisor diciendo *"me falta este dato, y te digo cuál"*. El
motor lo aplica en cascada: si falta el dato del proyecto, si no se sabe cuál de los límites rige, si
el corpus que fija el valor no tiene firma humana, si el expediente no acredita la fusión predial —
en todos esos casos sale `P`, y ninguno de ellos se redondea hacia el lado permisivo.

Está verificado por tests, no por convención. Los invariantes completos están en
[`doc/05-VALIDACION.md`](doc/05-VALIDACION.md).

## Arquitectura

```
  coordenada ──▶ L0 geo ──▶ zona (PRC)
                              │
  expediente ──▶ L0 clasificación ──▶ hechos   ← JEV / cualquier proveedor
                              │
                              ▼
                        L1 motor determinista ──▶ veredictos + hallazgos
                              │                    (cada uno con su cita y su hash)
                              ▼
                        L2 informe (Formato Tipo DDU 514)      ← pendiente
```

`rasante.dominio` (la capa L1) **importa solo la stdlib**. Lo impone
`tests/test_arquitectura.py`: sin red, sin YAML, sin dependencias. Es lo que hace que el veredicto
sea reproducible dentro de diez años.

### El corpus es ejecutable

`corpus/` no es documentación: es el **programa** que el motor interpreta. Cada artículo declara sus
`derivaciones` (cómo se calcula), sus `hechos` (qué condición rige) y sus `preguntas` (lo que no se
puede calcular y hay que clasificar). Una expresión del corpus se evalúa con `ast` y lista blanca,
**nunca con `eval`**: el corpus es dato que llega de fuera, eventualmente por PR de un tercero.

```yaml
# corpus/oguc/2.6.4.yaml
hechos:
  dimension_a:
    expresion: superficie_predio_m2 >= 5 * superficie_predial_minima and superficie_predio_m2 >= 5000
hechos_pendientes:
  dimension_c: 'La fusión predial del art. 63 del DFL 458 exige el historial registral.'
preguntas:
  dimension_c:
    tipo: noul
    instrucciones: >
      El predio del proyecto es el resultado de una fusión predial acogida al artículo 63 del
      DFL 458... Si el expediente no lo acredita, responde con una probabilidad baja.
```

## Dónde entra JEV (y dónde no)

[JEV](https://openrouter.ai/) (TypeSafe, `typesafe/jev-1.13`, vía OpenRouter) es el proveedor por
defecto de la capa de clasificación. Su contrato — `choice` / `noul` / `score`, un estado y varias preguntas
respondidas en una sola pasada — es exactamente la forma que necesita el hueco que el motor no puede
llenar: *"¿el predio constituye una manzana existente?"* no es una resta, es una lectura.

La guía oficial de JEV recomienda literalmente esta arquitectura —*"route with Jev, **compute in
code**, write with an LLM"*— y advierte que el modelo **no es confiable en aritmética, conteo ni
comparación de fechas**. Eso es, precisamente, lo que hace el motor determinista y no el modelo.

El contrato es un **protocolo**, no un vendor: DeepSeek, un modelo local o un proveedor guionizado
lo cumplen igual. Hay tests que corren con los cuatro.

**Lo que JEV no hace acá:** no decide cumplimiento, no calcula, no firma. Devuelve una respuesta
tipada con una confianza; el **portero** decide si esa confianza alcanza. Si no alcanza, el hecho
queda indeterminado y el veredicto sale `P`.

> **Sobre "el primer uso de JEV en Chile":** no lo afirmamos. No encontramos evidencia pública de un
> uso anterior con este propósito, pero **la ausencia de evidencia no es evidencia de ausencia**, y
> una búsqueda nuestra no es un censo. Lo que sí podemos sostener es más acotado y más útil: el
> modelo se usa donde su propia documentación dice que sirve, y **no** donde dice que falla.

## Estado

**Iteración 0 — Cimientos** ✅ completa (entorno, guardián de arquitectura, ingestor ArcGIS,
troceador de la OGUC, corpus curado con citas y hashes).

**Iteración 1 — Vertical slice** (coordenada → zona → parámetros):

| | |
|---|---|
| ✅ | Modelos de dominio con invariantes de construcción (`Decimal` obligatorio, cita obligatoria) |
| ✅ | Motor determinista, tres valores (`C` / `NC` / `P`) |
| ✅ | Corpus ejecutable: esquema, cargador, intérprete `ast` con lista blanca |
| ✅ | Verificador de factibilidad geométrica (el proyecto imposible que aprobaba parámetro por parámetro) |
| ✅ | Selección del límite vigente por hechos, con `P` si el hecho es indeterminado |
| ✅ | D18: un corpus sin firma humana no aprueba nada |
| ✅ | Capa de clasificación tipada con portero de confianza (D19) |
| ✅ | **Puente**: el corpus pregunta, el motor recibe hechos externos |
| ✅ | **Excepciones de aplicación general**: el +50 % y el +30 % de `cus` del Conjunto Armónico (OGUC 2.6.5) llegan al motor como factor sobre el valor que fija cada PRC |
| ⬜ | Índice espacial (reproyección + point-in-polygon) |
| ⬜ | CLI |
| ✅ | **Primera zona real transcrita**: Z-2 de Ñuñoa, con cada cita verificada contra el PDF de la ordenanza |
| ⬜ | Resto de las zonas de la comuna piloto |
| ⬜ | Validación contra expedientes reales |

**Lo que esto significa hoy, sin adornos:** el motor calcula y el corpus manda, pero todavía no hay
un comando que reciba una coordenada y devuelva el informe. La cadena está probada de punta a punta
con datos de test, no con expedientes reales. `task.md` tiene la cola exacta.

## Uso

```bash
uv sync
./gate.sh          # pytest + ruff + mypy sobre src Y tests. Debe decir "GATE EN VERDE"
```

El motor, sin red y sin modelos:

```python
from decimal import Decimal
from pathlib import Path

from rasante.corpus.cargador import cargar_preguntas, cargar_reglas, cargar_zona
from rasante.clasificacion.proveedor import ProveedorGuionizado
from rasante.puente import resolver_hechos
from rasante.dominio.modelos import Proyecto
from rasante.dominio.motor import evaluar

reglas = cargar_reglas(Path("corpus"))

# Los hechos que el corpus no puede calcular se clasifican contra el expediente.
# Sin documento no se consulta al proveedor: no se adivina sobre la nada.
resultado = resolver_hechos(
    cargar_preguntas(Path("corpus")),
    {"memoria": "El plano de loteo acredita la fusión predial del art. 63."},
    ProveedorGuionizado({}),          # en producción: ProveedorJev(clave)
)

proyecto = Proyecto(superficie_predio_m2=Decimal("1000"), numero_viviendas=1)

# La zona sale de un YAML del plan regulador (el corpus de la comuna piloto llega en T1.14).
ruta_zona = Path("corpus/zonas/<comuna>/<zona>.yaml")
veredictos = evaluar(proyecto, cargar_zona(ruta_zona), reglas, resultado.hechos)

for v in veredictos:
    print(v.clave, v.codigo.value, v.cita.norma_id, v.cita.articulo)
```

Los tests de integración contra la API real de MINVU están **excluidos por defecto** (marcador
`integracion`). Se corren con `RASANTE_INTEGRACION=1`:

```bash
RASANTE_INTEGRACION=1 uv run pytest -m integracion
```

## Estructura

```
src/rasante/
  dominio/         # L1 — motor puro, SOLO stdlib (D2, impuesto por test)
    modelos.py     #   tipos con invariantes de construcción
    motor.py       #   evaluación y tres valores
    reglas.py      #   intérprete del corpus (ast + lista blanca, sin eval)
    factibilidad.py#   verificador geométrico
    vocabulario.py #   vocabulario cerrado
  corpus/          # YAML → dominio (esquema, cargador, ingesta)
  clasificacion/   # contrato tipado + portero de confianza + proveedores
  geo/             # ArcGIS REST del IPT (MINVU)
  puente.py        # clasificación → hechos del motor
corpus/            # el corpus normativo (dato, no código)
doc/               # fuente de verdad del proyecto (SDD)
task.md            # cola de trabajo con estado por tarea
```

## Metodología

El proyecto se desarrolla con **Spec-Driven Development**: `doc/` es la fuente de verdad y `task.md`
la cola de trabajo. TDD estricto (RED → GREEN → REFACTOR), un commit atómico por tarea, **nunca un
commit con tests en rojo**, y el traspaso de estado viaja en el commit que cierra la tarea. Está
descrito en [`doc/00-METODOLOGIA.md`](doc/00-METODOLOGIA.md).

Las citas del corpus no se escriben de memoria: `tests/test_realidad_corpus.py` contrasta cada una
contra el artículo real, verificado por hash. **Ya cazó tres citas parafraseadas.**

## Corpus y fuentes

| | |
|---|---|
| OGUC | Texto consolidado de MINVU, 577 pp, `sha256:64cf1b7c…b127acc` |
| PRC | ArcGIS REST del IPT (`geoide.minvu.cl`), por región |
| DDU 514 | Circular del MINVU con el Formato Tipo (escaneado) |

El corpus guarda **citas, no texto íntegro**: norma, artículo, URL, hash y fecha. Eso es deliberado —
ver [`doc/06-OPERACION.md`](doc/06-OPERACION.md).

## Licencias

- **Código:** Apache-2.0 — [`LICENSE`](LICENSE)
- **Corpus normativo:** CC-BY-4.0 — [`LICENSE-CORPUS`](LICENSE-CORPUS)

## Advertencia

RASANTE **no es un informe firmado** y no reemplaza al revisor independiente ni el pronunciamiento de
la DOM. Es una herramienta de cálculo y trazabilidad: cada veredicto sale con la norma que lo
respalda para que una persona lo revise y lo firme. Un `P` significa exactamente eso — que hace falta
una persona.
