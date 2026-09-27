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
| D13 | **La OGUC aporta reglas; el PRC aporta valores.** Son dos mitades del corpus con naturaleza y frecuencia de cambio distintas | Ver §2.4. La OGUC define *cómo se computa*; los números (`cos 0,6`) los fija cada plan regulador |
| D14 | **El corpus es ejecutable.** Sus reglas no se describen: se interpretan | Ver §2.5. Hoy `DERIVACIONES` en `motor.py` hardcodea lo que `corpus/oguc/*.yaml` describe: dos fuentes de verdad para el mismo cálculo |
| D15 | **El motor verifica factibilidad, no solo parámetros sueltos** | Ver §2.6. Los parámetros están acoplados geométricamente: chequeados por separado, todos pueden dar `C` en un proyecto imposible |
| D19 | **Una capa de clasificación con contrato tipado** (`choice`/`noul`/`score`), con proveedor intercambiable y **portero de confianza** | Ver §2.9. El motor solo sabe comparar números; usos de suelo, agrupamiento y las condiciones que no son aritmética no tienen representación |
| D17 | **La incertidumbre vive en la extracción, no en el veredicto.** El extractor devuelve alternativas y confianza (Choice/Score/Noul); el motor consume solo valores ya resueltos | Ver §2.8. La ambigüedad se resuelve **una vez** al escribir el corpus, no en cada proyecto |
| D18 | **Un dato sin revisar no aprueba.** Sin `revisado_por` no hay `C` ni `NC`, solo `P` | Ver §2.8. Verificado el 2026-09-26: el motor no leía `EstadoRevision`, y `borrador` producía `C` |
| D16 | **El motor selecciona el límite aplicable evaluando hechos del corpus.** Si un hecho es indeterminado, da `P` — **nunca elige el límite más permisivo** | Ver §2.7. El caso real: la OGUC `2.6.5` permite +50 % de `cus` bajo las condiciones 1.a/1.b del `2.6.4`, pero solo +30 % bajo la 1.c |

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

El corpus tiene **tres partes** con ciclos de vida distintos (§2.4).

```
corpus/
  oguc/                     # NACIONAL. Reglas y definiciones. Cambia por decreto
    fuentes.yaml            # URL, hash, fecha de extracción, decreto consolidante
    1.1.2.yaml              # definiciones: constructibilidad, densidad bruta/neta, altura, rasante
    2.1.23.yaml             # altura en pisos -> 3,50 m
    5.1.10.yaml             # cómputo de la superficie del primer piso (COS)
    ...
  ddu/                      # NACIONAL. Circulares MINVU
    514.yaml                # Formato Tipo del informe + leyenda (C)/(NC)/(P)/(NP)/(PR)
  prc/<REGION>/<comuna>/    # MUNICIPAL. Valores. Cambia por enmienda
    fuentes.yaml            # dónde vive la ordenanza, versión, hash
    zonas/<codigo>.yaml     # los valores por zona
```

**Qué se guarda de cada norma.** Número de artículo + cita corta + URL + hash + fecha de extracción,
**no el texto íntegro**. Es citación, no reproducción: reduce el riesgo de titularidad y es mejor
ingeniería. Los PDFs crudos viven en `cache/`, que está en `.gitignore`.

```yaml
# corpus/oguc/2.1.23.yaml
norma_id: oguc
articulo: "2.1.23"
materia: altura de edificación expresada en pisos
cita: >
  Si el instrumento de planificación territorial fija altura de edificación en pisos, sin
  explicitar su medida en metros, ésta se determinará multiplicando 3,50 m por el número de pisos.
regla:
  tipo: conversion
  entrada: pisos
  factor: "3.50"
  unidad: m
procedencia:
  url_fuente: "https://www.minvu.gob.cl/wp-content/uploads/2019/05/OGUC-Mayo-2026-D.S.-N5-D.O.-22-05-2026-rev-15.09.2026.pdf"
  consolidado_por: "D.D. N°5, D.O. 22-05-2026"
  hash_fuente: "sha256:..."
  extraido: 2026-09-26
  extraido_por: "rasante.corpus.ingesta (determinista, sin LLM)"
  revisado_por: null
  estado: borrador          # borrador | revisado | validado
```

La OGUC se trocea **de forma determinista** por el patrón `Artículo X.Y.Z.` — sin LLM. El motor no
adivina dónde empieza un artículo.

