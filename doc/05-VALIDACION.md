# 05 — Validación

## Estrategia de tests

TDD estricto (RED → GREEN → REFACTOR) según `00-METODOLOGIA.md`. Un test escrito antes y verificado
en rojo por cada comportamiento.

### Qué se testea en cada capa

| Capa | Módulo | Qué se verifica |
|---|---|---|
| L1 | `rasante.dominio` | Lógica pura: veredictos, decimales, invariantes. Un test por artículo citado |
| Corpus | `rasante.corpus` | Carga y validación de esquema; rechazo de YAML sin cita o sin procedencia |
| L0 | `rasante.geo` | Paginación, caché, proyección, point-in-polygon |
| CLI | `rasante.cli` | Invocación, salida JSON estable, códigos de salida |

### Aislamiento de la red

Los tests corren **sin red** (decisión D9). Las respuestas de la API de MINVU están grabadas en
`tests/fixtures/` y se sirven con `httpx.MockTransport`. Un servicio caído no debe romper la suite.

Las fixtures están **recortadas** de respuestas reales (~11 KB) para no engordar el repo. La
descarga completa va a `cache/`, que está en `.gitignore`.

### Test de integración (T0.4)

`tests/integracion/` golpea la API real y detecta si MINVU cambia el esquema, mueve un servicio o
altera `maxRecordCount`. Excluido de la corrida por defecto:

```bash
RASANTE_INTEGRACION=1 uv run pytest -m integracion
```

**No comparar contra literales fijos.** El PRC de una comuna cambia; un test que espere 1718
features rompería sin que nada esté mal. Se compara contra el `count` que la API reporta en el
momento — así sigue detectando truncamiento, que es lo que importa.

## Invariantes que la suite debe proteger

1. **Un `Veredicto` sin `Cita` no se puede construir.** Es lo que impide fabricar veredictos sin
   respaldo normativo.
2. **Un dato desconocido se propaga como `(P)`, nunca como `(C)`.** Un dato que no tenemos jamás
   puede convertirse en un aprobado. Es el invariante más importante del proyecto.
3. **`rasante.dominio` solo importa stdlib** (guardián en `tests/test_arquitectura.py`).
4. **Decimal, nunca `float`** en rutas normativas.
5. **Un fallo de descarga no deja caché parcial** — un GeoJSON a medias se leería como completo.
6. **Toda norma del corpus cita y declara procedencia** — artículo, URL, hash y fecha de extracción.
   Una regla sin fuente no entra al corpus. El corpus guarda **citas, no texto íntegro**: es
   citación, no reproducción (ver `03-DISENO.md` §2.2).

## Validación contra predios reales (cierre de iteración 1)

Es lo que da credibilidad y lo que nadie más puede publicar.

1. Conseguir **N expedientes de permisos ya aprobados** de la comuna piloto (públicos vía Ley de
   Transparencia o portal DOM).
2. Correr la herramienta sobre cada uno.
3. Comparar contra la resolución real de la DOM:
   - zona y parámetros calculados vs. los del CIP
   - **¿cuántas de las observaciones que hizo la DOM habría predicho la herramienta?**
4. Publicar precisión y recall en `doc/`.

La iteración no se declara cerrada sin esto.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| **Responsabilidad civil y penal** | El revisor firma. La salida es una *propuesta* que exige aprobación explícita veredicto por veredicto. Traza completa de qué regla se aplicó y con qué datos |
| **Deriva normativa** — una regla obsoleta es peor que ninguna | `vigencia.desde/hasta` por regla, `hash_fuente`, badge de "última verificación", CI que alerta entradas obsoletas |
| **`P_DO` no sirve como vigencia** | Ver `04-DECISIONES.md`. Es la publicación original, no la del texto consolidado: hay que reconstruir la historia de enmiendas desde la ordenanza |
| **`UPERM`/`UPROH` son texto libre sucio** | En Ñuñoa `UPERM` está polucionado; en Providencia son punteros. Para usos, la autoridad es la ordenanza. Requiere taxonomía canónica de usos |
| **Coma decimal en las ordenanzas** | `0,6` mal parseado se vuelve `6`. El cargador debe exigir separador decimal explícito |
| **Inercia del sector** | La salida es el formato que ya usan, no un sistema nuevo que aprender. Funciona offline |
| **Titularidad de la normativa** | OGUC/LGUC son textos oficiales del Estado. **No verificado** el artículo de la Ley 17.336 que los excluye de protección. Mitigación ya aplicada: el corpus guarda parámetros extraídos + citas + hash, no republica documentos municipales íntegros |
| **El proyecto se estanca por falta de mantención** | Ver `01-VISION.md`: se monetiza la vigencia garantizada, no el acceso |
