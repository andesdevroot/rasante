# Rasante — Copiloto open source para revisores de permisos de edificación

> **Working title:** `rasante` (la rasante es el plano imaginario de la OGUC que ningún punto del edificio puede atravesar — nombre de dominio, corto, y señal de fluidez técnica ante un arquitecto chileno).
> Alternativas: `predio`, `cip`, `ordanza`, `ddu514`.

**Documento de estudio — versión 0.2 — 2026-09-26**

---

## 1. Tesis

La Ley 21.826 (publicada el 24 de junio de 2026) reformó la LGUC y creó algo que antes no existía: una **revisión formal de admisibilidad en 5 días hábiles**. Si la DOM no la declara inadmisible en plazo, *la solicitud se entiende acogida a trámite*. Y con **informe favorable de revisor independiente**, el plazo de la DOM baja de 25 a 15 días hábiles.

Eso convirtió el informe del revisor independiente en un **ticket de vía rápida**. Se creó un mercado privado de revisiones, con un formato de salida **definido por el Ministerio** (Circular DDU 514) y una obligación legal explícita en el **art. 116 bis de la LGUC**, introducido por la Ley 21.718: el revisor debe *explicar la forma* en que el proyecto da cumplimiento a las normas urbanísticas.

Nadie tiene herramienta para producir eso. Los code-checkers BIM existentes (Solibri, Verifi3D) validan contra códigos extranjeros — ICC, IFC genérico — no contra OGUC + plan regulador comunal.

**Rasante es el copiloto que hace esa pega.** No es un chatbot legal: es un motor de reglas determinista que computa las normas urbanísticas, más un LLM que redacta la justificación exigida por ley con cita al artículo, y que emite el Formato Tipo oficial.

---

## 2. Hallazgos de la investigación previa (todo verificado)

### 2.1 Los planes reguladores comunales son datos abiertos consultables

El hallazgo que cambia el proyecto: **MINVU expone los PRC de todas las regiones como servicios ArcGIS REST**.

```
https://geoide.minvu.cl/server/rest/services/IPT?f=json
  → IPT/PRC_Araucania, PRC_RM_Norte, PRC_RM_Sur, PRC_Valparaiso,
    PRC_Biobio, PRC_Maule, PRC_Coquimbo, PRC_Los_Lagos, ... (todas las regiones)
```

Cada uno es `FeatureServer` + `MapServer`, con `capabilities: "Query,Map,Data"` y `supportedQueryFormats: "JSON, geoJSON, PBF"` — es decir, **consultable y descargable en GeoJSON**.

Ejemplo real (`IPT/PRC_RM_Norte`), capas por comuna:

| id | capa |
|----|------|
| 11 | PRC_Las_Condes |
| 17 | PRC_Ñuñoa |
| 7 | PRC_Estacion_Central |
| 8 | PRC_Huechuraba |
| 5 | PRC_Conchalí |
| 13 | PRC_Lo_Barnechea |
| 0,1 | PRC_Colina (+ áreas de riesgo, zonas de restricción) |

Campos reales de la capa de Las Condes:

```
REG, COM, ZONA, NOM, UPERM, UPROH, P_DO, N_DOC, T_DO, LOC, OBS
```

Muestra real de unafeature:

```
ZONA  : UEe3/Ee3
NOM   : UEe3/Ee3 Zona Especial 3 Área de Parques
UPERM : Equipamiento de esparcimiento.
UPROH : Residencial; equipamiento de comercio, culto, culto, deporte, educación, ...
P_DO  : 30/05/1994
```

### 2.2 Lo que **sí** y lo que **no** viene en los datos

Esto define toda la arquitectura:

| Dato | ¿Disponible? | Fuente |
|---|---|---|
| Geometría del predio → zona | ✅ GeoJSON | ArcGIS REST MINVU |
| Código de zona (`UEe3/Ee3`) | ✅ | atributo `ZONA` |
| Usos permitidos / prohibidos | ✅ (texto libre, sucio) | `UPERM` / `UPROH` |
| **Fecha de publicación en DO** | ✅ | `P_DO` ← **versionado normativo gratis** |
| **Constructibilidad, ocupación de suelo, rasante, altura, densidad, estacionamientos, distanciamientos** | ❌ **NO** | ordenanza / CIP |