## 2.2.1 Esquema de las zonas del PRC

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
    valor: "0.6"            # la ordenanza escribe "0,6": coma decimal, ver T1.6
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

## 2.4 La OGUC aporta reglas, el PRC aporta valores (D13)

Descubierto al inspeccionar el texto consolidado de la OGUC (577 págs, 1.334.802 caracteres). Es la
corrección más importante al diseño original del corpus.

| | OGUC | PRC / ordenanza |
|---|---|---|
| Qué aporta | **Definiciones y procedimiento**: cómo se computa cada parámetro, rasantes, distanciamientos | **Los valores** por zona (`cos 0,6`, `cus 3,6`) |
| Alcance | Nacional | Una comuna |
| Cambia por | Decreto (decenas al año) | Enmienda municipal |
| Consolidador | MINVU publica la versión vigente y **declara el decreto que la consolida** | Nadie lo declara: `P_DO` trae la publicación original (§2.3) |

**Artículos verificados como necesarios** (nótese que los números NO son los que se suponen):

| Artículo | Materia | Para qué |
|---|---|---|
| `1.1.2` | Definiciones: *coeficiente de constructibilidad*, *densidad*, ***densidad bruta***, ***densidad neta***, *altura de edificación*, *rasante* | Resuelve con fuente la ambigüedad bruta/neta de A3 |
| `2.1.23` | Altura en pisos → **3,50 m por piso** | Regla dura y testeable |
| `5.1.10`, `5.1.11` | Cómo se determina la superficie edificada del primer piso | Cómputo del `cos` |

**Números que NO son lo que parecen**, y por eso hay que buscar en el texto en vez de asumir:

- `2.6.2` = **adosamiento** (no densidad)
- `2.6.3` = **distanciamientos y rasantes** (no ocupación de suelo)
- `2.6.4` = **Conjunto Armónico** (no constructibilidad)

**Consecuencia para el motor:** la cita de un veredicto puede referirse a la OGUC (la regla) o al PRC
(el valor). El `Cita.norma_id` ya soporta ambos (`"oguc"` | `"prc:nunoa"`). Un veredicto de densidad
cita **las dos**: la definición de densidad bruta de la OGUC y el valor de la ordenanza.

## 2.5 El corpus es ejecutable (D14)

**El problema.** `motor.py` tiene `DERIVACIONES` hardcodeado, y `corpus/oguc/2.1.22.yaml` describe la
misma conversión como texto. Dos fuentes de verdad para el mismo cálculo, que pueden divergir sin
que ningún test lo note. El corpus es hoy **decorativo**: se cita, no se ejecuta.

**Y el corpus no puede expresar lo que la ordenanza realmente dice.** Evidencia del texto refundido
de Ñuñoa:

```
Coeficiente de ocupación de suelo              0,6
Coeficiente de ocupación de suelo pisos sup.   0,4
Coeficiente de constructibilidad               4
Altura máxima de edificación continua.  17,50 m y 6 pisos
Altura máxima de edificación aislada.   ...
Altura máxima de edificación.           44,00 m y 15 pisos
```

Cuatro cosas que el esquema actual no representa:

| Gap | Evidencia | Consecuencia hoy |
|---|---|---|
| Varios límites **simultáneos** en un parámetro | *"44,00 m **y** 15 pisos"* | El corpus guarda un valor; el motor compara uno |
| El valor depende de una **clasificación** del proyecto | *"continua"* vs *"aislada"* | `Zona` tiene un `Parametro` por clave, con un valor plano |
| **Acoplamiento geométrico** entre parámetros | cos 0,6 + cos_sup 0,4 + cus 4 | Cada parámetro se evalúa aislado (§2.6) |
| **Excepciones condicionales** | OGUC `2.6.5`: Conjunto Armónico excede el cus hasta 50 % | `regla` es un string decorativo |

### Esquema propuesto

```yaml
# corpus/prc/RM/nunoa/zonas/Z-4.yaml
zona: "Z-4"
parametros:
  cus:
    unidad: adimensional
    limites:                       # TODOS ligan: es una conjunción, no una alternativa
      - valor: "4"
        cita: { norma_id: "prc:nunoa", articulo: "..." }
      - valor: "6"                 # excepción condicional
        cuando: { clasificacion: conjunto_armonico }
        cita: { norma_id: "oguc", articulo: "2.6.5" }
  altura_maxima:
    unidad: m
    limites:
      - valor: "44.00"
        unidad: m
        cita: { norma_id: "prc:nunoa", articulo: "..." }
      - valor: "15"
        unidad: pisos
        cita: { norma_id: "prc:nunoa", articulo: "..." }
        # la OGUC dice que el 3,50 m/piso solo aplica si NO se explicitan metros.
        # Ñuñoa sí los explicita, así que este límite lija en pisos, no convertido.

relaciones:                        # restricciones ENTRE parámetros
  - tipo: cota_superior
    objetivo: cus
    expresion: "cos.primer_piso + (numero_pisos - 1) * cos.pisos_superiores"
    fundamento: "se deduce de las definiciones de los coeficientes (OGUC 1.1.2)"
    cita: { norma_id: "oguc", articulo: "1.1.2" }
```

