"""Motor de evaluación. Capa L1, **módulo puro** (D2: solo stdlib).

Compara un `Proyecto` contra los parámetros que una `Zona` declara y devuelve un `Veredicto` por
parámetro, cada uno con su cita.

## El invariante que sostiene el producto

> **Un dato que no tenemos da `P` (pendiente), jamás `C` (cumple).**

Un `(C)` afirma que el proyecto cumple la norma. Si la norma es desconocida, si el dato del proyecto
falta, si no sabemos cómo comparar un parámetro, o si **no sabemos cuál de sus límites rige**,
afirmarlo sería un informe falso firmado por un profesional.

## El corpus manda (D14, D16)

**Cómo se calcula** viene de `derivaciones`, **cuál límite aplica** viene de los hechos, y **hacia
dónde compara** viene del `sentido` que declara cada parámetro. El motor no hardcodea nada.

Un hecho puede venir de dos lados: de una expresión del corpus (`clasificar` la evalúa) o de afuera
(`hechos_externos`), cuando el corpus declara que no es aritmética sobre el proyecto — saber si un
predio constituye una manzana existente exige el acta registral, no una resta. El motor no
distingue: para él un hecho es `True`, `False` o `None`, y `None` siempre da `P`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from .modelos import (
    CodigoVeredicto,
    EstadoParametro,
    Limite,
    Parametro,
    Proyecto,
    Sentido,
    TipoLimite,
    Veredicto,
    Zona,
)
from .reglas import (
    Clasificacion,
    ErrorHechoDuplicado,
    Excepcion,
    ProcedenciaHecho,
    Reglas,
    declarar_nombres,
    evaluar_expresion,
    evaluar_hecho,
)
from .vocabulario import nombres_de_expresion


def evaluar(
    proyecto: Proyecto,
    zona: Zona,
    reglas: Reglas,
    hechos_externos: Mapping[str, bool | None] | None = None,
) -> list[Veredicto]:
    """Evalúa cada parámetro que la zona declara, en orden determinista por clave.

    `hechos_externos` son los hechos que el corpus declara pero no puede calcular: los resuelve el
    puente (T1.10) con la capa de clasificación. Se tratan **igual** que los del corpus — un hecho
    externo indeterminado es exactamente tan indeterminado como uno que el corpus no pudo evaluar.
    """
    valores = valores_del_proyecto(proyecto)
    clasificacion = clasificar(proyecto, zona, reglas, valores, hechos_externos)
    revisada = zona.procedencia.revisada
    parametros = sorted(zona.parametros.values(), key=lambda p: p.clave)
    return [
        _evaluar_uno(parametro, valores, reglas, clasificacion, revisada)
        for parametro in parametros
    ]


def clasificar(
    proyecto: Proyecto,
    zona: Zona,
    reglas: Reglas,
    valores: Mapping[str, Decimal | None] | None = None,
    hechos_externos: Mapping[str, bool | None] | None = None,
) -> Clasificacion:
    """Qué hechos del corpus se cumplen para este proyecto, contra esta zona.

    Tres estados por hecho: `True`, `False` y **`None` = no se sabe**. El tercero es lo que impide
    que un dato faltante se traduzca en aplicar el límite más permisivo.

    Un hecho externo **no puede sobrescribir** uno del corpus: si un mismo hecho tuviera dos
    fuentes, cuál gana sería una decisión implícita. El corpus lo impide al validar, y acá se
    vuelve a exigir por si alguien llama al motor directamente.
    """
    disponibles: dict[str, Decimal | None] = dict(valores or valores_del_proyecto(proyecto))
    disponibles.update(valores_normados(zona))
    evaluados: dict[str, bool | None] = {}
    procedencia: dict[str, ProcedenciaHecho] = {}
    for nombre, hecho in reglas.hechos.items():
        estado = evaluar_hecho(hecho.expresion, declarar_nombres(hecho.expresion, disponibles))
        evaluados[nombre] = estado
        if estado is None:
            procedencia[nombre] = _motivo(hecho.expresion, disponibles)
    for nombre, estado in (hechos_externos or {}).items():
        if nombre in evaluados:
            raise ErrorHechoDuplicado(
                f"el hecho {nombre!r} ya lo define el corpus: un hecho externo no puede "
                "sobrescribirlo, porque cuál de las dos fuentes gana sería una decisión implícita"
            )
        evaluados[nombre] = estado
        if estado is None:
            procedencia[nombre] = ProcedenciaHecho.EXTERNO_INDETERMINADO
    return Clasificacion(
        hechos=MappingProxyType(evaluados), procedencia=MappingProxyType(procedencia)
    )


def _motivo(expresion: str, disponibles: Mapping[str, Decimal | None]) -> ProcedenciaHecho:
    """Por qué una expresión no dio un número (T3).

    Se calcula **solo para los hechos que salieron `None`**, nunca en el camino caliente: evaluar un
    proyecto con todos sus datos no paga nada por esto.

    Distingue dos causas que `evaluar_expresion` deliberadamente confunde —las dos son "no se pudo
    calcular", y para el veredicto da lo mismo—: si falta un nombre, el problema es el **dato**; si
    están todos, el problema es la **expresión**. El arreglo de cada una es distinto.
    """
    completos = declarar_nombres(expresion, disponibles)
    if any(completos[nombre] is None for nombre in nombres_de_expresion(expresion)):
        return ProcedenciaHecho.DATO_FALTANTE
    return ProcedenciaHecho.EXPRESION_NO_CALCULABLE


def valores_del_proyecto(proyecto: Proyecto) -> dict[str, Decimal | None]:
    """Las primitivas del proyecto, con los nombres del vocabulario del corpus.

    Un campo que el proyecto no declara se incluye como `None`, no se omite: así el intérprete
    distingue "no lo declaró" de "no existe ese nombre".
    """
    return {
        "superficie_predio_m2": proyecto.superficie_predio_m2,
        "superficie_primer_piso_m2": proyecto.superficie_primer_piso_m2,
        "superficie_edificada_m2": proyecto.superficie_edificada_m2,
        "numero_pisos": _decimal(proyecto.numero_pisos),
        "numero_viviendas": Decimal(proyecto.numero_viviendas),
        "altura_m": proyecto.altura_m,
        "acoge_conjunto_armonico": Decimal(1) if proyecto.acoge_conjunto_armonico else Decimal(0),
    }


def valores_normados(zona: Zona) -> dict[str, Decimal]:
    """Los valores que la zona fija, por clave y por id.

    Un hecho puede referirse a `superficie_predial_minima`, que **no** es una primitiva del proyecto
    sino un valor del plan regulador. Se usa el límite base: es el valor por defecto de la zona.
    """
    valores: dict[str, Decimal] = {}
    for clave, parametro in zona.parametros.items():
        base = parametro.base
        if base is not None:
            valores[clave] = base.valor
            valores.setdefault(parametro.id, base.valor)
    return valores


def _evaluar_uno(
    parametro: Parametro,
    valores: Mapping[str, Decimal | None],
    reglas: Reglas,
    clasificacion: Clasificacion,
    fuente_revisada: bool,
) -> Veredicto:
    limite, indeterminados = _limite_vigente(parametro, clasificacion, reglas)
    derivacion = reglas.derivaciones.get(parametro.clave)
    valor_proyecto = (
        evaluar_expresion(derivacion.expresion, declarar_nombres(derivacion.expresion, valores))
        if derivacion is not None
        else None
    )
    return Veredicto(
        parametro_id=parametro.id,
        codigo=_decidir(parametro, limite, indeterminados, valor_proyecto, fuente_revisada),
        cita=parametro.cita if limite is None else limite.cita,
        valor_norma=None if limite is None else limite.valor,
        valor_proyecto=valor_proyecto,
        calificador=parametro.calificador,
    )


def _limite_vigente(
    parametro: Parametro, clasificacion: Clasificacion, reglas: Reglas
) -> tuple[Limite | None, tuple[str, ...]]:
    """El límite que rige, y los hechos que no se pudieron determinar.

    Las **excepciones sustituyen al base**, no se le suman: si ligaran los dos y ganara el más
    restrictivo, la excepción del Conjunto Armónico de la OGUC `2.6.5` —que *amplía* el `cus`—
    nunca podría aplicarse y la norma sería letra muerta. Acá "gana el más restrictivo" se aplica
    **entre excepciones**, no entre la excepción y el base.

    Entre **varias excepciones** que se cumplen a la vez manda la más restrictiva: si dos normas
    discrepan, la prudencia es exigir la más severa. Eso cubre el caso real de `2.6.5`, donde un
    proyecto puede cumplir la letra a) —50 %— y la letra c) —30 %— a la vez.
    """
    faltantes: set[str] = set()
    vigentes: list[Limite] = []
    for limite in _candidatos(parametro, reglas):
        aplica = clasificacion.aplica(limite.cuando)
        if aplica is None:
            faltantes.update(clasificacion.indeterminados(limite.cuando))
        elif aplica:
            vigentes.append(limite)

    if faltantes:
        return None, tuple(sorted(faltantes))
    if vigentes:
        return min(vigentes, key=lambda x: x.valor), ()
    return parametro.base, ()


def _candidatos(parametro: Parametro, reglas: Reglas) -> list[Limite]:
    """Todos los límites que podrían regir: los que fija la zona y los de aplicación general."""
    propios = [x for x in parametro.limites if x.tipo is TipoLimite.EXCEPCION]
    generales = [
        ampliado
        for ampliado in (
            _ampliado(excepcion, parametro)
            for excepcion in excepciones_generales(parametro, reglas)
        )
        if ampliado is not None
    ]
    return propios + generales


def excepciones_generales(parametro: Parametro, reglas: Reglas) -> tuple[Excepcion, ...]:
    """Las excepciones de aplicación general que nombran este parámetro.

    Se comparan contra la **clave compuesta**: una excepción sobre `cos` no debe alcanzar a
    `cos.pisos_superiores`.
    """
    return tuple(e for e in reglas.excepciones if e.parametro == parametro.clave)


def _ampliado(excepcion: Excepcion, parametro: Parametro) -> Limite | None:
    """El límite que resulta de aplicar el factor sobre el valor que fija la zona.

    Sin base no hay nada que ampliar: el factor multiplica un número que no está, así que **no se
    inventa un valor**. Devuelve `None` y el parámetro dará `P` por su cuenta — el mismo principio
    de siempre, aplicado a la aritmética en vez de al dato.
    """
    base = parametro.base
    if base is None:
        return None
    return Limite(
        tipo=TipoLimite.EXCEPCION,
        valor=base.valor * excepcion.factor,
        unidad=base.unidad,
        cita=excepcion.cita,
        cuando=excepcion.hechos,
    )


def _decidir(
    parametro: Parametro,
    limite: Limite | None,
    indeterminados: tuple[str, ...],
    valor_proyecto: Decimal | None,
    fuente_revisada: bool,
) -> CodigoVeredicto:
    """El veredicto de un parámetro. **El orden importa y no es negociable.**

    Todo lo que no se puede afirmar sale antes de cualquier comparación. El orden va de la causa más
    general a la más particular, y cada paso existe porque omitirlo produjo —o produciría— un
    veredicto falso firmado por un profesional:

    1. **`fuente_revisada`.** De un corpus que nadie firmó no se afirma nada. Va primero porque es
       la única condición que invalida **todas** las demás: si el valor no está revisado, da lo
       mismo cuán completo sea el proyecto. Cubre también `NO_APLICA`: "no procede" es una
       afirmación sobre la norma, y no se puede hacer desde un dato sin revisar. (D18)
    2. **`estado is NO_APLICA`.** La norma existe pero no rige para este caso. Es una afirmación
       *negativa* —"esto no le aplica"— y por eso va después de la firma: se puede afirmar, pero
       solo con fuente revisada.
    3. **`indeterminados`.** No sabemos **cuál** de los límites rige, porque algún hecho quedó en
       `None`. Es distinto de "no sabemos el límite": acá el límite está declarado y lo que falta es
       saber si aplica. Elegir uno sería elegir el permisivo la mitad de las veces. (D16)
    4. **`estado is DESCONOCIDO` o `limite is None`.** No sabemos **cuál es** el límite: la zona no
       lo fija, o la excepción aplicable no se pudo calcular por falta de base. (D20)
    5. **`valor_proyecto is None`.** Sabemos el límite y sabemos que rige, pero no cuánto mide el
       proyecto. Es el último `P` posible antes de comparar.
    6. **La comparación**, y recién acá. `sentido` dice hacia dónde: `MAXIMO` cumple por debajo,
       `MINIMO` por encima. Sin `sentido` el esquema no deja construir el parámetro, porque un
       mínimo tratado como máximo da el veredicto **invertido** sin que nadie se entere. (T1.9)

    **Lo que este orden garantiza:** los pasos 1 a 5 solo pueden devolver `P`. Ninguno compara. La
    comparación es el paso 6 y es la única línea donde un `C` o un `NC` puede nacer.

    **Lo que NO entra acá:** el margen, la procedencia de un `None` (`ProcedenciaHecho`) y cualquier
    otra señal de diagnóstico. Este método decide; si leyera un campo de diagnóstico, el diagnóstico
    empezaría a decidir.
    """
    if not fuente_revisada:
        return CodigoVeredicto.PENDIENTE
    if parametro.estado is EstadoParametro.NO_APLICA:
        return CodigoVeredicto.NO_PROCEDE
    if indeterminados:
        return CodigoVeredicto.PENDIENTE  # no sabemos **cuál** límite rige
    if parametro.estado is EstadoParametro.DESCONOCIDO or limite is None:
        return CodigoVeredicto.PENDIENTE  # no sabemos cuál es el límite
    if valor_proyecto is None:
        return CodigoVeredicto.PENDIENTE  # no sabemos cuánto mide el proyecto
    if parametro.sentido is Sentido.MAXIMO:
        return (
            CodigoVeredicto.CUMPLE
            if valor_proyecto <= limite.valor
            else CodigoVeredicto.NO_CUMPLE
        )
    return (
        CodigoVeredicto.CUMPLE if valor_proyecto >= limite.valor else CodigoVeredicto.NO_CUMPLE
    )


def _decimal(entero: int | None) -> Decimal | None:
    return Decimal(entero) if entero is not None else None