**Conclusión:** la capa base la da el Estado gratis; los **parámetros numéricos hay que extraerlos de la ordenanza**. Ese es exactamente el trabajo que nadie ha hecho y que constituye el foso del proyecto.

### 2.3 El formato de salida ya está especificado por el Ministerio

**Circular DDU 514** (10 de enero de 2025) publica el *Formato Tipo de Informe del Revisor Independiente*.

Leyenda de veredictos **oficial** (usar estos códigos literalmente):

```
(C)  = Cumple con exigencias normativas
(P)  = Pendiente
(NC) = No cumple con exigencia normativa
(NP) = No procede
(PR) = Plan Regulador
```

Estructura del formato:

```
I.   IDENTIFICACIÓN DE PROPIETARIO Y PROFESIONALES
II.  INFORMACIÓN DEL PREDIO          (basta el CIP + Zona del IPT)
III. INFORMACIÓN DEL PROYECTO
IV.  NORMAS A LAS QUE SE ACOGE EL PROYECTO
     IV.1  Disposiciones especiales o excepcionales
     IV.2  Otras disposiciones
     IV.3  Conjunto viviendas económicas (6.1.8 OGUC)
V.   DESCRIPCIÓN DEL PROYECTO
C.   CUMPLIMIENTO DE LAS NORMAS URBANÍSTICAS        ← art. 116 bis LGUC (Ley 21.718)
D.   CUMPLIMIENTO DE OTRAS NORMAS ASOCIADAS
E.   CUMPLIMIENTO CAPÍTULOS 1, 2 y 3, TÍTULO 4 OGUC
F.   CUMPLIMIENTO CAPÍTULOS 4 AL 14, TÍTULO 4 OGUC
G.   DECLARACIÓN DE INSTALACIONES Y PAVIMENTACIÓN DE CALZADAS INTERIORES
```

Hay variantes por tipo de permiso (S.A.A. ON, R.A.A. ON, S.A.L. 3.1.4, R.A.L. 3.1.4), más los **Formularios Únicos Nacionales (FUN)** como entrada estructurada.

Formularios: <https://www.minvu.gob.cl/elementos-tecnicos/formularios/grupo-15-formato-tipo-de-informes-revisor-independiente/>

### 2.4 El dolor está documentado por los propios revisores

Citas textuales del proceso de consulta pública del formato (MINVU, 31 págs). Son requisitos de producto gratuitos:

> *"Me parece extraño que el informe del revisor independiente sea 3 o 4 veces más extenso que los formularios municipales."*

> *"Es ineficiente repetir antecedentes que se detallan en los formularios de solicitud."*

> *"Resulta poco eficiente explicar la inaplicabilidad de una norma, en tanto induce a subjetividades que no contribuyen a la claridad del Informe."*

> *"O hay síntesis, como ocurre en un check-list, o bien nos extendemos en verificaciones y explicaciones, que no caben en un casillero."*

**La tensión central del producto:** el revisor necesita *simultáneamente* el checklist terso **y** la justificación trazable completa. Un humano no puede producir ambos sin duplicar trabajo. Un programa **sí**: son dos renderizaciones del mismo árbol de decisión. Ahí está el valor.

### 2.5 Economía de inferencia (DeepSeek, verificado)

| | deepseek-flash (V4.1) | deepseek-v4-pro |
|---|---|---|
| Contexto | 1M | 1M |
| Max output | 384K | 384K |
| Input cache **miss** off-peak | $0.15 / M | $0.66 / M |
| Input cache **hit** | **$0.003 / M** | $0.022 / M |
| Output off-peak | $0.60 / M | $1.98 / M |
| **Visión** | ✅ | ❌ |
| Concurrencia | 2500 | 500 |

Dos consecuencias de diseño:

1. **El prefijo normativo va cacheado.** OGUC + ordenanza + instrucciones = corpus estable → **$0.003/M = 50× más barato**. Incluir los capítulos completos de la OGUC en cada llamada cuesta casi nada. Esto es lo que permite citar con precisión en vez de resumir de memoria.
2. **El horario hábil chileno es 100% off-peak.** Peak = 01:00–04:00 y 06:00–10:00 UTC. Chile opera 12:00–22:00 UTC → **siempre mitad de precio**. Los jobs batch nocturnos también.

