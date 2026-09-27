"""Excepciones de aplicación general: la OGUC modifica un valor que fija el PRC (T1.10b).

`corpus/oguc/2.6.5.yaml` declara, desde T0.6, que un Conjunto Armónico puede exceder el coeficiente
de constructibilidad. Y **ningún código lo leía**: el bloque `excepcion:` era texto en un YAML. El
corpus afirmaba algo que el motor no podía aplicar, lo que es peor que no tenerlo — parece cubierto.

## Por qué un `factor` y no un `valor`

La norma no dice "el `cus` es 6": dice *"podrán exceder hasta en un 50% el coeficiente de
constructibilidad **establecido por el Plan Regulador respectivo**"*. El `cus` de Ñuñoa no es el de
Las Condes, y la OGUC aplica a los dos. Un `Limite` con `valor` absoluto no puede expresarlo, y
expandirlo por zona duplicaría la regla nacional en cada ordenanza y rompería su trazabilidad.

## Por qué una entrada por hecho

`2.6.5` dice *"las letras a) **o** b)"*. Es una disyunción. Se modela con **una `Excepcion` por
hecho**: cada una concede su factor por separado y, entre las que apliquen, manda la más
restrictiva. Es exactamente el comportamiento de `_limite_vigente` para las excepciones de zona, así
que no hace falta un operador nuevo — y para un máximo, "la más restrictiva gana" es la dirección
segura.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from rasante.corpus.cargador import cargar_reglas
from rasante.corpus.esquema import ErrorEsquema, validar_corpus, validar_documento
from rasante.dominio import factibilidad
from rasante.dominio.modelos import (
    Cita,
    CodigoHallazgo,
    CodigoVeredicto,
    ErrorDominio,
    EstadoParametro,
    EstadoRevision,
    Limite,
    Parametro,
    Procedencia,
    Proyecto,
    Sentido,
    TipoLimite,
    Vigencia,
    Zona,
)
from rasante.dominio.motor import evaluar
from rasante.dominio.reglas import Derivacion, Excepcion, Hecho, Reglas

RAIZ = Path(__file__).resolve().parents[1]
REGLAS_REALES = cargar_reglas(RAIZ / "corpus")
CITA = Cita(norma_id="oguc", articulo="2.6.5", texto="Conjunto Armónico: excepción al cus")

CUS_EXPRESION = "superficie_edificada_m2 / superficie_predio_m2"


# --- helpers ---


def procedencia() -> Procedencia:
    return Procedencia(
        url_fuente="https://www.nunoa.cl/ordenanza.pdf",
        hash_fuente="sha256:" + "0" * 64,
        consolidado_por="Texto refundido, junio 2025",
        extraido="2026-09-26",
        revisado_por="Revisor de prueba",
        estado=EstadoRevision.REVISADO,
    )


def zona(*parametros: Parametro) -> Zona:
    return Zona(
        codigo="Z-4",
        nombre="Z-4",
        comuna="Ñuñoa",
        parametros={p.clave: p for p in parametros},
        vigencia=Vigencia(),
        procedencia=procedencia(),
    )


def parametro_cus(base: str | None, sentido: Sentido = Sentido.MAXIMO) -> Parametro:
    limites = (
        () if base is None else (Limite(TipoLimite.BASE, Decimal(base), "adimensional", CITA),)
    )
    return Parametro(
        id="cus",
        limites=limites,
        sentido=sentido,
        estado=EstadoParametro.APLICABLE,
        cita=CITA,
    )


def proyecto(predio: str, edificada: str) -> Proyecto:
    return Proyecto(
        superficie_predio_m2=Decimal(predio),
        numero_viviendas=1,
        superficie_edificada_m2=Decimal(edificada),
    )


def reglas(
    *excepciones: Excepcion, hechos: tuple[str, ...] = ()
) -> Reglas:
    """Un corpus hermético: una sola derivación y los hechos que hagan falta."""
    return Reglas(
        derivaciones=MappingProxyType(
            {"cus": Derivacion(parametro="cus", expresion=CUS_EXPRESION, cita=CITA)}
        ),
        hechos=MappingProxyType(
            {
                n: Hecho(nombre=n, expresion="superficie_predio_m2 >= 5000", cita=CITA)
                for n in hechos
            }
        ),
        excepciones=excepciones,
    )


def excepcion(hecho: str, factor: str, parametro: str = "cus") -> Excepcion:
    """Una excepción con **un** hecho. Para conjunciones, construye `Excepcion` a mano."""
    return Excepcion(
        parametro=parametro, hechos=frozenset({hecho}), factor=Decimal(factor), cita=CITA
    )


def veredicto(
    p: Proyecto, z: Zona, r: Reglas, externos: Mapping[str, bool | None]
) -> CodigoVeredicto:
    return next(v for v in evaluar(p, z, r, externos) if v.clave == "cus").codigo


def limite_aplicado(
    p: Proyecto, z: Zona, r: Reglas, externos: Mapping[str, bool | None]
) -> Decimal | None:
    return next(v for v in evaluar(p, z, r, externos) if v.clave == "cus").valor_norma


# --- 1. el tipo ---


def test_una_excepcion_necesita_factor_decimal() -> None:
    """D6: un `float` en cualquier valor normativo reintroduce el error binario."""
    with pytest.raises(ErrorDominio, match="Decimal"):
        Excepcion(
            parametro="cus",
            hechos=frozenset({"dimension_a"}),
            factor=1.5,  # type: ignore[arg-type]
            cita=CITA,
        )


def test_un_factor_no_positivo_no_se_puede_construir() -> None:
    """Un factor 0 anularía el parámetro; uno negativo lo invertiría."""
    with pytest.raises(ErrorDominio, match="mayor que cero"):
        excepcion("dimension_a", "0")
    with pytest.raises(ErrorDominio, match="mayor que cero"):
        excepcion("dimension_a", "-1.5")


def test_una_excepcion_necesita_cita() -> None:
    with pytest.raises(ErrorDominio, match="Cita"):
        Excepcion(
            parametro="cus",
            hechos=frozenset({"dimension_a"}),
            factor=Decimal("1.5"),
            cita="no soy cita",  # type: ignore[arg-type]
        )


def test_una_excepcion_necesita_parametro_y_hechos() -> None:
    with pytest.raises(ErrorDominio):
        Excepcion(parametro="", hechos=frozenset({"dimension_a"}), factor=Decimal("1.5"), cita=CITA)
    with pytest.raises(ErrorDominio, match="hechos"):
        Excepcion(parametro="cus", hechos=frozenset(), factor=Decimal("1.5"), cita=CITA)
    with pytest.raises(ErrorDominio, match="vacíos"):
        Excepcion(parametro="cus", hechos=frozenset({"  "}), factor=Decimal("1.5"), cita=CITA)


# --- 2. el motor la aplica ---


def test_sin_excepciones_rige_el_base() -> None:
    """El control: 5,0 de `cus` contra un base de 4 no cumple."""
    z = zona(parametro_cus("4"))
    assert veredicto(proyecto("1000", "5000"), z, reglas(), {}) is CodigoVeredicto.NO_CUMPLE


def test_el_factor_se_aplica_sobre_el_valor_que_fija_el_plan_regulador() -> None:
    """+50 % sobre 4 es 6. El valor absoluto no está en la OGUC: está en el PRC multiplicado."""
    z = zona(parametro_cus("4"))
    r = reglas(excepcion("dimension_a", "1.5"))
    assert limite_aplicado(proyecto("1000", "5000"), z, r, {"dimension_a": True}) == Decimal("6.0")


def test_con_el_hecho_cierto_la_excepcion_sustituye_al_base() -> None:
    z = zona(parametro_cus("4"))
    r = reglas(excepcion("dimension_a", "1.5"))
    assert veredicto(proyecto("1000", "5000"), z, r, {"dimension_a": True}) is (
        CodigoVeredicto.CUMPLE
    )


def test_con_el_hecho_falso_rige_el_base() -> None:
    z = zona(parametro_cus("4"))
    r = reglas(excepcion("dimension_a", "1.5"))
    assert veredicto(proyecto("1000", "5000"), z, r, {"dimension_a": False}) is (
        CodigoVeredicto.NO_CUMPLE
    )


def test_con_el_hecho_indeterminado_da_pendiente_y_no_el_limite_ampliado() -> None:
    """El test que sostiene todo: si no se sabe si es Conjunto Armónico, no se regala el +50 %."""
    z = zona(parametro_cus("4"))
    r = reglas(excepcion("dimension_a", "1.5"))
    assert veredicto(proyecto("1000", "5000"), z, r, {"dimension_a": None}) is (
        CodigoVeredicto.PENDIENTE
    )


def test_sin_el_hecho_externo_tampoco_se_asume_la_excepcion() -> None:
    z = zona(parametro_cus("4"))
    r = reglas(excepcion("dimension_a", "1.5"))
    assert veredicto(proyecto("1000", "5000"), z, r, {}) is CodigoVeredicto.PENDIENTE


def test_sin_base_no_se_puede_calcular_el_factor() -> None:
    """El factor multiplica un valor que no está: sin base no hay nada que ampliar.

    El hecho es cierto, así que la excepción aplica — pero su **valor** no se puede calcular. El
    parámetro queda pendiente, y no por la excepción: por su propia falta de base.
    """
    z = zona(
        Parametro(
            id="cus",
            limites=(
                Limite(
                    TipoLimite.EXCEPCION,
                    Decimal("9"),
                    "adimensional",
                    CITA,
                    frozenset({"dimension_local"}),
                ),
            ),
            sentido=Sentido.MAXIMO,
            estado=EstadoParametro.APLICABLE,
            cita=CITA,
        )
    )
    r = reglas(excepcion("dimension_a", "1.5"))
    externos = {"dimension_a": True, "dimension_local": False}
    assert veredicto(proyecto("1000", "5000"), z, r, externos) is CodigoVeredicto.PENDIENTE


def test_entre_dos_excepciones_que_aplican_manda_la_mas_restrictiva() -> None:
    """Un proyecto que cumple a) y c) recibe el 30 %, no el 50 %."""
    z = zona(parametro_cus("4"))
    r = reglas(excepcion("dimension_a", "1.5"), excepcion("dimension_c", "1.3"))
    # 5,5 de `cus`: entra en el 50 % (6) pero no en el 30 % (5,2).
    ambas = {"dimension_a": True, "dimension_c": True}
    assert limite_aplicado(proyecto("1000", "5500"), z, r, ambas) == Decimal("5.2")
    assert veredicto(proyecto("1000", "5500"), z, r, ambas) is CodigoVeredicto.NO_CUMPLE


def test_una_excepcion_no_toca_a_otro_parametro() -> None:
    """`2.6.5` habla del coeficiente de constructibilidad, no de la ocupación de suelo."""
    z = zona(parametro_cus("4"))
    r = reglas(excepcion("dimension_a", "1.5", parametro="cos"))
    assert veredicto(proyecto("1000", "5000"), z, r, {"dimension_a": True}) is (
        CodigoVeredicto.NO_CUMPLE
    )


def test_la_excepcion_de_la_zona_y_la_nacional_conviven() -> None:
    """La del PRC y la de la OGUC se evalúan juntas; gana la más restrictiva de las que apliquen."""
    z = zona(
        Parametro(
            id="cus",
            limites=(
                Limite(TipoLimite.BASE, Decimal("4"), "adimensional", CITA),
                Limite(
                    TipoLimite.EXCEPCION,
                    Decimal("5"),
                    "adimensional",
                    CITA,
                    frozenset({"dimension_local"}),
                ),
            ),
            sentido=Sentido.MAXIMO,
            estado=EstadoParametro.APLICABLE,
            cita=CITA,
        )
    )
    r = reglas(excepcion("dimension_a", "1.5"))
    aplican = {"dimension_local": True, "dimension_a": True}
    # min(5 de la zona, 6 de la OGUC) = 5: la ordenanza local es más estricta y prevalece.
    assert limite_aplicado(proyecto("1000", "5000"), z, r, aplican) == Decimal("5")


# --- 3. el esquema ---


def documento(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "norma_id": "oguc",
        "articulo": "2.6.5",
        "cita": "texto de la norma",
        "procedencia": {
            "url_fuente": "https://x.cl/o.pdf",
            "hash_fuente": "sha256:" + "0" * 64,
            "consolidado_por": "refundido",
            "extraido": "2026-09-26",
        },
    }
    base.update(extra)
    return base


def excepcion_yaml(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {"parametro": "cus", "hechos": ["dimension_a"], "factor": "1.5"}
    base.update(extra)
    return base


def test_el_esquema_exige_factor_de_texto() -> None:
    """`1.5` sin comillas es `float` en YAML y reintroduce el error binario (D6)."""
    with pytest.raises(ErrorEsquema, match="texto"):
        validar_documento(documento(excepciones=[excepcion_yaml(factor=1.5)]))


def test_el_esquema_rechaza_un_factor_no_positivo() -> None:
    with pytest.raises(ErrorEsquema, match="mayor que cero"):
        validar_documento(documento(excepciones=[excepcion_yaml(factor="0")]))


def test_el_esquema_rechaza_un_factor_que_no_es_numero() -> None:
    with pytest.raises(ErrorEsquema, match="factor"):
        validar_documento(documento(excepciones=[excepcion_yaml(factor="mucho")]))


def test_el_esquema_rechaza_un_parametro_desconocido() -> None:
    with pytest.raises(ErrorEsquema, match="parametro"):
        validar_documento(documento(excepciones=[excepcion_yaml(parametro="inventado")]))


def test_el_esquema_rechaza_una_excepcion_sin_hechos() -> None:
    with pytest.raises(ErrorEsquema, match="hechos"):
        validar_documento(documento(excepciones=[{"parametro": "cus", "factor": "1.5"}]))


def test_el_esquema_rechaza_excepciones_que_no_son_lista() -> None:
    with pytest.raises(ErrorEsquema, match="lista"):
        validar_documento(documento(excepciones=excepcion_yaml()))


def test_un_hecho_de_excepcion_que_nadie_resuelve_es_un_error(tmp_path: Path) -> None:
    """Si el hecho no existe, la excepción no aplicaría nunca y nadie se enteraría."""
    import yaml

    (tmp_path / "a.yaml").write_text(
        yaml.safe_dump(
            documento(excepciones=[excepcion_yaml(hechos=["dimension_z"])]), allow_unicode=True
        ),
        encoding="utf-8",
    )
    with pytest.raises(ErrorEsquema, match="dimension_z"):
        validar_corpus(tmp_path)


def test_un_hecho_preguntado_sirve_para_una_excepcion(tmp_path: Path) -> None:
    """Es el caso real: `2.6.5` depende de hechos que el corpus no calcula y hay que clasificar."""
    import yaml

    doc = documento(
        hechos_pendientes={"dimension_c": "exige el historial registral"},
        preguntas={
            "dimension_c": {
                "tipo": "noul",
                "instrucciones": "¿Es una fusión predial?",
                "cita": {"norma_id": "oguc", "articulo": "2.6.4"},
            }
        },
        excepciones=[excepcion_yaml(hechos=["dimension_c"], factor="1.3")],
    )
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    assert len(validar_corpus(tmp_path)) == 1


# --- 4. el corpus real ---


def test_el_corpus_real_carga_las_excepciones_de_2_6_5() -> None:
    """El bloque que llevaba cerrado desde T0.6, ahora sí llega al motor."""
    de_cus = sorted(
        (tuple(sorted(e.hechos)), str(e.factor))
        for e in REGLAS_REALES.excepciones
        if e.parametro == "cus"
    )
    assert de_cus == [
        (("conjunto_armonico", "dimension_a"), "1.5"),
        (("conjunto_armonico", "dimension_b"), "1.5"),
        (("conjunto_armonico", "dimension_c"), "1.3"),
    ]


def test_las_excepciones_del_corpus_real_citan_el_articulo_2_6_5() -> None:
    for e in REGLAS_REALES.excepciones:
        assert e.cita.norma_id == "oguc"
        assert e.cita.articulo == "2.6.5"
        assert e.cita.texto.strip()


def test_la_excepcion_del_50_por_ciento_cita_las_letras_a_y_b() -> None:
    """La cita tiene que respaldar el hecho que activa la excepción, no solo el artículo."""
    del_50 = [e for e in REGLAS_REALES.excepciones if e.factor == Decimal("1.5")]
    assert len(del_50) == 2
    for e in del_50:
        assert "letras a) o b)" in e.cita.texto


def test_la_excepcion_del_30_por_ciento_cita_la_letra_c() -> None:
    del_30 = [e for e in REGLAS_REALES.excepciones if e.factor == Decimal("1.3")]
    assert len(del_30) == 1
    assert "letra c)" in del_30[0].cita.texto
    assert "30%" in del_30[0].cita.texto


SIN_ARMONICO: dict[str, bool | None] = {"dimension_b": False, "dimension_c": False}


def test_un_proyecto_que_no_se_acoge_no_recibe_la_ampliacion() -> None:
    """Acogerse es una facultad del titular, no una consecuencia del tamaño del predio.

    Es el test que evita que el motor regale un +50 % de `cus` a cualquier terreno de más de
    5.000 m² — y el que mantiene útiles los veredictos de `cus` en el resto del proyecto.
    """
    z = zona_real("4")
    assert veredicto_real(proyecto_real("4.8", "6000"), z, SIN_ARMONICO) is (
        CodigoVeredicto.NO_CUMPLE
    )


def test_acogido_y_con_dimension_suficiente_la_excepcion_amplia() -> None:
    """`dimension_a` la **calcula el corpus** (6.000 m² contra una predial mínima de 1.000)."""
    z = zona_real("4")
    p = proyecto_real("4.8", "6000", acoge=True)
    assert veredicto_real(p, z, SIN_ARMONICO) is CodigoVeredicto.CUMPLE


def test_el_conjunto_armonico_real_por_manzana_tambien_amplia() -> None:
    """La letra b) es la otra mitad de la disyunción del 50 %."""
    z = zona_real("4")
    manzana = {"dimension_b": True, "dimension_c": False}
    assert veredicto_real(proyecto_real("4.8", "1000", acoge=True), z, manzana) is (
        CodigoVeredicto.CUMPLE
    )


def test_la_letra_a_real_da_el_50_por_ciento() -> None:
    """El +50 % sobre un base de 4 llega justo a 6,0, y el proyecto tiene exactamente 6,0."""
    z = zona_real("4")
    assert veredicto_real(proyecto_real("6", "6000", acoge=True), z, SIN_ARMONICO) is (
        CodigoVeredicto.CUMPLE
    )


def test_la_letra_c_real_da_30_por_ciento_y_no_50() -> None:
    """6,0 entra en el 50 % (6,0) pero no en el 30 % (5,2)."""
    z = zona_real("4")
    fusion = {"dimension_b": False, "dimension_c": True}
    assert veredicto_real(proyecto_real("6", "1000", acoge=True), z, fusion) is (
        CodigoVeredicto.NO_CUMPLE
    )


def test_cuando_aplican_la_letra_a_y_la_letra_c_gana_la_mas_restrictiva() -> None:
    z = zona_real("4")
    ambas = {"dimension_b": False, "dimension_c": True}
    # min(6,0 del 50 %, 5,2 del 30 %) = 5,2: el proyecto no entra.
    assert veredicto_real(proyecto_real("6", "6000", acoge=True), z, ambas) is (
        CodigoVeredicto.NO_CUMPLE
    )


def test_acogido_pero_sin_clasificar_los_hechos_el_cus_queda_pendiente() -> None:
    """El hallazgo que cambia el producto.

    Antes de cargar `2.6.5`, el motor daba `C` o `NC` sobre `cus` **ignorando en silencio** que el
    proyecto podía acogerse al +50 % o al +30 %. Ahora, cuando se acoge, dice `P` hasta saber si es
    manzana o fusión: menos respuesta y más verdad.
    """
    z = zona_real("4")
    assert veredicto_real(proyecto_real("4.8", "1000", acoge=True), z, {}) is (
        CodigoVeredicto.PENDIENTE
    )


def test_el_hallazgo_nombra_los_hechos_que_faltan_para_clasificar_el_cus() -> None:
    """Un `P` sin motivo no le sirve al revisor: tiene que decirle **qué** dato ir a buscar."""
    p = proyecto_real("4.8", "1000", acoge=True)
    hallazgos = factibilidad.verificar(p, zona_real("4"), REGLAS_REALES)
    faltantes = {
        nombre
        for h in hallazgos
        if h.codigo is CodigoHallazgo.CLASIFICACION_INDETERMINADA
        for nombre in h.parametros
    }
    assert {"cus", "dimension_b", "dimension_c"} <= faltantes


def test_un_hecho_falso_decide_antes_que_uno_desconocido() -> None:
    """`X and False = False`: un hecho descartado no se vuelve duda porque otro sea desconocido.

    Antes esto daba `P`: el motor reportaba una duda que ya no existía.
    """
    z = zona(parametro_cus("4"))
    r = reglas(
        Excepcion(
            parametro="cus",
            hechos=frozenset({"dimension_a", "dimension_z"}),
            factor=Decimal("1.5"),
            cita=CITA,
        )
    )
    descartado = {"dimension_a": False, "dimension_z": None}
    assert veredicto(proyecto("1000", "5000"), z, r, descartado) is CodigoVeredicto.NO_CUMPLE
    en_duda = {"dimension_a": True, "dimension_z": None}
    assert veredicto(proyecto("1000", "5000"), z, r, en_duda) is CodigoVeredicto.PENDIENTE


# --- utilidades del corpus real ---


def zona_real(cus_base: str) -> Zona:
    """Una zona con `cus` y la superficie predial mínima que necesita el hecho `dimension_a`."""

    def adimensional(clave: str, valor: str, sentido: Sentido) -> Parametro:
        return Parametro(
            id=clave,
            limites=(Limite(TipoLimite.BASE, Decimal(valor), "adimensional", CITA),),
            sentido=sentido,
            estado=EstadoParametro.APLICABLE,
            cita=CITA,
        )

    return zona(
        adimensional("cus", cus_base, Sentido.MAXIMO),
        adimensional("superficie_predial_minima", "1000", Sentido.MINIMO),
    )


def proyecto_real(cus: str, predio: str, acoge: bool = False) -> Proyecto:
    """El `cus` que el corpus deriva de un proyecto es `superficie_edificada_m2 / predio`."""
    return Proyecto(
        superficie_predio_m2=Decimal(predio),
        numero_viviendas=1,
        superficie_edificada_m2=Decimal(cus) * Decimal(predio),
        acoge_conjunto_armonico=acoge,
    )


def veredicto_real(p: Proyecto, z: Zona, externos: Mapping[str, bool | None]) -> CodigoVeredicto:
    return next(v for v in evaluar(p, z, REGLAS_REALES, externos) if v.clave == "cus").codigo


# --- 5. el corpus real ---


def test_el_corpus_real_declara_una_excepcion_por_cada_hecho_que_la_activa() -> None:
    """`2.6.5` es una disyunción ("letras a) o b)") más una letra c): tres hechos, tres entradas.

    Y las tres exigen **acogerse**: cumplir la condición de dimensión no basta.
    """
    dimensiones = {
        h for e in REGLAS_REALES.excepciones for h in e.hechos if h != "conjunto_armonico"
    }
    assert dimensiones == {"dimension_a", "dimension_b", "dimension_c"}
    assert all("conjunto_armonico" in e.hechos for e in REGLAS_REALES.excepciones)
    assert all(e.parametro == "cus" for e in REGLAS_REALES.excepciones)
