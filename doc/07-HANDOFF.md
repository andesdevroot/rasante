# 07 — Handoff

Documento vivo. Estado **real**, no aspiracional. Se actualiza en el commit que cierra cada tarea
(`00-METODOLOGIA.md`).

---

## Estado actual

**Iteración 1 — Vertical slice, en curso.** T1.1 cerrada (iteración 0 completa: T0.1–T0.6).

| | |
|---|---|
| Tarea en curso | ninguna. Siguiente: **T1.2** (motor de evaluación) |
| Código | `dominio/modelos.py` · `geo/arcgis.py` · `corpus/ingesta.py` · `corpus/` (8 normas citadas) |
| Tests | **96 verdes** offline · **3 de integración** contra la API real, excluidos por defecto |
| Gate | `pytest` verde, sin saltados · `ruff` limpio · `mypy --strict` limpio |
| Árbol git | limpio — todo commiteado |

Reestructuración a `doc/` aplicada el 2026-09-26: `01-VISION.md`, `03-DISENO.md`,
`04-DECISIONES.md` y `07-HANDOFF.md` vienen de `docs/RASANTE-plan-desarrollo.md`, `design.md`,
`docs/decision-comuna.md` y `handoff.md`.

## Último commit

```
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

**T1.2 — Dominio: motor de evaluación** (`src/rasante/dominio/motor.py`).

`evaluar(proyecto, zona) -> list[Veredicto]`. **Es la tarea más delicada de la iteración**: el
invariante que importa es que un dato desconocido dé `P`, **jamás `C`**. Y `densidad` es la única
regla derivada (`numero_viviendas / superficie_predio_ha`), así que el motor recibe el `Proyecto`
completo, no un número suelto.

Reglas en `corpus/oguc/`: `2.1.22` (densidad bruta hab/ha, conversión /4), `2.1.23` (3,50 m por
piso), `5.1.10`/`5.1.11` (cómputo del cos), `5.1.12` (subterráneo fuera del cus).

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
| 2026-09-26 | **`clave_compuesta()` es la única definición de la clave.** `Parametro`, `Veredicto` y (en T1.3) el cargador del corpus deben coincidir, o dos reglas se pisan en el mapping |

Detalle completo de cada una en `04-DECISIONES.md`.