**Costo por informe:** expediente ~150 págs ≈ 120k tokens input (miss) + 10k output ≈ **$0.024 USD**. Con cache hit en el corpus, menos. El informe completo cuesta **menos de 3 centavos de dólar**.

---

## 3. Principio de arquitectura: el LLM no decide

Regla dura, no negociable:

> **El LLM redacta y extrae. Nunca calcula ni dictamina.**

Un veredicto `(NC)` es un acto profesional firmado bajo responsabilidad civil y penal. No puede ser una muestra de un modelo. Además, hacer que el modelo decida es caro, lento, no reproducible y alucina citas — fatal aquí.

Tres capas:

```
┌─ L0 · FUENTE AUTORITATIVA (determinista) ─────────────────────────┐
│  ArcGIS REST MINVU (zona + usos + P_DO)                           │
│  CIP del predio (norma aplicable autoritativa)                    │
│  Formularios Únicos Nacionales (entrada estructurada)             │
│  Corpus OGUC/LGUC versionado                                      │
└───────────────────────────┬──────────────────────────────────────┘
                            ▼
┌─ CLASIFICACIÓN · choice/noul/score + portero (JEV) ───────────────┐
│  lo que el motor no puede decidir: usos, condiciones de texto     │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─ L1 · MOTOR DE REGLAS (determinista, auditable, testeable) ───────┐
│  Cálculo: ocupación de suelo, constructibilidad, altura,          │
│  rasantes, densidad, estacionamientos, distanciamientos,          │
│  aguas lluvias, accesibilidad, admisibilidad documental           │
│  Salida: veredicto (C|NC|P|NP|PR) + traza + valores + cita        │
│  Python puro · decimal stdlib · tests por artículo                │
└───────────────────────────┬──────────────────────────────────────┘
                            ▼
┌─ L2 · LLM (extracción de PDFs y redacción) ───────────────────────┐
│  (a) compila prosa de ordenanza → reglas L1   [revisión humana]   │
│  (b) extrae datos de PDFs escaneados y planos [visión]            │
│  (c) redacta "la forma en que da cumplimiento" (116 bis LGUC)     │
│  (d) responde consultas con cita verificable                      │
│  NUNCA: aritmética, veredictos, ni números inventados             │
└──────────────────────────────────────────────────────────────────┘
```

La **capa de clasificación** y L2 usan modelos, pero para cosas distintas: la primera responde
preguntas **tipadas** sobre texto (¿qué uso es este? ¿es una fusión predial?) y devuelve
probabilidades; el segundo extrae de PDFs —que JEV no puede leer— y redacta el informe.

**Corolario crítico:** el **núcleo** —corpus + motor— funciona **con cero modelos**. Entrega los
cálculos, la factibilidad y el checklist de admisibilidad sin red, sin costo y sin sacar un dato del
país. Es lo que da adopción sin fricción.

La capa de clasificación es **aditiva**: sin ella, las preguntas que solo ella sabe responder quedan
en `P` —nunca en un veredicto inventado—. Y eso vale para los dos: una capa de clasificación caída
degrada a `P`, no a una respuesta plausible.

### Cómo se evita la alucinación de citas

El LLM no produce texto libre con citas. Produce **JSON con referencias a IDs de regla** del corpus (`oguc:2.6.2`, `prc:las-condes:UEe3:constructibilidad`). El renderizador resuelve el ID al texto del artículo desde el corpus versionado. Si el ID no existe, **la generación falla** — no hay forma de inventar una cita.

---

## 4. El corpus normativo como repositorio Git

Este es el foso **y** el mecanismo de tracción. La normativa como código, revisada por pares.

```
normativa/
  oguc/
    DS47/
      articulos/
        2.6.2.yaml            # densidad
        2.6.3.yaml            # coeficiente de ocupación de suelo
        3.1.3.yaml
        5.1.15.yaml
      meta.yaml               # versión, decretos modificatorios, hash
  prc/
    RM/
      las-condes/
        ordenanza.md
        fuentes.yaml
        zonas/
          UEe3.yaml
          Ee3.yaml
        areas-de-riesgo/
  fun/
    formularios.json          # esquema de Formularios Únicos Nacionales
```

Una zona:

