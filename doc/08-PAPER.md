# §3–§4 formalizados — borrador de paper

> **Qué es este archivo.** Las secciones 3 y 4 del paper, escritas contra el código que existe. Cada
> afirmación formal apunta al artefacto que la sostiene: una decisión de diseño (`D…`), un test que
> la verifica mecánicamente, o los dos. **Lo que no tiene respaldo, no está acá.**
>
> **Alcance, y hay que decirlo en la primera página del paper:** estos teoremas son propiedades **del
> motor dado un corpus**. No dicen nada sobre si el corpus es correcto. Un motor que satisface los
> tres teoremas sobre una ordenanza mal transcrita produce veredictos equivocados con perfecta
> disciplina. La corrección del corpus es un problema distinto, y la respuesta del proyecto es
> verificable pero no formal: cada cita se contrasta contra el texto fuente
> (`tests/test_realidad_corpus.py`, `tests/test_corpus_nunoa.py`) y toda fuente exige firma humana
> (D18).

---

## §3 El invariante de seguridad epistémica

### 3.1 El escenario

Un **corpus** `C = (D, H, X)` es un conjunto de documentos normativos que aportan:

- `D`: **derivaciones** — cómo se calcula el valor de un parámetro a partir de las primitivas del
  proyecto. `d ∈ D` es una expresión de un vocabulario cerrado.
- `H`: **hechos** — predicados nombrados que deciden qué límite rige.
- `X`: **excepciones** — normas de aplicación general que modifican, por un factor, un valor que fija
  otro instrumento (D20).

Un **proyecto** `p` declara primitivas (superficies, pisos, altura, viviendas) y **una zona** `z`
declara parámetros con límites, cada uno con su cita y su `sentido` (`MAXIMO`/`MINIMO`).

Un **estado de conocimiento** `K : H ∪ H_ext → {⊤, ⊥, ?}` asigna a cada hecho si se cumple, no se
cumple, o **no se sabe**. El corpus determina `K` parcialmente —vía `H`, que son expresiones sobre
`p` y `z`— y una **capa de decisión externa** puede aportar el resto sobre hechos que el corpus
declara incalculables (D19, y §5).

El **veredicto** es una función `V(p, z, K) : Params(z) → {C, NC, P, NP}`: cumple, no cumple,
pendiente, no procede.

### 3.2 El invariante

> **(ES) Seguridad epistémica.** `V(·) = C` solo si existe un límite `ℓ` —declarado por una fuente
> **firmada**, con todas sus condiciones decididas en `K`, y con el valor del proyecto computable—
> tal que el proyecto satisface `ℓ`.

El invariante es **asimétrico en su forma y simétrico en su efecto**: habla de `C`, pero `NC` es una
afirmación con la misma carga —un informe que rechaza un proyecto también está firmado por un
profesional— y por eso la cascada de §4 protege las dos por igual. `P` y `NP` no afirman nada sobre
el cumplimiento y quedan fuera del invariante por construcción.

### 3.3 El retículo, y por qué tres valores no alcanzan a explicarlo

`{C, NC, P}` con `NP` aparte no es un orden total, y tratarlo como tal es el error que el diseño
evita. Lo relevante es la relación entre estados de conocimiento y veredictos:

```
        ⊤ ─────────────┐
   K:   ?  ──►  V ∈ {C, NC, P}
        ⊥ ─────────────┘
```

Un veredicto **no** es una probabilidad de cumplimiento y no se puede leer como tal. `P` no significa
"probablemente cumple": significa que el motor **no puede afirmar**, y §4.4 demuestra que un `P`
puede resolverse a `C` **o** a `NC` —las dos— así que no está sesgado hacia ningún lado.

### 3.4 Lo que el invariante NO es

Vale la pena porque es el malentendido más probable de un revisor:

- **No es "ser conservador".** Un motor que respondiera `P` a todo lo satisfaría trivialmente y sería
  inútil. La métrica relevante es que el motor **no se niega indiscriminadamente**: sobre Ñuñoa Z-2
  concluye **6 de 12** parámetros, y los 6 pendientes tienen causas distintas (§4.5, E4).
- **No es una probabilidad.** El motor no combina confianzas ni emite un score de cumplimiento (D17).
  La incertidumbre vive en la capa de decisión, que decide **si un dato está listo**, no **cuánto
  cumple**.
- **No es verificable por inspección del corpus.** Es una propiedad del **motor**: se verifica sobre
  el código, y §4 la demuestra y los tests la fijan.

---

## §4 El motor L1 como procedimiento de decisión

### 4.1 La cascada

`_decidir(p, ℓ, I, v, r)` —donde `I` son los hechos indeterminados que condicionan el límite, `v` el
valor del proyecto y `r` la firma de la fuente— recorre **seis pasos en orden**, y el orden no es
negociable:

| # | condición | salida |
|---|---|---|
| 1 | `¬r` (fuente sin firmar) | `P` |
| 2 | `estado = NO_APLICA` | `NP` |
| 3 | `I ≠ ∅` | `P` |
| 4 | `estado = DESCONOCIDO` o `ℓ = ⊥` | `P` |
| 5 | `v = ⊥` | `P` |
| 6 | `sentido = MAXIMO ? v ≤ ℓ : v ≥ ℓ` | `C` / `NC` |

**El orden va de la causa más general a la más particular**, y cada paso existe porque omitirlo
produjo —o produciría— un veredicto falso firmado:

- El **paso 1 va primero** porque es la única condición que invalida a todas las demás (D18).
  Cubre también `NP`: "no procede" es una afirmación *sobre la norma*, y no se puede hacer desde un
  dato sin revisar.
- El **paso 2 va antes que el 3** porque `NP` **sí** es afirmable con fuente firmada.
- El **paso 3** distingue "no sé **cuál** límite rige" de "no sé **cuál es** el límite". Los dos son
  `P` y el arreglo es distinto.
- El **paso 6 es el único sitio donde nace un `C` o un `NC`.** Los pasos 1 a 5 **no comparan**.

`MotivoPendiente` (`motor.py`) es la **única definición** de esta cascada: `_decidir` y el reporte de
cobertura leen los dos de ahí, así que no pueden divergir. Un test comprueba sobre el código fuente
que **ningún `P` ni `NP` aparece después de la comparación** (`test_dominio_observabilidad.py`).

### 4.2 Totalidad y determinismo

**Proposición 1.** `V` es una **función total** y determinista sobre su dominio.

*Demostración.* Todos los pasos son decidibles: `r` es un campo booleano; `estado` y `sentido` son
enums; `I` es una tupla finita; `ℓ` y `v` son `Decimal` o `None`. La evaluación de expresiones
termina (el árbol es finito y la recursión está acotada por su tamaño) y una división por cero
devuelve `None` en vez de levantar. Los parámetros se recorren en orden determinista
(`sorted(..., key=clave)`), y `excepciones_generales` y `_candidatos` preservan el orden de
declaración. ∎

Nada acá se apoya en una implementación particular: `V` es una función de `(p, z, K)` y el motor la
calcula. **Es lo que hace al veredicto reproducible años después**, que es la propiedad que un
informe firmado necesita.

### 4.3 Corrección de `C`

**Teorema 1 (solidez de `C`).** Si `V(param) = C`, entonces el proyecto satisface el límite vigente,
y ese límite está respaldado por una fuente firmada.

*Demostración.* `C` se emite solo en el paso 6, que exige haber atravesado los pasos 1 a 5. El paso 1
garantiza `r`; el 3 garantiza `I = ∅` —todas las condiciones de todos los candidatos están decididas
o descartadas—; el 4 garantiza que hay un límite `ℓ` con valor; el 5 garantiza que `v` es computable.
El paso 6 devuelve `C` exactamente cuando `v` satisface `ℓ`. La cita del veredicto es la del límite
vigente o la del parámetro, y `Veredicto` **no se puede construir sin `Cita`** (invariante de
construcción, `modelos.py`). ∎

**Corolario.** `NC` tiene la misma garantía por el mismo argumento: se emite en el paso 6.o.

### 4.4 Monotonía, y qué la compra

Sea `K ⊑ K'` un **refinamiento**: todo hecho que `K` resuelve, `K'` lo resuelve **igual**, y `K'`
puede además resolver hechos que en `K` eran `?`. Refinar es **agregar información**, no
contradecirla.

**Teorema 2 (monotonía bajo refinamiento).** Si `V(K) ∈ {C, NC}` y `K ⊑ K'`, entonces `V(K') = V(K)`.
Solo `P` es inestable.

*Demostración.* `V(K) ∈ {C, NC}` exige alcanzar el paso 6, o sea `I = ∅`. Por la definición de
`_limite_vigente`, un candidato deja de aportar a `I` en exactamente dos casos: algún conjuncto suyo
es `⊥` (queda descartado por el cortocircuito `X ∧ ⊥ = ⊥`), o **todos** sus conjunctos están
decididos. Así que al alcanzar el paso 6, **todo candidato está descartado o decidido**, y los
descartados lo están por un `⊥` que `K` ya conoce. Un refinamiento preserva `⊤` y `⊥` y solo puede
convertir `?` en uno de los dos: un candidato descartado sigue descartado, y uno decidido sigue
decidido. El conjunto de límites vigentes no cambia, el límite elegido tampoco, y la comparación del
paso 6 da el mismo resultado. ∎

**Demostrado por búsqueda, no solo por argumento.** `tests/test_dominio_no_monotonia.py` enumera los
9 estados de conocimiento sobre los hechos externos de `2.6.5` × 6 proyectos y examina **todos** los
pares `K ⊑ K'`. La búsqueda no encuentra ninguna inversión. **Que vuelva vacía es el resultado.**

