# 04 — Registro de decisiones

Decisiones abiertas, cerradas y su fundamento. Las decisiones de arquitectura **D1–D12** viven en
`03-DISENO.md`; acá está el registro de las decisiones de alcance y de datos.

## Índice

| ID | Decisión | Estado |
|---|---|---|
| A1 | Entrada de la iteración 1: coordenada vs rol/CIP | ✅ cerrada — por **coordenada** |
| A2 | Comuna piloto | 🟦 recomendada **Ñuñoa**, sin confirmar |
| A3 | Tercer parámetro: `altura_maxima` vs `densidad` | ⬜ abierta (bloquea T1.1) |
| — | `P_DO` como fuente de vigencia (corrige D5) | ⚠️ **corregida** — ver §3 |

---

# A2 — Decisión de comuna piloto (T0.3)

**2026-09-26** · Datos obtenidos en vivo de `IPT/PRC_RM_Norte` (MINVU) y de las ordenanzas
municipales. Candidatas: **Las Condes** (capa 11), **Ñuñoa** (capa 17), **Providencia** (capa 21).
Las tres están en `PRC_RM_Norte`, no hay que cruzar servicios.

---

## 1. Evidencia

### 1.1 Cobertura de campos

| Comuna | features | zonas | UPERM | UPROH | P_DO | NOM |
|---|---|---|---|---|---|---|
| Las Condes | 424 | 66 | 100 % | 100 % | 100 % | 100 % |
| Ñuñoa | 1718 | 40 | 100 % | 100 % | 100 % | 100 % |
| Providencia | 270 | 20 | 100 % | 100 % | 100 % | 100 % |

La cobertura es total en las tres. El problema no es presencia de datos, es su **contenido**.

### 1.2 Geometría

| Comuna | features | geometrías únicas | repetidas | máx. polígonos por zona |
|---|---|---|---|---|
| Las Condes | 424 | 424 | 0 | 139 |
| Ñuñoa | 1718 | 1718 | 0 | **514** |
| Providencia | 270 | 270 | 0 | 41 |

Sin duplicados en ninguna: no hay ambigüedad por solapamiento exacto. Ñuñoa está muy fragmentada
(1718 polígonos para 40 zonas) — afecta el tamaño del índice, no la corrección.

### 1.3 Calidad semántica de los usos — el factor decisivo en contra

**Providencia** tiene `UPERM` y `UPROH` con **el mismo puntero literal** en todas las zonas:

```
ZONA PzV | NOM="PzV Plazas Vecinales"
  UPERM: "Según art. 2.3 de la Ordenanza Local"
  UPROH: "Según art. 2.3 de la Ordenanza Local"
```

Cero dato utilizable. Concuerda con los separadores: 270 features y solo **3 `;`** en total.
La capa es un mapa, no un dataset de usos.

**Ñuñoa** tiene `UPERM` **polucionado**: el campo mezcla usos con notas de altura y texto
truncado a mitad de frase.

```
ZONA Z-2 | UPERM: "área afectada por la zona de protección de helipuerto, deberán
                    cumplir con las alturas fijadas en"
         | UPROH: "Equipamiento; Esparcimiento; salud (algunas), seguridad (algunas); ..."
ZONA Z-4 | UPERM: "Aeronáutica Civil."
```

`UPERM` no es confiable. `UPROH` sí es utilizable, pero con calificadores `(algunas)` /
`(todas)` que exigen interpretación.

**Las Condes** es la única con usos limpios y autodescriptivos:

```
ZONA UEe3/Ee3 | NOM="UEe3/Ee3 Zona Especial 3 Área de Parques"
  UPERM: "Equipamiento de esparcimiento."
  UPROH: "Residencial; equipamiento de comercio, culto, culto, deporte, ..."
```

Único defecto: **14 tokens duplicados** (`"culto, culto"`) y espacios dobles. Normalizable.

### 1.4 Disponibilidad de la ordenanza — el mayor costo del proyecto

Los parámetros numéricos (cos, cus, altura, subdivisión predial) **no están en ArcGIS en ninguna
comuna**. Hay que extraerlos de la ordenanza. Ese es el trabajo real.