```yaml
# corpus/prc/RM/las-condes/zonas/UEe3.yaml
zona: UEe3/Ee3
nombre: "Zona Especial 3 Área de Parques"

usos:
  permitidos: [equipamiento_de_esparcimiento]
  prohibidos:
    - residencial
    - equipamiento_de_comercio
    - equipamiento_de_culto
    # ... normalizado desde UPERM/UPROH

parametros:
  coeficiente_ocupacion_suelo:
    valor: null
    estado: no_aplica
  coeficiente_constructibilidad:
    valor: null
    estado: no_aplica
  altura_maxima:
    valor: null
    estado: no_aplica
  # Zona de parques: la ordenanza no fija parámetros de edificación.

admisibilidad:
  antecedentes_requeridos: [CIP, plano_emplazamiento, ...]

vigencia:
  desde: 1994-05-30           # desde P_DO
  hasta: null

procedencia:
  instrumento: "PRC Las Condes"
  documento: "Decreto alcaldicio ..."
  publicado_do: 1994-05-30
  url_fuente: "https://geoide.minvu.cl/server/rest/services/IPT/PRC_RM_Norte/MapServer/11"
  hash_fuente: "sha256:..."
  extraido_por: "llm:deepseek-flash"
  revisado_por: null           # ← nombre del revisor humano
  estado: borrador             # borrador | revisado | validado
```

**Por qué esto funciona como foso y como flywheel:**

- Cada oficina de arquitectura arregla **su** comuna y contribuye el YAML vía PR. Costo marginal para ellos: bajo. Valor agregado al común: alto.
- `estado: borrador → revisado → validado` con nombre del revisor humano. La validación es el activo escaso.
- El `hash_fuente` detecta si la ordenanza cambió aguas arriba.
- **`vigencia.desde/hasta` permite evaluar contra la norma vigente a la fecha de ingreso de la solicitud.** Ninguna herramienta comercial hace esto y evita una clase entera de informes erróneos.

**El PR de una comuna nueva es la unidad de contribución.** Ahí está la tracción open source.

---

## 5. Stack