> **Nota de método.** El autor de este trabajo enunció primero el teorema **contrario** —que el
> veredicto era no monótono y que aprender un dato podía revocar un `C`— y la búsqueda exhaustiva lo
> refutó: el contraejemplo propuesto requería **cambiar** un hecho de `⊥` a `⊤`, y eso es **revisión**,
> no refinamiento. El test escrito para confirmar la intuición la desmintió. Se reporta porque es
> evidencia de que el método de falsación funciona, y porque la versión correcta **es más fuerte**.

**Teorema 3 (la negativa a concluir compra la monotonía).** Bajo la semántica alternativa que trata
un hecho indeterminado como "la excepción más permisiva aplica" —la opción que un implementador
escribiría primero— la monotonía **falla**.

*Demostración (por contraejemplo, sobre el corpus real).* Base `cus = 4`, proyecto `cus = 5,5`,
`2.6.5` concede +50 % por la letra b) y +30 % por la letra c). Con `K = {b: ?, c: ⊤}` la semántica
permisiva concede el +50 % → límite 6,0 → **`C`**. Con `K' = {b: ⊥, c: ⊤} ⊒ K` → límite 5,2 →
**`NC`**. El refinamiento **revoca el cumplimiento**. ∎

El motor real da `P` en `K` y `NC` en `K'`, y por el Teorema 2 no puede dar otra cosa.

> **Lo que esto significa, y es la tesis del paper:** la negativa a concluir **no es prudencia
> defensiva**, es la condición que **compra** la estabilidad del veredicto. "Elegimos ser
> conservadores" es una decisión de diseño; "ser conservadores es lo que hace el veredicto monótono,
> y relajarlo lo rompe" es un resultado, y tiene un contraejemplo en una ordenanza real.

**Corolario (el portero tiene dos bordes).** Por el Teorema 2, `P` es el único inestable; y por la
búsqueda de `test_dominio_no_monotonia.py`, un `P` alcanza **tanto `C` como `NC`**. Por lo tanto,
equivocarse resolviendo un hecho como **falso** es tan peligroso como resolverlo como cierto: un
umbral de un solo lado —"resuelvo si la confianza supera 0,8"— dejaría pasar un `0,3` como `⊥` y
produciría un veredicto invertido. **La banda gris de dos lados (`0,2–0,8`) no es una elección de
tuning: es una consecuencia del Teorema 2.**

### 4.5 La negativa no es indiscriminada

Un motor que devolviera `P` siempre satisfaría (ES) y el Teorema 2, y sería inútil. La propiedad que
lo hace útil es **medible**, y se mide con `dominio/cobertura.py` (E4):

| Zona Z-2 de Ñuñoa, 12 parámetros | |
|---|---|
| Concluidos sin clasificar el expediente | **6** |
| `parametro_desconocido` | 2 — la ordenanza remite a otra norma |
| `sin_dato_proyecto` | 4 — el expediente no declara el dato |

Y el hallazgo que lo demuestra: **`cus` se concluye** aunque `2.6.5` lo condicione a hechos que el
corpus no puede calcular, porque el proyecto **no se acoge** al Conjunto Armónico (D21) y el
cortocircuito descarta las excepciones. Los hechos desconocidos **dejan de importar**.

> **El motor no se niega cuando falta un dato: se niega cuando la duda cambia el resultado.**

Acogido, el mismo expediente baja a 5 de 12, y clasificando los dos hechos vuelve a 6. La cobertura
depende del **expediente**, no solo del corpus — que es exactamente la razón de existir de la capa
de decisión de §5.

---

## Lo que falta para cerrar §3–§4

| | |
|---|---|
| **§5** | La capa calibrada y el teorema de preservación. El corolario del §4.4 ya da la mitad: el portero debe ser de dos lados. Falta **calibrarlo** (E3/P2): confiabilidad y ECE sobre datos etiquetados |
| **§7** | Precisión vs. revisor humano. Los teoremas hablan del motor dado un corpus; **no dicen si el motor acierta**. Eso es matriz de confusión, y necesita T1.15 |
| **Notación** | Unificar con la del borrador y con las tres citas verificadas |

**Lo que NO hay que escribir:** que esto sea "the first formal treatment of deterministic normative
evaluation engines". Catala (ICFP 2021) es un lenguaje de programación para la ley con semántica
formal, y la lógica deóntica defeasible lleva dos décadas formalizando normas con excepciones. La
afirmación defendible es más acotada y más útil: **aislar el invariante epistémico como restricción de
diseño, y demostrar que la negativa a concluir es lo que hace el veredicto monótono bajo
refinamiento** — con un contraejemplo sobre una ordenanza real para la semántica que lo rompe.
