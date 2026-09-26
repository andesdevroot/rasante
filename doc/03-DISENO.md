# 03 — Diseño

**v0.2 · 2026-09-26**

Copiloto open source para revisores independientes y DOM. Computa normas urbanísticas
determinísticamente y emite el Formato Tipo MINVU (Circular DDU 514).

- Problema, mercado y fuentes verificadas: `01-VISION.md`
- Alcance y qué queda fuera: `02-ALCANCE.md`
- Decisiones de alcance y datos (A1–A3): `04-DECISIONES.md`
- Estrategia de tests y riesgos: `05-VALIDACION.md`
- Cómo correr: `06-OPERACION.md`

---

## 1. Decisiones de arquitectura

| # | Decisión | Porqué |
|---|---|---|
| D1 | **Python 3.14**, gestionado con `uv` | Experiencia del autor; el trabajo es GIS + NLP + orquestación de LLM. Detalle en `01-VISION.md` §5 |
| D2 | **El motor de reglas es un módulo puro**: solo stdlib (`decimal`, `dataclasses`, `enum`), JSON in / JSON out, sin I/O | Es el único código portable si algún día se necesita Rust o WASM. Evita quedar encerrado en pandas. Innegociable |
| D3 | **El LLM nunca decide ni calcula.** No se usa en iteración 1 | Un veredicto `(NC)` es un acto profesional firmado. Un modelo no puede producirlo |
| D4 | **No hay fine-tuning.** RAG + citas por ID de regla | Un checkpoint congela la norma; el corpus en Git se actualiza con un PR. Fine-tuning alucina citas |
| D5 | **Corpus normativo como repositorio Git versionado** | Foso y flywheel comunitario. La validación humana por PR es el activo escaso |
| D6 | **Decimal, nunca float** para normativa | Constructibilidad y superficies con error binario son inaceptables en un informe firmado |
| D7 | **`pypdf`/`pdfminer.six`, no PyMuPDF** | PyMuPDF es AGPL-3.0: contamina Apache-2.0 y alcanza servicios en red |
| D8 | **Sin GDAL** — `shapely` + `pyproj`, no geopandas/fiona/rasterio | Bundle de ~80 MB en vez de ~300 MB |
| D9 | **GeoJSON cacheado en disco local** | Reproducibilidad: los tests no dependen de la red ni de que MINVU esté arriba |
| D10 | Código `Apache-2.0`, corpus `CC-BY-4.0` con atribución municipal | — |
| D11 | **La iteración 1 entra por coordenada (lat/lon)**, no por rol ni CIP | El rol de avalúo no tiene geometría pública masiva; la del predio vive en el CIP y parsearlo requiere LLM (iteración 2) |
| D12 | **`P_DO` es procedencia, no vigencia** | Ver §2.3. Es la publicación original del instrumento, no la del texto consolidado |

## 2. Arquitectura de capas

```
L0  FUENTE AUTORITATIVA     ArcGIS REST MINVU (zona, usos, P_DO)   [I/O, red]
                            CIP, Formularios Únicos Nacionales
                             ↓
L1  MOTOR DE REGLAS         Python puro · decimal · sin deps       [PURO]
                            veredicto + traza + valores + cita
                             ↓
L2  LLM                     extracción y redacción                  [ITERACIÓN 2+]
```

**Regla dura:** la frontera entre L0/L1 y L2 es el módulo puro. `src/rasante/dominio/` no importa
nada fuera de la stdlib. Si necesita shapely, la geometría está del lado equivocado. Lo vigila
`tests/test_arquitectura.py`.

## 2.1 Modelo de dominio (`src/rasante/dominio/`)

```python
Decimal  # todos los valores normativos

@dataclass(frozen=True)
class Cita:
    norma_id: str            # "oguc" | "prc:nunoa"
    articulo: str            # "2.6.3"
    texto: str

@dataclass(frozen=True)
class Parametro:
    id: str                  # "cos" | "cus" | "altura_maxima" | "densidad"
    calificador: str | None  # cos: "primer_piso" | "pisos_superiores"
                             # densidad: "bruta" | "neta"
    valor: Decimal | None
    unidad: str              # "adimensional" | "m" | "viv/ha"
    estado: Estado           # APLICABLE | NO_APLICA | DESCONOCIDO
    cita: Cita

@dataclass(frozen=True)
class Zona:
    codigo: str              # "Z-4"
    nombre: str
    comuna: str
    parametros: Mapping[str, Parametro]
    vigencia: Vigencia       # desde / hasta — NO derivada de P_DO (D12)
    procedencia: Procedencia # url_fuente, hash_fuente, publicado_do, estado

@dataclass(frozen=True)
class Proyecto:
    """Datos declarados del proyecto. Con `densidad` en alcance (A3) deja de ser un
    placeholder: el motor necesita estos campos de verdad, no relleno de tests."""
    superficie_predio_m2: Decimal
    numero_viviendas: int
    superficie_edificada_m2: Decimal | None   # para `cus`
    altura_m: Decimal | None                  # para `altura_maxima`

@dataclass(frozen=True)
class Veredicto:
    parametro_id: str
    calificador: str | None
    codigo: CodigoVeredicto  # C | NC | P | NP | PR
    valor_norma: Decimal | None
    valor_proyecto: Decimal | None
    cita: Cita               # obligatoria: sin cita no hay veredicto
```

`CodigoVeredicto` reproduce la leyenda oficial de la Circular DDU 514:
`C` cumple · `NC` no cumple · `P` pendiente · `NP` no procede · `PR` plan regulador.