> **Nota de revisión (v0.2).** La versión anterior de esta sección recomendaba **Rust**. Se corrige a **Python**.
> El error fue inferir las prioridades desde el requisito "binarios que instalen y arranquen rápido" y
> subponderar el dato explícito del perfil: 20 años de C/Java/**Python**. En un proyecto unipersonal la
> velocidad de iteración domina, y el trabajo real de este proyecto es **GIS + NLP + orquestación de LLM**,
> que es territorio Python. Lo que se pierde es acotado y cuantificado más abajo.

### 5.1 Decisión central: **Python** para el core

| Dimensión | Python | Rust |
|---|---|---|
| Tu curva de aprendizaje | **~0** | semanas (borrow checker, lifetimes, async) |
| Geometría / GIS | **`shapely`**, ecosistema dominante (y `pyproj` si hiciera falta) | `geo` + `proj4rs`, más delgado |
| Extracción de PDF | **`pypdf`, `pdfminer.six`**, los mejores del rubro | `pdfium-render`, binding a la misma lib C++ |
| Ecosistema LLM | **el de referencia** | SDKs comunitarios |
| Aritmética decimal | **`decimal` en stdlib**, precisión arbitraria | `rust_decimal` (128 bits) |
| Arranque | ~150–400 ms con imports perezosos | ~50 ms |
| Tamaño distribuible | ~80–120 MB | ~15 MB |
| Instaladores | Nuitka / Briefcase (1–2 semanas de pega) | `cargo-dist` (automático) |
| Demo WASM sin instalar | Pyodide, ~10 MB, init lento | **compilación nativa, ideal** |

**Veredicto:** las dos últimas filas son las únicas que favorecen a Rust, y ninguna es bloqueante:

- **Arranque:** 400 ms en una app de escritorio que abre un navegador es **invisible**. El requisito original se cumple.
- **Tamaño:** 100 MB es normal en 2026 (VS Code son ~350 MB). Solo molesta en internet malo — considera un instalador con el corpus descargado aparte, bajo demanda.
- **WASM:** es la pérdida real. Se reemplaza por una **demo pública servida desde un FastAPI pequeño** (ver §5.2 punto 8). Cuesta unos dólares al mes y a cambio controlas qué versión del corpus expones.

### 5.2 Mitigaciones concretas (no son opcionales)

1. **`uv` para todo.** Instalación reproducible y rápida: `uv tool install rasante`. Fija la versión de Python y resuelve dependencias en segundos. Es lo que hace que "instalar y arrancar rápido" sea cierto del lado del usuario.
2. **Evitar el stack geoespacial pesado.** Usa **`shapely`** (wheel con la librería nativa incluida), **no** `geopandas`/`fiona`/`rasterio`/GDAL. Para leer GeoJSON no necesitas GDAL: `shapely.geometry.shape()`. Esto baja el bundle de ~300 MB. **`pyproj` se descartó en T1.11**: el servicio de MINVU ya devuelve EPSG:4326 y el punto de consulta llega en el mismo CRS.
3. **`polars`, no `pandas`.** Import más liviano, mucho más rápido, backend en Rust.
4. **Imports perezosos, medidos.** `python -X importtime` en CI. `shapely` se importa solo al hacer geometría, no al arrancar. Es la diferencia entre 700 ms y 200 ms.
5. **Nuitka, no PyInstaller.** Compila a C, arranque bastante mejor y menos falsos positivos de antivirus.
6. **UI como estáticos.** Build de SvelteKit servido por el proceso local. Sin cambios respecto al plan original.
7. **`sqlite3` de stdlib** (o `apsw` si necesitas más control). Cero instalación de DB.
8. **La demo pública es un FastAPI chico**, no WASM. Rate-limited, con la comuna piloto y el corpus embebido.

### 5.3 Lo que importa más que el lenguaje: aislar el motor

Esta es la decisión arquitectónica que de verdad protege el proyecto, y es independiente de si eliges Python o Rust.

**L1 (el motor de reglas) debe ser un módulo puro:**

- Entrada y salida **JSON**, sin I/O, sin red, sin base de datos.
- Dependencias permitidas: **solo stdlib** (`decimal`, `dataclasses`, `enum`). Ni pandas, ni polars, ni shapely.
- Sin efectos secundarios. Función pura: `evaluar(expediente, corpus, fecha) -> [veredicto]`.
- Tamaño estimado: 2.000–3.000 líneas.

Por qué: **si algún día necesitas el binario Rust o el demo WASM, portas solo ese módulo** — dos o tres mil líneas de lógica pura y bien testeada, no una maraña de dataframes. Es el único código cuya reescritura es viable.

Y al revés: si dejas que los `DataFrame` de pandas se filtren al motor, quedas **encerrado en Python** y en pandas, sin salida barata. La frontera importa más que el lenguaje.

### 5.4 Tabla de stack (Python)

| Capa | Elección | Nota |
|---|---|---|
| Core / motor de reglas | **Python 3.13 · módulo puro, solo stdlib** | ver §5.3 — sin excepciones |
| Aritmética | `decimal` (stdlib) | nunca `float` en normativa |
| Geometría | `shapely` | point-in-polygon: predio → zona |
| Proyecciones | ~~`pyproj`~~ | **Descartado en T1.11.** Este documento afirmaba que ArcGIS da EPSG:3857: **es falso**, da EPSG:4326, y el punto de consulta llega en el mismo CRS. Si alguna capa llegara proyectada, se reproyecta en la ingesta |
| JSON rápido | `orjson` | lectura de GeoJSON |
| Persistencia | `sqlite3` (stdlib) | cero instalación de DB |
| HTTP local | **FastAPI** + `uvicorn` | API local |
| UI | **SvelteKit** → build estático servido por el proceso | se abre en `127.0.0.1:PORT` |
| Instalador de escritorio | **Nuitka** + **Briefcase** (o `uv tool install`) | `.dmg`, `.msi`, `.deb` |
| PDF digital | **`pypdf`** (BSD-3) o `pdfminer.six` (MIT) | **evitar PyMuPDF** — ver §5.5 |
| PDF escaneado / planos | **DeepSeek vision** (`deepseek-flash`) | v4-pro **no** tiene visión |
| DXF (fase posterior) | `ezdxf` | cuadro de superficies vectorial |
| IFC (fase posterior) | IfcOpenShell | diferir hasta que exista demanda |
| LLM | `deepseek-flash` vía API OpenAI-compatible | BYO-key |
| LLM alternativo / offline | Ollama / vLLM con pesos abiertos | endpoint OpenAI-compatible = agnóstico |
| Salida DOCX | `python-docx` | el revisor debe poder editar y firmar |
| Salida PDF | `typst` (binario) o WeasyPrint | plantilla del Formato Tipo |
| Testing | `pytest` + `syrupy` (snapshots) | un test por artículo de la OGUC |
| Empaquetado | `uv` + `pyproject.toml` | lockfile reproducible |
| CI/CD | GitHub Actions + `uv` + Nuitka | releases multiplataforma |
| Demo pública | FastAPI chico, rate-limited | reemplaza al demo WASM |

### 5.5 Licencias: cuidado con PyMuPDF

**PyMuPDF es AGPL-3.0** (doble licencia con opción comercial de Artifex). Si lo usas en un proyecto Apache-2.0, la AGPL te contamina — y su carácter "affero" alcanza también a un servicio en red, lo que mataría una futura versión hosted.

**Usa `pypdf` (BSD-3) o `pdfminer.six` (MIT).** Son algo más lentos y menos tolerantes a PDFs malformados, pero la licencia es limpia. Si más adelante el rendimiento lo exige, se aísla tras una interfaz y se resuelve con el binario `pdftotext` (Poppler, GPL pero ejecutado como proceso separado) o licenciando PyMuPDF.

Verificar lo mismo para `ezdxf` (MIT) e IfcOpenShell (LGPL) antes de integrarlos.

### 5.6 Por qué **no** hacer fine-tuning

"Entrenar el agente con la OGUC y los planes reguladores" es la intuición correcta pero la implementación equivocada. Fine-tuning aquí es un error por cuatro razones:

1. **Queda obsoleto.** Los PRC se enmiendan, la OGUC se modifica por decreto. Un modelo fine-tuneado congela la norma en el checkpoint. El corpus en Git se actualiza con un PR.
2. **No es auditable.** No puedes señalar *qué artículo* sustenta un veredicto si el conocimiento está difuso en pesos.
3. **Alucina citas.** Un modelo fine-tuneado genera referencias plausibles y falsas. En un informe firmado bajo responsabilidad penal, eso es terminal.
4. **Es innecesario.** 1M de contexto + cache hit a $0.003/M pone la OGUC completa literalmente delante del modelo en cada llamada, más barato que mantener un modelo entrenado.

**Lo correcto:** RAG sobre el corpus versionado + citas por ID de regla + motor determinista. Fine-tuning solo si acaso para el **estilo de redacción** del informe, y eso es cosmético, con datos sintéticos derivados y versionados.

### 5.7 Modo sin costo para el proyecto

Modelo **BYO-key**: el ejecutable no tiene backend. Cada revisor usa su propia API key. El proyecto no paga inferencia, el usuario paga centavos al mes. Eso es lo que hace sostenible "gratis y open source" sin servidores.

Y para quien no puede sacar datos del país: **modo 100% offline** con pesos abiertos vía Ollama. El core habla cualquier endpoint OpenAI-compatible, así que es un cambio de URL.

---

## 6. Plan de desarrollo

Comuna piloto: **una sola, hecha exhaustivamente**. Recomiendo **Ñuñoa** (volumen alto, PRC reciente, ordenanza legible) o **Providencia**. No diez comunas a medias.

| Fase | Semanas | Entregable | Criterio de aceptación |
|---|---|---|---|
| **0. Cimientos** | 2 | Esquema YAML del corpus. Ingestor ArcGIS REST → GeoJSON → SQLite. CLI `rasante zona --cip CIP.pdf` | Dado un rol de predio en Ñuñoa, devuelve la zona correcta con cita a `P_DO` |
| **1. Motor de reglas** | 3 | DSL de reglas OGUC + cálculo de los 8 parámetros urbanísticos. Comuna piloto completa | 100% de tests verdes por artículo; validado contra 10 CIP reales |
| **2. Informe** | 3 | Ingesta de expediente (CIP, FUN, cuadro de superficies). Extracción con visión. Emisión del Formato Tipo DOCX/PDF con veredictos `(C)/(NC)/(P)/(NP)/(PR)` | Informe generado == estructura DDU 514, cada veredicto con traza y cita |
| **3. Admisibilidad** | 2 | Checklist de admisibilidad Ley 21.826 (5 días hábiles) por tipo de permiso | Detecta los 20 motivos de inadmisibilidad más comunes |
| **4. Distribución** | 3 | UI web local servida por FastAPI. Instaladores vía Nuitka + Briefcase. **Demo pública sin instalación** | `uv tool install rasante` funciona; demo web carga en <2 s |
| **5. Comunidad** | continuo | Plantilla de PR para comunas. 2ª y 3ª comuna por contribución externa. Publicación del benchmark | Al menos una comuna aportada por alguien externo al proyecto |

**~13 semanas a un v1.0 defendible.** Las fases 0–3 son donde está el valor real; la 4 es la que da tracción.

### 6.1 La demo pública es la pieza de tracción más importante

Una página donde un arquitecto **pega el rol del predio y sube su CIP** y obtiene el checklist sin instalar nada ni crear cuenta. Cero fricción. Ese es el motor de adopción, y el funnel natural hacia la aplicación de escritorio.

En Rust esto salía gratis compilando el motor a WASM. **En Python se sirve desde un FastAPI pequeño** con una o dos comunas embebidas. Cuesta unos dólares al mes y tiene dos ventajas sobre WASM: controlas qué versión del corpus expones, y puedes medir qué consultan realmente (el mejor insumo para priorizar la siguiente comuna).

Consecuencia para §5.3: la demo refuerza por qué el motor debe ser un módulo puro sin dependencias — es exactamente el código que se reutiliza tal cual entre el ejecutable y el servicio.

### 6.2 Metodología de validación (esto es lo que da credibilidad)

Tomar **N expedientes de permisos ya aprobados** de la comuna piloto (públicos vía Ley de Transparencia / portal DOM). Correr la herramienta. Comparar:

- veredictos del motor vs. resolución real de la DOM
- **¿cuántas de las observaciones que hizo la DOM habría predicho la herramienta?**

Publicar precisión y recall. Ese benchmark es el activo de credibilidad — y el anzuelo para el interés académico (escuelas de arquitectura, CIT, MINVU). Nadie más puede publicar eso.

---

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| **Responsabilidad civil/penal** | El revisor firma. La salida es una *propuesta* que requiere aprobación explícita veredicto por veredicto. Licencia + disclaimer + traza completa de qué regla se aplicó y con qué datos |
| **Deriva normativa** (una regla obsoleta es peor que ninguna) | `vigencia.desde/hasta`, `hash_fuente`, badge de "última verificación" en la UI, CI que alerta entradas obsoletas |
| **Calidad de `UPERM`/`UPROH`** | Es texto libre sucio (vi literalmente `"culto, culto"` duplicado). Requiere taxonomía canónica de usos + normalización. Eso es en sí mismo una contribución valiosa |
| **Inercia del sector** | La salida es el formato que **ya usan**, no un sistema nuevo que aprender. Funciona offline. Demo sin instalación |
| **Titularidad de la normativa** | OGUC/LGUC son textos oficiales del Estado. **No pude verificar con certeza el artículo exacto de la Ley 17.336 que los excluye de protección**, así que trátalo como verificación legal pendiente. Mitigación de diseño: almacenar **parámetros extraídos + citas + hash**, no republicar íntegros los documentos municipales. Es a la vez más seguro y mejor ingeniería |
| **El proyecto se estanca por falta de mantención** | Ver §8 |

---

## 8. Sostenibilidad (open source gratis necesita una historia)

**Gratis para siempre:** motor, corpus, CLI, app de escritorio, demo web público.

Lo que se cobra — y es honesto decirlo desde el día uno:

1. **Mantención de reglas certificada.** El producto real no es el software, es que las ordenanzas cambian. Un *rule pack* con SLA ("actualizado dentro de X días de publicada una enmienda en el DO") es lo que una oficina paga. El software es gratis; la vigencia garantizada es el servicio.
2. **Hosted multiusuario para DOM municipales** — SSO, log de auditoría, gestión de expedientes.
3. **Capacitación y certificación** de revisores.
4. **Financiamiento público:** CORFO, FONDEF, ANID. El ángulo "infraestructura pública digital" y "bien público" calza perfecto, y el respaldo de MINVU/CChC/Colegio de Arquitectos es la puerta.

**No poner el corpus tras un paywall.** Es el bien público que genera la adopción; monetizar la vigencia, no el acceso.

---

## 9. Canales de adopción

| Canal | Por qué |
|---|---|
| Asociación de Revisores Independientes | Son el usuario primario y tienen el dolor documentado |
| Colegio de Arquitectos | Distribución y legitimidad |
| CChC (Cámara Chilena de la Construcción) | Adopción desde las oficinas grandes |
| Red de DOM municipales | Municípios chicos sin capacidad técnica |
| Escuelas de arquitectura | Tesis, prácticas, contribución al corpus |
| Publicación del benchmark | Prensa técnica + interés de MINVU |

---

## 10. Próximos pasos concretos

1. **Verificar el estado de titularidad** de OGUC/LGUC/ordenanzas (Ley 17.336) antes de definir licencia del corpus. Licencia sugerida: código `Apache-2.0`, corpus `CC-BY-4.0` con atribución a la fuente municipal.
2. **Bajar los PRC de las 3 comunas candidatas** vía ArcGIS REST y evaluar la calidad real de `UPERM`/`UPROH`.
3. **Conseguir 5–10 expedientes reales** de la comuna piloto (Ley de Transparencia) — son el set de validación y el requisito para la fase 1.
4. **Elegir comuna piloto** y hacer su ordenanza completa a mano, sin LLM. El trabajo manual primero define el esquema correcto del YAML; automatizar antes de entender el esquema produce un esquema equivocado.
5. **Prototipo de 1 semana:** CLI que dado un CIP devuelve la zona desde ArcGIS + las reglas del corpus. Es la prueba de que la columna vertebral funciona.

---

## Anexo A — Endpoints verificados

```
# Catálogo de servicios
GET https://geoide.minvu.cl/server/rest/services?f=json
GET https://geoide.minvu.cl/server/rest/services/IPT?f=json

# Capas por comuna (Región Metropolitana Norte)
GET https://geoide.minvu.cl/server/rest/services/IPT/PRC_RM_Norte/MapServer?f=json
GET https://geoide.minvu.cl/server/rest/services/IPT/PRC_RM_Norte/MapServer/11?f=json   # Las Condes

# Query en GeoJSON
GET https://geoide.minvu.cl/server/rest/services/IPT/PRC_RM_Norte/MapServer/11/query
      ?where=1=1&outFields=ZONA,NOM,UPERM,UPROH,P_DO&f=geojson

# Planes reguladores intercomunales / metropolitanos
IPT/PRMS   # Plan Regulador Metropolitano de Santiago
IPT/PRMC   # Plan Regulador Metropolitano de Concepción
IPT/PRM    # ...
IPT/PRC_<region>   # Araucania, RM_Norte, RM_Sur, Valparaiso, Biobio, Maule,
                   # Coquimbo, Los_Lagos, Los_Rios, Magallanes, Nuble,
                   # OHiggins, Tarapaca, Antofagasta, Arica_y_Parinacota, Atacama, Aysen
# Otros: IPT/Patrimonio, IPT/IPT_AREA_RIESGO, IPT/Limites_Urbanos, IPT/PREMVAL
```

## Anexo B — Referencias

- Ley 21.826 (LGUC, agilización de permisos, admisibilidad 5 días): <https://www.bcn.cl/leychile/navegar?idNorma=1225430>
- LGUC DFL 458: <https://www.bcn.cl/leychile/navegar?idNorma=13560>
- Formato Tipo Informe Revisor Independiente (Circular DDU 514): <https://www.minvu.gob.cl/elementos-tecnicos/formularios/grupo-15-formato-tipo-de-informes-revisor-independiente/>
- Circulares DDU: <https://www.minvu.gob.cl/elementos-tecnicos/circulares-division-de-desarrollo-urbano-ddu/circulares-generales-por-numero/>
- Respuesta a consulta pública del Formato Tipo (31 págs, con el dolor documentado): <https://territoriociudadano.minvu.gob.cl/sites/default/files/2026-08/respuesta_ministerial_formato_tipo_de_informe_del_revisor_independiente.pdf>
- Análisis Ley 21.826: <https://www.cuatrecasas.com/es/latam/publico/art/ley-21-826-estandares-urbanizacion-edificacion>
- Geoportal IDE Chile: <https://geoportal.cl/>
- Precios DeepSeek: <https://api-docs.deepseek.com/quick_start/pricing>
