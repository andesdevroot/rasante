# rasante — design.md

**v0.1 · 2026-09-26 · Iteración objetivo: 1**

Copiloto open source para revisores independientes y DOM. Computa normas urbanísticas
determinísticamente y emite el Formato Tipo MINVU (Circular DDU 514).

Antecedentes y justificación de mercado: `docs/RASANTE-plan-desarrollo.md`.

---

## 1. Alcance

**Iteración 1 (esta spec):** entrada = coordenada → salida = zona del PRC + 3 parámetros
urbanísticos + cita. Atraviesa L0 y L1 completos con TDD.

**Fuera de alcance en iteración 1:** LLM, extracción de PDF, informes DOCX/PDF, UI, demo web,
rasantes, densidad, estacionamientos, admisibilidad.

---

## 2. Decisiones

| # | Decisión | Porqué |
|---|---|---|
| D1 | **Python 3.13**, gestionado con `uv` | 20 años de experiencia del autor; el trabajo es GIS + NLP + orquestación LLM. Detalle en plan §5 |
| D2 | **El motor de reglas es un módulo puro**: solo stdlib (`decimal`, `dataclasses`, `enum`), JSON in / JSON out, sin I/O | Es el único código portable si algún día se necesita Rust o WASM. Evita quedar encerrado en pandas. Innegociable |
| D3 | **El LLM nunca decide ni calcula.** No se usa en iteración 1 | Un veredicto `(NC)` es un acto profesional firmado. Un modelo no puede producirlo |
| D4 | **No hay fine-tuning.** RAG + citas por ID de regla | Un checkpoint congela la norma; el corpus en Git se actualiza con un PR. Fine-tuning alucina citas |
| D5 | **Corpus normativo como repositorio Git versionado** | Foso + flywheel comunitario. `vigencia.desde/hasta` permite evaluar contra la norma vigente a la fecha de ingreso |
| D6 | **Decimal, nunca float** para normativa | Constructibilidad y superficies con error binario son inaceptables en un informe firmado |
| D7 | **`pypdf`/`pdfminer.six`, no PyMuPDF** | PyMuPDF es AGPL-3.0: contamina Apache-2.0 y alcanza servicios en red |
| D8 | **Sin GDAL** — `shapely` + `pyproj`, no geopandas/fiona/rasterio | Bundle de ~80 MB en vez de ~300 MB |
| D9 | **GeoJSON cacheado en disco local** | Reproducibilidad: los tests no dependen de la red ni de que MINVU esté arriba |
| D10 | Código `Apache-2.0`, corpus `CC-BY-4.0` con atribución municipal | — |
| D11 | **La iteración 1 entra por coordenada (lat/lon)**, no por rol ni CIP | El rol de avalúo no tiene geometría pública masiva; la del predio vive en el CIP y parsearlo requiere LLM (iteración 2) |

**Pendiente legal:** verificar el artículo de la Ley 17.336 que excluye textos oficiales del
Estado de protección. Mitigación de diseño ya aplicada: el corpus guarda **parámetros extraídos
+ citas + hash**, no republica documentos municipales íntegros.

---

## 3. Arquitectura de capas

```
L0  FUENTE AUTORITATIVA     ArcGIS REST MINVU (zona, usos, P_DO)   [I/O, red]
                            CIP, Formularios Únicos Nacionales
                             ↓
L1  MOTOR DE REGLAS         Python puro · decimal · sin deps       [PURO]
                            veredicto + traza + valores + cita
                             ↓
L2  LLM                     extracción y redacción                  [ITERACIÓN 2+]
```

**Regla dura:** la frontera entre L0/L1 y L2 es el módulo puro. `src/rasante/dominio/` no
importa nada fuera de la stdlib. Si necesita shapely, la geometría está del lado equivocado.

---

## 4. Modelo de dominio (`src/rasante/dominio/`)

```python
Decimal  # todos los valores normativos

@dataclass(frozen=True)
class Parametro:
    id: str                  # "cos" | "cus" | "altura_maxima"
    valor: Decimal | None
    unidad: str              # "adimensional" | "m"
    estado: Estado           # APLICABLE | NO_APLICA | DESCONOCIDO
    cita: Cita               # norma_id + articulo + texto

@dataclass(frozen=True)
class Zona:
    codigo: str              # "UEe3/Ee3"
    nombre: str
    comuna: str
    parametros: Mapping[str, Parametro]
    vigencia: Vigencia       # desde / hasta
    procedencia: Procedencia # url_fuente, hash_fuente, publicado_do, estado

@dataclass(frozen=True)
class Proyecto:
    """Datos declarados del proyecto. En iteración 1 se construye a mano en tests."""

@dataclass(frozen=True)
class Veredicto:
    parametro_id: str
    codigo: CodigoVeredicto  # C | NC | P | NP | PR
    valor_norma: Decimal | None
    valor_proyecto: Decimal | None
    cita: Cita               # obligatoria: sin cita no hay veredicto
```

