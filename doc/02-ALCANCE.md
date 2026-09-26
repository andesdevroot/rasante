# 02 — Alcance

## Qué es rasante

Copiloto open source para revisores independientes y Direcciones de Obras Municipales. Computa
normas urbanísticas de forma **determinística** (OGUC + plan regulador comunal) y emite el Formato
Tipo oficial de informe del revisor independiente (Circular DDU 514).

Problema, mercado y fuentes verificadas: `01-VISION.md`.
Arquitectura y decisiones: `03-DISENO.md`.

## Iteración 1 — vertical slice (alcance actual)

**Entrada:** una coordenada (`lat`, `lon`).
**Salida:** código de zona del PRC + `cos`, `cus`, `altura_maxima` y `densidad`, **cada uno con su
cita**.

Atraviesa L0 y L1 completos. Es el corte más pequeño que prueba la arquitectura entera.

Por qué coordenada y no rol ni CIP: ver `04-DECISIONES.md` (A1). El rol de avalúo del SII no tiene
geometría pública masiva; la del predio vive en el CIP, y parsearlo requiere LLM (iteración 2).

### Los 4 parámetros

`cos` (coeficiente de ocupación de suelo), `cus` (coeficiente de constructibilidad), `altura_maxima`
y `densidad` (unidades de vivienda por hectárea).

Tres son escalares comparables directamente. **`densidad` no**: es una razón derivada que exige
datos del `Proyecto` (superficie del predio y número de viviendas). Es la única regla de la
iteración que no es "valor contra valor", y obliga a que el motor reciba el proyecto completo.
Implicaciones completas en `04-DECISIONES.md` (A3).

`cos` además necesita un **calificador**: las ordenanzas distinguen "ocupación de suelo" de
"ocupación de suelo pisos superiores".

## Fuera de alcance en iteración 1

LLM · extracción de PDF · informes DOCX/PDF · UI · demo web · rasantes · estacionamientos ·
distanciamientos · checklist de admisibilidad · usos de suelo.

## Iteraciones siguientes

| Iteración | Contenido |
|---|---|
| 2 | Ingesta de CIP y Formularios Únicos Nacionales · extracción con `deepseek-flash` visión · citas por ID de regla |
| 3 | Emisión del Formato Tipo DOCX/PDF (DDU 514) con veredictos y narrativa del Art. 116 Ley 21.718 |
| 4 | Checklist de admisibilidad Ley 21.826 (5 días hábiles) |
| 5 | UI local SvelteKit · instaladores Nuitka/Briefcase · demo pública FastAPI |
| 6 | Rasantes, estacionamientos, distanciamientos, aguas lluvias · 2ª y 3ª comuna |

## Comuna piloto

**Ñuñoa**, fijada el 2026-09-26 (A2). Justificación con datos en `04-DECISIONES.md`. Una sola
comuna **hecha exhaustivamente**, no diez a medias.
