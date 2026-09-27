"""Modelos del dominio. Capa L1, **módulo puro**.

Restricción D2 (`doc/03-DISENO.md` §1): este paquete solo puede importar stdlib. Lo vigila
`tests/test_arquitectura.py`. La geometría, el YAML y la red viven en `rasante.geo` y
`rasante.corpus`, nunca acá.

Tres invariantes que sostienen el proyecto:

1. **Sin cita no hay veredicto.** Un veredicto sin respaldo normativo es un error de construcción,
   no un dato incompleto.
2. **Decimal, nunca float** (D6). Un float reintroduce el error binario en un informe que alguien
   firma bajo responsabilidad civil y penal.
3. **La clave de parámetro es compuesta** (`cos.primer_piso`). Ver `Parametro.clave`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from .vocabulario import CONDICIONES


class ErrorDominio(ValueError):
    """Se intentó construir un modelo violando un invariante del dominio."""


class EstadoParametro(StrEnum):
    """Si la norma fija un valor para este parámetro en esta zona."""

    APLICABLE = "aplicable"
    NO_APLICA = "no_aplica"
    DESCONOCIDO = "desconocido"


class EstadoRevision(StrEnum):
    """Cuánta confianza humana hay depositada en una norma del corpus."""

    BORRADOR = "borrador"
    REVISADO = "revisado"
    VALIDADO = "validado"


class CodigoVeredicto(StrEnum):
    """Los cinco códigos de la leyenda oficial de la Circular DDU 514.

    El valor es el código literal que va en el Formato Tipo; el nombre es para leerlo en código.
    Los textos viven en `LEYENDA`, que un test contrasta contra `corpus/ddu/514.yaml`.
    """

    CUMPLE = "C"
    NO_CUMPLE = "NC"
    PENDIENTE = "P"
    NO_PROCEDE = "NP"
    PLAN_REGULADOR = "PR"

    @property
    def texto(self) -> str:
        """Texto oficial del código, según la leyenda de la DDU 514."""
        return LEYENDA[self]


LEYENDA: Mapping[CodigoVeredicto, str] = MappingProxyType(
    {
        CodigoVeredicto.CUMPLE: "Cumple con exigencias normativas",
        CodigoVeredicto.NO_CUMPLE: "No cumple con exigencia normativa",
        CodigoVeredicto.PENDIENTE: "Pendiente",
        CodigoVeredicto.NO_PROCEDE: "No procede",
        CodigoVeredicto.PLAN_REGULADOR: "Plan Regulador",
    }
)


def clave_compuesta(identificador: str, calificador: str | None = None) -> str:
    """Clave de un parámetro dentro de una zona: `id` o `id.calificador`.

    Es la única definición de la clave compuesta. `Parametro`, `Veredicto` y el cargador del
    corpus (T1.6) tienen que coincidir en esto o las reglas se pisan.
    """
    return f"{identificador}.{calificador}" if calificador else identificador


@dataclass(frozen=True, slots=True)
class Cita:
    """Respaldo normativo de una regla o de un veredicto.

    `norma_id` distingue la fuente: `"oguc"` para la regla nacional, `"prc:nunoa"` para el valor
    municipal. Un veredicto de altura cita las dos (D13).
    """

    norma_id: str
    articulo: str
    texto: str

    def __post_init__(self) -> None:
        if not self.norma_id.strip():
            raise ErrorDominio("una Cita necesita 'norma_id' no vacío")
        if not self.articulo.strip():
            raise ErrorDominio("una Cita necesita 'articulo' no vacío")
        if not self.texto.strip():
            raise ErrorDominio("una Cita necesita 'texto' no vacío")


class TipoLimite(StrEnum):
    """Cómo se relaciona un límite con los demás del mismo parámetro."""

    BASE = "base"
    """El valor por defecto. No lleva condiciones: un base con condición no es un base."""

    EXCEPCION = "excepcion"
    """Cuando sus hechos se cumplen, **sustituye** al base.

    Sustituye, no se suma. Si ligaran los dos y ganara el más restrictivo, la excepción del
    Conjunto Armónico de la OGUC `2.6.5` —que *amplía* el `cus`— nunca podría aplicarse.
    """


@dataclass(frozen=True, slots=True)
class Limite:
    """Un valor normado para un parámetro, con las condiciones que lo activan.

    `cuando` son nombres de **hechos** que el corpus define como expresiones. Una excepción sin
    `cuando` aplicaría siempre y anularía al base; por eso no se puede construir.
    """

    tipo: TipoLimite
    valor: Decimal
    unidad: str
    cita: Cita
    cuando: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.valor, Decimal):
            tipo = type(self.valor).__name__
            raise ErrorDominio(f"el valor de un Limite debe ser Decimal, no {tipo}")
        if not isinstance(self.cita, Cita):
            raise ErrorDominio("un Limite necesita una Cita")
        if not self.unidad.strip():
            raise ErrorDominio("un Limite necesita 'unidad'")
        if self.tipo is TipoLimite.BASE and self.cuando:
            raise ErrorDominio("un límite 'base' no lleva 'cuando'")
        if self.tipo is TipoLimite.EXCEPCION and not self.cuando:
            raise ErrorDominio(
                "un límite 'excepcion' necesita 'cuando': sin condiciones aplicaría siempre y "
                "anularía al base"
            )


@dataclass(frozen=True, slots=True)
class Parametro:
    """Un parámetro urbanístico normado para una zona, con **todos** sus límites.

    `calificador` no es decorativo: sin él dos reglas distintas colisionan en la misma clave.

    - `cos` distingue `primer_piso` (`0,6`) de `pisos_superiores` (`0,4`).
    - `densidad` distingue `bruta` de `neta`.

    `limites` vacío con `estado=DESCONOCIDO` es legítimo y **debe propagarse como `P` pendiente,
    nunca como cumple**. Un dato que no tenemos no puede convertirse en un aprobado.
    """

    id: str
    limites: tuple[Limite, ...]
    estado: EstadoParametro
    cita: Cita
    calificador: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ErrorDominio("un Parametro necesita 'id' no vacío")
        if "." in self.id:
            raise ErrorDominio(
                f"'{self.id}': el 'id' no lleva calificador. Usa id y calificador por separado, "
                "no la clave compuesta: si no, la clave sale duplicada ('densidad.bruta.bruta')"
            )
        if not isinstance(self.cita, Cita):
            raise ErrorDominio(f"'{self.id}': un Parametro necesita una Cita")
        if self.estado is EstadoParametro.APLICABLE and not self.limites:
            raise ErrorDominio(f"'{self.id}': un Parametro aplicable necesita al menos un límite")
        if len({limite.tipo for limite in self.limites if limite.tipo is TipoLimite.BASE}) > 1:
            raise ErrorDominio(f"'{self.id}': no puede tener dos límites 'base'")

    @property
    def clave(self) -> str:
        """Clave compuesta del parámetro dentro de una zona: `id` o `id.calificador`."""
        return clave_compuesta(self.id, self.calificador)

    @property
    def base(self) -> Limite | None:
        """El límite por defecto, si lo hay."""
        return next((x for x in self.limites if x.tipo is TipoLimite.BASE), None)

    @property
    def excepciones(self) -> tuple[Limite, ...]:
        """Los límites que sustituyen al base cuando sus hechos se cumplen."""
        return tuple(x for x in self.limites if x.tipo is TipoLimite.EXCEPCION)


@dataclass(frozen=True, slots=True)
class Vigencia:
    """Intervalo en que una norma está en vigor.

    **No se deriva de `P_DO`** (D12): ese campo trae la publicación original del instrumento, no
    la del texto consolidado. Hay que reconstruir la historia de enmiendas desde la ordenanza.
    """

    desde: date | None = None
    hasta: date | None = None
    nota: str | None = None

    def __post_init__(self) -> None:
        if self.desde is not None and self.hasta is not None and self.hasta < self.desde:
            raise ErrorDominio("'hasta' no puede ser anterior a 'desde'")


@dataclass(frozen=True, slots=True)
class Procedencia:
    """Trazabilidad de una norma del corpus. Sin esto, la regla no entra (invariante 6)."""

    url_fuente: str
    hash_fuente: str
    consolidado_por: str
    extraido: str
    extraido_por: str | None = None
    revisado_por: str | None = None
    estado: EstadoRevision = EstadoRevision.BORRADOR

    def __post_init__(self) -> None:
        if not self.url_fuente.strip():
            raise ErrorDominio("Procedencia necesita 'url_fuente' no vacía")
        if not self.hash_fuente.strip():
            raise ErrorDominio("Procedencia necesita 'hash_fuente' no vacío")
        if not self.consolidado_por.strip():
            raise ErrorDominio("Procedencia necesita 'consolidado_por' no vacío")
        if not self.extraido.strip():
            raise ErrorDominio("Procedencia necesita 'extraido' no vacío")


@dataclass(frozen=True, slots=True)
class Zona:
    """Una zona del plan regulador, con los parámetros que le fija la ordenanza.

    `parametros` se indexa por **clave compuesta** (`Parametro.clave`). Una clave por `id`
    produciría claves duplicadas en el YAML y el parser descartaría una en silencio, perdiendo una
    regla. La construcción lo verifica.
    """

    codigo: str
    nombre: str
    comuna: str
    parametros: Mapping[str, Parametro]
    vigencia: Vigencia
    procedencia: Procedencia

    def __post_init__(self) -> None:
        for clave, parametro in self.parametros.items():
            if clave != parametro.clave:
                raise ErrorDominio(
                    f"en {self.comuna}/{self.codigo}: la clave '{clave}' no coincide con la del "
                    f"parámetro '{parametro.clave}'. Usa la clave compuesta."
                )

    def parametro(self, clave: str) -> Parametro | None:
        """El parámetro con esa clave compuesta, o `None` si la zona no lo fija."""
        return self.parametros.get(clave)


@dataclass(frozen=True, slots=True)
class Proyecto:
    """Datos declarados del proyecto que se evalúa.

    Con `densidad` en alcance (A3) deja de ser un placeholder: la densidad es una razón derivada
    (`numero_viviendas / superficie_predio_ha`), así que el motor necesita estos campos de verdad.
    """

    superficie_predio_m2: Decimal
    numero_viviendas: int
    superficie_edificada_m2: Decimal | None = None
    superficie_primer_piso_m2: Decimal | None = None
    altura_m: Decimal | None = None
    numero_pisos: int | None = None
    clasificaciones: frozenset[str] = frozenset()
    """Atributos que activan límites condicionales (`conjunto_armonico`, `agrupamiento_*`)."""

    def __post_init__(self) -> None:
        if not isinstance(self.superficie_predio_m2, Decimal):
            raise ErrorDominio("'superficie_predio_m2' debe ser Decimal")
        if self.superficie_predio_m2 <= 0:
            raise ErrorDominio("'superficie_predio_m2' debe ser mayor que cero")
        if self.numero_viviendas < 0:
            raise ErrorDominio("'numero_viviendas' no puede ser negativo")
        opcionales = ("superficie_edificada_m2", "superficie_primer_piso_m2", "altura_m")
        for nombre in opcionales:
            if getattr(self, nombre) is not None and not isinstance(getattr(self, nombre), Decimal):
                raise ErrorDominio(f"'{nombre}' debe ser Decimal o None")
        if self.numero_pisos is not None and self.numero_pisos < 0:
            raise ErrorDominio("'numero_pisos' no puede ser negativo")
        desconocidas = sorted(self.clasificaciones - CONDICIONES)
        if desconocidas:
            raise ErrorDominio(f"clasificaciones fuera del vocabulario: {desconocidas}")


@dataclass(frozen=True, slots=True)
class Veredicto:
    """El resultado de comparar el proyecto contra la norma, para un parámetro.

    **`cita` es obligatoria y no puede ser `None`.** Es lo que impide fabricar veredictos sin
    respaldo normativo: un `(NC)` es un acto profesional firmado, no una salida de modelo.
    """

    parametro_id: str
    codigo: CodigoVeredicto
    cita: Cita
    valor_norma: Decimal | None = None
    valor_proyecto: Decimal | None = None
    calificador: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.cita, Cita):
            raise ErrorDominio(
                f"el veredicto de '{self.parametro_id}' no tiene 'cita': un veredicto sin respaldo "
                "normativo no se puede construir"
            )
        if self.valor_norma is not None and not isinstance(self.valor_norma, Decimal):
            raise ErrorDominio("'valor_norma' debe ser Decimal o None")
        if self.valor_proyecto is not None and not isinstance(self.valor_proyecto, Decimal):
            raise ErrorDominio("'valor_proyecto' debe ser Decimal o None")

    @property
    def clave(self) -> str:
        """Clave compuesta del parámetro al que se refiere, igual que `Parametro.clave`."""
        return clave_compuesta(self.parametro_id, self.calificador)


class CodigoHallazgo(StrEnum):
    """Tipos de hallazgo del verificador de factibilidad (D15).

    Un `Hallazgo` **no** es un `Veredicto`: un veredicto es de un parámetro y va en el Formato Tipo;
    un acoplamiento geométrico involucra varios y se rinde por otro camino.
    """

    PROYECTO_IMPOSIBLE = "proyecto_imposible"
    """El proyecto no se puede construir: no cabe en su propia huella y número de pisos."""

    CUS_INALCANZABLE = "cus_inalcanzable"
    """El conjunto normativo es internamente inalcanzable: ningún proyecto podría cumplirlo."""

    CLASIFICACION_INDETERMINADA = "clasificacion_indeterminada"
    """No hay datos para saber qué límite rige. Se da `P`; **jamás** se asume el más permisivo."""


class Severidad(StrEnum):
    """Qué hacer con un hallazgo."""

    BLOQUEANTE = "bloqueante"
    """El proyecto no existe: hay que corregirlo antes de seguir."""

    ADVERTENCIA = "advertencia"
    """Puede ser un error del corpus o una particularidad real. El revisor decide."""


@dataclass(frozen=True, slots=True)
class Hallazgo:
    """Un problema que no es de un parámetro suelto, sino de su **combinación**.

    Como el `Veredicto`, exige `cita`: un hallazgo sin respaldo normativo es una opinión.
    """

    codigo: CodigoHallazgo
    severidad: Severidad
    mensaje: str
    cita: Cita
    parametros: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.mensaje.strip():
            raise ErrorDominio("un Hallazgo necesita 'mensaje'")
        if not isinstance(self.cita, Cita):
            raise ErrorDominio(
                f"el hallazgo '{self.codigo}' no tiene 'cita': un hallazgo sin respaldo normativo "
                "no se puede construir"
            )