**Cómo se evalúa.** La `expresion` es un mini-DSL evaluado con el módulo `ast` de la stdlib sobre
un **vocabulario cerrado**: solo nombres declarados, operadores aritméticos y comparaciones. Nada de
llamadas, atributos ni acceso a nada. Es un intérprete de ~60 líneas, puro y determinista.

La razón de usar `ast` con lista blanca y no `eval`: un corpus es **dato que llega de fuera**. `eval`
sobre un YAML de la comunidad es ejecución de código arbitrario. Con `ast` y vocabulario cerrado, lo
peor que puede pasar es un error de evaluación, y el árbol sintáctico queda auditable.

## 2.6 Verificación de factibilidad (D15)

Chequear cada parámetro por separado **no alcanza**, porque están acoplados. Aritmética sobre datos
reales de Ñuñoa (`cos=0,6`, `cos_sup=0,4`, `cus=4`, altura 44 m y 15 pisos):

```
cus máximo alcanzable con 15 pisos = 0,6 + 14 × 0,4 = 6,2   → cus=4 es holgado
cus=4 con cos=0,6 exige al menos 7 pisos                    → ≈24,5 m a 3,50 m/piso
15 pisos × 3,50 m = 52,5 m > 44,00 m                        → los dos límites no se
                                                              alcanzan con pisos de 3,50
```

El motor actual diría `C` en **cada** parámetro de un proyecto imposible. Eso no es un problema de
rendimiento: es un informe aprobando algo que no se puede construir.

Se verifican dos cosas **distintas**, y las dos salen citadas:

1. **Consistencia del conjunto normativo.** ¿Existe algún proyecto que satisfaga todos los límites
   de la zona a la vez? Si el `cus` normado excede lo que permiten `cos`/`cos_sup`/`altura`, la
   ordenanza es inalcanzable en ese punto. Puede ser un error del corpus o una particularidad real
   que el revisor debe conocer.
2. **Factibilidad del proyecto declarado.** Las relaciones geométricas se cumplen contra el proyecto
   real: si declara `cus=4` y `cos=0,6`, necesita ≥7 pisos; si su altura no da para eso, el
   proyecto es imposible aunque cada parámetro por separado cumpla.

El hallazgo no es un `Veredicto` de parámetro: es un `Hallazgo` con severidad, cita y los parámetros
involucrados. Ambos terminan en el Formato Tipo, pero por caminos distintos.

## 2.7 Hechos y selección de límites (D16)

**El problema.** `Parametro` guarda **un** `valor`, pero la ordenanza fija **varios límites según cómo
sea el proyecto**. El caso no es hipotético; está en la OGUC:

```
2.6.4  Un proyecto tiene la calidad de Conjunto Armónico cuando cumple ALGUNA de estas
       condiciones:
       1.- Condición de dimensión:
         a) terreno cuya superficie total sea >= 5 veces la superficie predial mínima del PRC
         b) ...
         c) ...

2.6.5  Los proyectos que cumplan la condición a) o b) podrán exceder hasta en un 50% el
       coeficiente de constructibilidad.
       Los que cumplan la condición c) podrán exceder hasta en un 30%.
```

`superficie_predio_m2 >= 5 × superficie_predial_minima` **es una comparación**, no algo que haya que
aprender. Y el desglose importa: entre 50 % y 30 % de `cus` hay 20 puntos, que es justo lo que
convierte un `(NC)` en un `(C)`.

**Por qué no un clasificador entrenado.** Sería descalificante en los cuatro frentes a la vez:

1. **Reproducibilidad.** El mismo expediente debe dar el mismo veredicto siempre.
2. **Trazabilidad.** El revisor tiene que poder escribir *"cumple la condición 1.a) del art. 2.6.4
   porque el predio tiene 6.200 m² y la superficie predial mínima es 1.000 m²"*. *"El sistema
   determinó que es Conjunto Armónico"* no es defendible ante la DOM.