**Invariante:** un `Veredicto` sin `Cita` es un error de construcción. Es lo que impide fabricar
veredictos sin respaldo normativo.

**Calificadores (resuelto en A3).** `calificador` no es decorativo: sin él dos reglas distintas
colisionan en la misma clave.

- `cos` distingue "ocupación de suelo" (`0,6`) de "ocupación de suelo **pisos superiores**" (`0,4`)
  — ambos verificados en la misma zona del texto refundido de Ñuñoa. Un `cos` único perdería uno.
- `densidad` distingue **bruta** (sobre el predio) de **neta** (descontando vialidad). Son números
  distintos para la misma zona; el corpus debe declarar cuál usa cada una.

**`densidad` es la única regla derivada.** Las otras tres comparan un valor del proyecto contra el
de la norma. La densidad se calcula: `numero_viviendas / (superficie_predio_m2 / 10_000)` en viv/ha.
Por eso el motor recibe el `Proyecto` completo y no un número suelto.

## 2.2 Esquema del corpus

```
corpus/prc/<REGION>/<comuna>/
  ordenanza.md              # texto fuente (referencia, no se republica íntegro)
  fuentes.yaml              # procedencia + hash
  zonas/<codigo>.yaml       # parámetros extraídos
```

```yaml
zona: "Z-4"
nombre: "Z-4"
comuna: "Ñuñoa"
region: "RM"
parametros:
  # La clave es COMPUESTA (id.calificador). Con `cos` y `densidad` teniendo variantes, una
  # clave por `id` produciria claves duplicadas en el YAML, y el parser descartaria una en
  # silencio perdiendo una regla. Leccion de diseño, no estilo.
  cos.primer_piso:
    id: cos
    calificador: primer_piso
    valor: "0.6"            # la ordenanza escribe "0,6": coma decimal, ver T1.3
    unidad: adimensional
    estado: aplicable
    cita: { norma_id: "prc:nunoa", articulo: "..." }
  cos.pisos_superiores:
    id: cos
    calificador: pisos_superiores
    valor: "0.4"
    unidad: adimensional
    estado: aplicable
    cita: { norma_id: "prc:nunoa", articulo: "..." }
  cus:
    id: cus
    calificador: null
    valor: "3.6"
    unidad: adimensional
    estado: aplicable
    cita: { norma_id: "prc:nunoa", articulo: "..." }
  altura_maxima:
    id: altura_maxima
    calificador: null
    valor: null
    unidad: m
    estado: desconocido
    cita: { norma_id: "prc:nunoa", articulo: "..." }
  densidad.bruta:
    id: densidad
    calificador: bruta      # bruta o neta: el corpus DEBE declararlo (A3)
    valor: null
    unidad: viv/ha
    estado: desconocido
    cita: { norma_id: "prc:nunoa", articulo: "..." }
vigencia:
  desde: null               # NO se deriva de P_DO (D12)
  hasta: null
  nota: "reconstruir la historia de enmiendas desde la ordenanza"
procedencia:
  instrumento: "PRC Ñuñoa"
  url_fuente: "https://www.nunoa.cl/app/uploads/2025/06/Ordenanza-PRC-Texto-Refundido-..."
  publicado_do: 1989-10-27  # publicación ORIGINAL del instrumento
  hash_fuente: "sha256:..."
  extraido_por: "manual"
  revisado_por: null
  estado: borrador          # borrador | revisado | validado
```

`estado: desconocido` es un valor legítimo y **debe propagarse como `(P)` pendiente, nunca como
cumple**. Un dato que no tenemos no puede convertirse en un aprobado.

## 2.3 Por qué `P_DO` no sirve como vigencia (D12)

`P_DO` es **un único valor para toda la capa**, no por polígono: Las Condes 30/05/1994 (424/424
features), Ñuñoa 27/10/1989 (1718/1718), Providencia 23/01/2007 (270/270).

Es la **publicación original del instrumento**, no la del texto consolidado. Ñuñoa reporta 1989
teniendo un texto refundido de 2025.

Por lo tanto `vigencia.desde` **no puede** derivarse de `P_DO`: hay que reconstruir la historia de
enmiendas desde la propia ordenanza. `P_DO` queda como campo de **procedencia**. La capacidad de
"evaluar contra la norma vigente a la fecha de ingreso de la solicitud" sigue siendo alcanzable,
pero cuesta más de lo que se supuso al diseñar el corpus.

Evidencia completa en `04-DECISIONES.md`.

## 3. Flujo de la iteración 1

```
coordenada (lat, lon)
  → reproyectar EPSG:4326 → EPSG:3857          [pyproj]
  → point-in-polygon contra capas PRC cacheadas [shapely STRtree]
  → código de zona
  → lookup en corpus YAML                       [cargador]
  → Zona
  → motor L1 evalúa cos / cus / altura_maxima / densidad
  → [Veredicto, Veredicto, Veredicto]  (cada uno con cita)
```

## 4. Dependencias permitidas por capa

| Capa | Módulo | Dependencias |
|---|---|---|
| Dominio (L1) | `rasante.dominio` | **solo stdlib** |
| Corpus | `rasante.corpus` | `pyyaml` |
| Geo (L0) | `rasante.geo` | `shapely`, `pyproj`, `httpx` |
| CLI | `rasante.cli` | `typer` |

Solo `httpx` está instalado hoy (T0.2). El resto se agrega en la tarea que lo necesite: así cada
commit queda atómico y sin dependencias ociosas.
