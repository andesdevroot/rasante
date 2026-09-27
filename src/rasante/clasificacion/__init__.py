"""Capa de clasificación con contrato tipado (D19).

El motor determinista solo sabe comparar números. Usos de suelo, agrupamiento y las condiciones que
no son aritmética sobre el proyecto no tienen representación ahí. Esta capa las responde con las
tres
primitivas de JEV —`choice`, `noul`, `score`— y devuelve **respuestas tipadas con confianza**.

**Vive fuera de `rasante.dominio`**: puede hablar por red, y el dominio no (D2).

**El portero es lo que importa:** una respuesta por debajo del umbral no se resuelve, queda marcada
para revisión humana. Es D18 aguas arriba — la confianza decide *si un dato está listo*, no *cuánto
cumple*.
"""

from __future__ import annotations