3. **Error asimétrico.** Un clasificador con 95 % de acierto falla en 1 de cada 20 proyectos y el
   revisor **no tiene forma de saber en cuál**. Aquí ese fallo invierte el veredicto.
4. **No hay nada que aprender.** La regla está escrita. Un modelo la aproximaría peor.

Es D3 (*"el LLM nunca decide"*) aplicado a las condiciones.

**El mecanismo: hechos.** Un *hecho* es un predicado nombrado, definido en el corpus con una
expresión del mismo vocabulario cerrado que las derivaciones. La maquinaria de T1.4 ya lo evalúa.

```yaml
# corpus/oguc/2.6.4.yaml
hechos:
  dimension_a_o_b:
    expresion: "superficie_predio_m2 >= 5 * superficie_predial_minima"
    cita: { norma_id: oguc, articulo: "2.6.4" }
  dimension_c:
    expresion: "..."
    cita: { norma_id: oguc, articulo: "2.6.4" }
```

```yaml
# en la zona
cus:
  limites:
    - { valor: "4",   cita: { norma_id: "prc:nunoa", articulo: "Z-4" } }
    - { valor: "6",   cuando: [dimension_a_o_b], cita: { norma_id: oguc, articulo: "2.6.5" } }
    - { valor: "5.2", cuando: [dimension_c],     cita: { norma_id: oguc, articulo: "2.6.5" } }
```

La expresión mezcla una primitiva del proyecto (`superficie_predio_m2`) con un **valor normado**
(`superficie_predial_minima`, que fija el PRC). El validador ya lo admite porque suma los parámetros
declarados por la zona al vocabulario.

**Las dos capas de fallo, y ninguna es silenciosa.**

| Cuándo | Qué falta | Qué pasa |
|---|---|---|
| **Al validar** | Un límite pide `cuando: [x]` y ningún artículo define el hecho `x` | El validador **falla fuerte**: es un defecto del corpus, y silenciarlo haría que ese límite nunca aplique |
| **Al evaluar** | El hecho está definido pero al proyecto le falta un dato para evaluarlo | **`P` + `Hallazgo` de clasificación indeterminada**, diciendo qué falta |

Lo segundo es el mismo principio que ya gobierna el motor: **lo que no se puede verificar no se
afirma**. Y acá es crítico, porque el fallback permisivo —aplicar el +50 %— aprobaría proyectos que
no califican.

**Cambio de modelo.** `Parametro` pasa de `valor: Decimal | None` a `limites: tuple[Limite, ...]`, y
aparece `Limite` con `valor`, `unidad`, `cita` y `cuando`. Varios límites aplicables **ligan todos**:
manda el más restrictivo.

**Dónde sí entra el aprendizaje.** Extrayendo datos de PDFs y planos (iteración 2), y redactando la
propuesta de regla que un humano valida por PR. **El modelo propone; el humano firma.** Nunca en la
ruta del veredicto.

## 2.8 Incertidumbre: en la extracción, no en el veredicto (D17, D18)

**El agujero que se verificó.** El motor **no leía** `Procedencia.estado`. Una zona en `borrador`,
con `revisado_por=None`, producía los mismos `(C)` que una validada:

```
corpus en estado borrador   -> C   (revisado_por=None)
corpus en estado revisado   -> C   (revisado_por=None)
```

Es la misma clase de fallo que el proyecto viene cerrando: **aprobación silenciosa desde entrada no
confiable**. Un dato que nadie firmó no puede convertirse en un `(C)` — ni en un `(NC)`, que
rechazaría un proyecto que quizá cumple. De ahí **D18**: sin firma, todo sale `P` y un `Hallazgo`
que dice por qué.

**Dónde SÍ hay incertidumbre de verdad: la extracción.** No la evaluación. Sobre un PDF escaneado
—la DDU 514 extrae `"SAANTIAGo, 10 ENE 2029"`— la duda es real, y ahí las tres primitivas encajan:

| Primitiva | Dónde vive |
|---|---|
| **Choice** | "¿cuál de estos 8 artículos define constructibilidad?" |
| **Score** | "¿qué tan legible es esta página?" — triaje antes de extraer |
| **Noul** | "¿este fragmento contiene un coeficiente de ocupación de suelo?" (probabilidad 0–1) |