| Comuna | Fuente | Estado |
|---|---|---|
| **Ñuñoa** | [Texto refundido, jun 2025, 76 págs](https://www.nunoa.cl/app/uploads/2025/06/Ordenanza-PRC-Texto-Refundido-incluye-Fallo-Enmienda-1-1.pdf) (1,3 MB) | **Consolidado en un solo documento**, con las enmiendas incorporadas |
| Providencia | [Decreto 424 en LeyChile](https://www.bcn.cl/leychile/navegar/imprimir?idNorma=189886) + modificaciones dispersas | Autoritativo y versionado, pero repartido |
| Las Condes | [Decreto 3218](https://www.bcn.cl/leychile/navegar/imprimir?idNorma=218302) (modificación Nº2) + muchas otras | Muy enmendado: consolidar es caro |

Verificación sobre el PDF de Ñuñoa: 76 páginas, 207.531 caracteres, y **90 líneas de parámetros
limpiamente extraíbles**:

```
Coeficiente de ocupación de suelo 0,6
Coeficiente de ocupación de suelo pisos superiores 0,4
Coeficiente de constructibilidad 4
Coeficiente de ocupación de suelo 0,6
Coeficiente de ocupación de suelo pisos superiores 0,4
Coeficiente de constructibilidad 3,6
```

Ocurrencias: `ocupación de suelo` 59 · `altura máxima` 45 · `constructibilidad` 39 ·
`subdivisión predial mínima` 50. Códigos de zona detectados en el texto: `Z-1, Z-1A/B/C, Z-2,
Z-2A, Z-3, Z-3A, Z-4, Z-4C, Z-4m, Z-5, Z-5A, Z-6, Z-7, Z-7A/B, Z-8`.

---

## 2. Decisión

> ### Comuna piloto: **Ñuñoa**

El criterio dominante es **el costo del corpus**, que es el activo del proyecto: **Ñuñoa tiene un
texto refundido único y reciente con los parámetros en tablas extraíbles.** Ninguna otra candidata
ofrece eso. Sobre 40 zonas, extraer 3–5 a mano para T1.7 es acotado y trazable.

Las Condes tiene mejores datos de usos, y fue la tentación obvia, pero tiene **66 zonas** y una
ordenanza muy enmendada: el costo de construir y *mantener* el corpus es el más alto de las tres.
Los usos de ArcGIS no son la autoridad de todos modos — la ordenanza sí.

**Corrección de mi recomendación inicial.** En el plan recomendé Ñuñoa por "PRC reciente y
ordenanza legible", que era hand-waving: su PRC es de 1989 y su `UPERM` está polucionado. La
conclusión sobrevive, pero por una razón distinta y verificada: **el texto refundido de 2025**.

### Deudas registradas de Ñuñoa

1. **`UPERM` inutilizable.** Para usos (iteración 2+) la fuente es la ordenanza, no ArcGIS.
2. **`UPROH` con calificadores** `(algunas)` / `(todas)`: requieren taxonomía canónica.
3. **Geometría muy fragmentada** (máx. 514 polígonos en una zona): vigilar el rendimiento del índice.
4. **Coma decimal.** La ordenanza escribe `0,6` y `3,6`. El cargador de T1.3 **debe** parsear `,`
   como separador decimal, o producirá `6` y `36`.
5. **`cos` tiene dos variantes**: "ocupación de suelo" y "ocupación de suelo **pisos superiores**".
   El modelo de dominio necesita un calificador, no un único `cos`.

---

## 3. Hallazgo que corrige el diseño (D5)

**`P_DO` es un único valor para toda la capa**, no por polígono:

| Comuna | `P_DO` | valores distintos |
|---|---|---|
| Las Condes | 30/05/1994 | 1 |
| Ñuñoa | 27/10/1989 | 1 |
| Providencia | 23/01/2007 | 1 |

Es la **publicación original del instrumento**, no la vigencia del texto consolidado. Ñuñoa
reporta 1989 teniendo un refundido de 2025. Las Condes reporta 1994 con una modificación Nº2
posterior.

**Consecuencia:** mi afirmación en `03-DISENO.md` D5 de que `P_DO` da "versionado normativo gratis"
es **incorrecta**. `vigencia.desde` **no puede** derivarse de `P_DO`. Hay que reconstruir la
historia de enmiendas desde la propia ordenanza.

`P_DO` sigue siendo útil como **procedencia** ("publicación original del instrumento"), no como
`vigencia`. La capacidad de "evaluar contra la norma vigente a la fecha de ingreso" sigue siendo
alcanzable, pero es más trabajo del que impliqué. Ver **D12** en `03-DISENO.md`.