`CodigoVeredicto` reproduce la leyenda oficial de la Circular DDU 514:
`C` cumple · `NC` no cumple · `P` pendiente · `NP` no procede · `PR` plan regulador.

**Invariante:** un `Veredicto` sin `Cita` es un error de construcción. Es lo que impide
fabricar veredictos sin respaldo normativo.

**Los 3 parámetros de la iteración 1:** `cos` (coeficiente de ocupación de suelo),
`cus` (coeficiente de constructibilidad), `altura_maxima`.

---

## 5. Esquema del corpus

```
corpus/prc/<REGION>/<comuna>/
  ordenanza.md              # texto fuente (referencia, no se republica íntegro)
  fuentes.yaml              # procedencia + hash
  zonas/<codigo>.yaml       # parámetros extraídos
```

```yaml
zona: "UEe3/Ee3"
nombre: "Zona Especial 3 Área de Parques"
comuna: "Las Condes"
region: "RM"
parametros:
  cos:
    valor: null
    unidad: adimensional
    estado: no_aplica
    cita: { norma_id: "prc:las-condes", articulo: "..." }
  cus: { valor: "2.0", unidad: adimensional, estado: aplicable, cita: {...} }
  altura_maxima: { valor: null, unidad: m, estado: desconocido, cita: {...} }
vigencia: { desde: 1994-05-30, hasta: null }
procedencia:
  instrumento: "PRC Las Condes"
  url_fuente: "https://geoide.minvu.cl/server/rest/services/IPT/PRC_RM_Norte/MapServer/11"
  publicado_do: 1994-05-30
  hash_fuente: "sha256:..."
  extraido_por: "manual"
  revisado_por: null
  estado: borrador          # borrador | revisado | validado
```

`estado: desconocido` es un valor legítimo y **debe propagarse como `(P)` pendiente, nunca
como cumple**. Un dato que no tenemos no puede convertirse en un aprobado.

---

## 6. Flujo de la iteración 1

```
coordenada (lat, lon)
  → reproyectar EPSG:4326 → EPSG:3857          [pyproj]
  → point-in-polygon contra capas PRC cacheadas [shapely STRtree]
  → código de zona
  → lookup en corpus YAML                       [cargador]
  → Zona
  → motor L1 evalúa cos/cus/altura_maxima
  → [Veredicto, Veredicto, Veredicto]  (cada uno con cita)
```

---

## 7. Dependencias permitidas por capa

| Capa | Módulo | Dependencias |
|---|---|---|
| Dominio (L1) | `rasante.dominio` | **solo stdlib** |
| Corpus | `rasante.corpus` | `pyyaml` |
| Geo (L0) | `rasante.geo` | `shapely`, `pyproj`, `httpx`, `orjson` |
| CLI | `rasante.cli` | `typer` |

Un test de arquitectura verifica que `rasante.dominio` no importe nada de terceros.

---

## 8. Decisiones abiertas — requieren tu input

**A1 — CERRADA (2026-09-26).** La iteración 1 entra por **coordenada (lat/lon)**. Ver D11.

**A2. Comuna piloto.** Pendiente de la comparación de datos de T0.3.

**A3. ¿`altura_maxima` o `densidad` como tercer parámetro?** Altura es más simple de testear
(un escalar). Densidad exige superficie del predio y unidad de vivienda. Propongo altura.

---

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| `UPERM`/`UPROH` son texto libre sucio (vi `"culto, culto"` duplicado) | Normalizar a taxonomía canónica; en iteración 1 los usos no se evalúan |
| Los parámetros **no** vienen en los atributos ArcGIS, hay que extraerlos de la ordenanza | Es el trabajo real y el foso. Iteración 1 los carga a mano y validados |
| Datos ausentes tratados como cumplimiento | `estado: desconocido` → `(P)`. Invariante testeado |
| Deriva normativa | `vigencia.desde/hasta` + `hash_fuente` |

---

## 10. Convenciones

- **TDD:** el test se escribe y falla antes de la implementación. Sin excepción.
- **1 tarea = 1 commit atómico.** Detalle en `task.md`.
- Todo veredicto cita. Toda zona cita procedencia con hash.
- Nunca `float` en rutas normativas.