**D17: eso es un contrato de la capa de extracción, no del motor.** Cada dato extraído llega con sus
alternativas y su confianza, y **solo cruza al motor cuando un humano lo resolvió a un valor
único**. La confianza decide **si un dato está listo**, no *cuánto cumple*. Un umbral bajo lo deja en
`borrador`; una firma lo pasa a `revisado`.

**Por qué el veredicto no puede ser probabilístico.**

1. **Es un acto, no una estimación.** `(C)` afirma que el proyecto cumple la norma, bajo
   responsabilidad civil y penal. Una probabilidad no se firma.
2. **El Formato Tipo no tiene casillero.** La DDU 514 define `(C)/(NC)/(P)/(NP)/(PR)`. No existe
   "confianza 0,62"; inventarlo rompe la correspondencia con el formulario oficial.
3. **Lo binario obliga a decidir.** Un `0,94` se archiva sin mirar; un `P` fuerza a resolver el dato.
4. **La ambigüedad se resuelve una vez, no en cada proyecto.** Si un artículo es ambiguo, un humano
   lo lee, decide y **escribe la regla** — versionada, citada y revisada, aplicándose igual a todos
   los proyectos futuros. Un evaluador probabilístico volvería a adivinar en cada evaluación: la
   misma norma daría 0,70 en enero y 0,65 en junio **sobre el mismo expediente**. Eso no es rigor,
   es ruido con decimales.

**Ninguno de los fallos reales fue de interpretación.** El registro de esta iteración: el troceador
fusionaba `2.1.3` con `2.1.3 bis` (regex mal escrita), `densidad.bruta.bruta` (clave compuesta
pasada como `id`), *"ligan todos"* rompía el `2.6.5` (spec mal escrita, con la norma **inequívoca**
delante), tres citas parafraseadas (transcripción). Todos deterministas, todos cazados por
verificaciones deterministas. Un evaluador probabilístico no habría cazado **ninguno**, y habría
hecho los cuatro más difíciles de cazar.

## 2.9 Capa de clasificación (D19)

**El hueco que cierra.** El motor determinista solo sabe comparar números. Quedaron fuera, escritos
en nuestro propio corpus:

- **Usos de suelo.** `UPERM`/`UPROH` son texto libre sucio (`"culto, culto"`, fragmentos truncados).
  Responder "¿este uso está permitido en la zona?" es una **`choice`**, y hoy no se puede.
- **`dimension_b`** ("constituya en sí una manzana existente") y **`dimension_c`** ("fusión predial
  del art. 63"), parkeadas en `hechos_pendientes` de `2.6.4.yaml`. No son aritmética sobre números
  del proyecto: son juicios sobre texto (escrituras, CIP). Eso es un **`noul`**.
- **Triaje de legibilidad** de una página escaneada, antes de extraer: un **`score`**.

**Por qué JEV encaja.** TypeSafe lo describe como un modelo *System One*: juicios rápidos, una
pasada, respuestas tipadas con probabilidad en vez de prosa. Y su guía de uso recomienda exactamente
nuestra arquitectura: *"route with Jev, **compute in code**, write with an LLM"*, *"exact data never
goes through a model"*. Añade que **no es confiable en aritmética, conteo ni comparación de fechas**
— que es justo lo que hace nuestro motor.

| | |
|---|---|
| Forma | Un **estado** (bloques de texto con nombre) + N preguntas tipadas, en **una pasada** |
| Salida | `choice`: opción + confianza + reparto · `noul`: probabilidad · `score`: nivel + confianza |
| Límites | **Solo texto**: no lee PDFs ni imágenes. Pierde precisión con detalle irrelevante |
| Coste | $0,042/M entrada, salida gratis · ~194 ms mediana |

**El portero es lo que importa.** Una respuesta por debajo del umbral **no se resuelve**: queda
marcada para revisión humana. Nunca se redondea una duda hacia el lado permisivo — un `noul` de 0,5
no es ni sí ni no, y una elección con 0,54 no se resuelve a la opción más probable. Es **D18 aguas
arriba**: la confianza decide **si un dato está listo**, no cuánto cumple.

**El contrato no depende de JEV.** `Proveedor` es un protocolo: JEV, DeepSeek, un modelo local o un
proveedor guionizado para tests. `rasante.clasificacion` vive **fuera de `rasante.dominio`** porque
habla por red, y el dominio no (D2).

**Lo que NO hace.** No calcula cumplimiento. No decide. No opina sobre geometría. Clasifica, y el
motor calcula.

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
