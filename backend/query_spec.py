"""Spec estructurada de consulta (Fase 4).

El router (o el LLM) llena estos slots; `sql_builder` los traduce a SQL.
Extracción determinista basada en léxico + resolvers semánticos.
"""
import re
import unicodedata

import semantic_loader
import terminos_sesnsp


OPERACIONES = {
    "detalle", "conteo", "promedio", "maximo", "minimo", "suma",
    "top_n", "por_anio", "por_entidad", "por_tipo_violencia",
    "anios_disponibles", "comparar",
}

METRICA_A_OPERACION = {
    "detalle": "detalle",
    "conteo": "conteo",
    "promedio": "promedio",
    "maximo": "maximo",
    "minimo": "minimo",
    "suma": "suma",
    "top_n": "top_n",
}


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def extraer_anio(texto):
    n = normalizar(texto)
    coincidencias = re.findall(r"\b(19|20)\d{2}\b", n)
    if not coincidencias:
        return None
    anios = [int(a) for a in re.findall(r"\b((?:19|20)\d{2})\b", n)]
    return anios[0] if anios else None


def extraer_limite(texto):
    n = normalizar(texto)
    m = re.search(r"\btop\s+(\d+)\b", n)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(?:los|las)?\s*(\d+)\s+(?:mas|valores|indicadores|resultados|publicaciones)\b", n)
    if m:
        return int(m.group(1))
    return None


MARCADORES_SEGUIMIENTO = [
    "cada anio", "por anio", "cada ano", "por ano", "y en", "tambien",
    "de esos", "de esas", "ese ", "esa ", "el mismo", "la misma",
    "ahora", "entonces", "y el", "y la", "de cada", "por cada",
]


def _es_seguimiento(texto, contexto):
    if not contexto or not contexto.get("pregunta"):
        return False
    return any(m in texto for m in MARCADORES_SEGUIMIENTO)


def construir_spec(pregunta, señales=None, contexto=None):
    n = normalizar(pregunta)
    señales = señales or {}
    previo = (contexto or {}).get("spec") or {}
    seguimiento = _es_seguimiento(n, contexto)

    metrica = señales.get("metrica") or semantic_loader.resolver_metrica(pregunta)
    if metrica is None and seguimiento:
        metrica = previo.get("metrica")
    operacion = METRICA_A_OPERACION.get(metrica or "detalle", "detalle")

    # Agrupaciones
    grupo = []
    if any(g in n for g in ["por anio", "cada anio", "por ano", "cada ano", "por cada anio"]):
        grupo.append("anio")
    if any(g in n for g in ["por entidad", "por estado"]):
        grupo.append("entidad")

    if "anio" in grupo:
        operacion = "por_anio"
    elif "entidad" in grupo:
        operacion = "por_entidad"

    # Orden
    orden = "desc"
    if any(t in n for t in ["mas bajo", "menor", "minimo", "los menores"]):
        orden = "asc"

    limite = extraer_limite(pregunta)
    if operacion == "top_n" and limite is None:
        limite = 5
    if limite is None:
        limite = 100

    fuente = señales.get("fuente")
    if not fuente and seguimiento:
        fuente = previo.get("fuente")

    entidad_nombre = None
    entidad_id = señales.get("entidad_id")
    if entidad_id is None:
        entidad_id = semantic_loader.resolver_entidad(pregunta)
    if entidad_id is None and seguimiento:
        entidad_id = previo.get("entidad_id")
    if entidad_id is not None:
        entidad_nombre = _nombre_entidad(entidad_id)

    anio = extraer_anio(pregunta)
    if anio is None and seguimiento:
        anio = previo.get("anio")

    return {
        "operacion": operacion,
        "metrica": metrica or "detalle",
        "fuente": fuente,
        "entidad": entidad_nombre,
        "entidad_id": entidad_id,
        "anio": anio,
        "grupo": grupo,
        "orden": orden,
        "limite": limite,
        "indicador": None,
    }


def _nombre_entidad(id_entidad):
    return semantic_loader.nombre_entidad(id_entidad)


def validar_spec(spec):
    if not isinstance(spec, dict):
        return False, "La spec no es un diccionario."
    if spec.get("operacion") not in OPERACIONES:
        return False, "Operación no permitida."
    if not isinstance(spec.get("limite", 100), int) or not (1 <= spec.get("limite", 100) <= 500):
        return False, "Límite fuera de rango."
    if spec.get("anio") is not None and not isinstance(spec["anio"], int):
        return False, "Año inválido."
    return True, None


def _metrica_de_operacion(operacion):
    if operacion in ("conteo", "promedio", "maximo", "minimo", "suma", "top_n"):
        return operacion
    return "detalle"


def desde_interpretacion(interp, contexto=None, pregunta=None):
    """Construye una spec a partir del JSON del intérprete, heredando contexto."""
    operacion = interp.get("operacion") or "detalle"
    previo = (contexto or {}).get("spec") or {}

    fuente = interp.get("fuente")
    entidad = interp.get("entidad")
    anio = interp.get("anio")
    tipo_violencia = interp.get("tipo_violencia")

    if interp.get("intencion") == "seguir" or operacion in (
        "anios_disponibles", "por_anio",
    ):
        fuente = fuente or previo.get("fuente")
        entidad = entidad or previo.get("entidad")
        anio = anio if anio is not None else previo.get("anio")
        tipo_violencia = tipo_violencia or previo.get("tipo_violencia")

    # "dividir por estado": se agrupa por TODAS las entidades, no se hereda la entidad.
    if operacion == "por_entidad":
        fuente = fuente or previo.get("fuente")
        tipo_violencia = tipo_violencia or previo.get("tipo_violencia")

    if not tipo_violencia and previo.get("tipo_violencia"):
        if not (pregunta and semantic_loader.resolver_tipo_violencia(pregunta)):
            tipo_violencia = previo["tipo_violencia"]

    entidad_id = None
    if entidad:
        entidad_id = semantic_loader.resolver_entidad(entidad)

    # "el estado/entidad con más violencia" => ranking por entidad, no un valor suelto.
    if operacion in ("maximo", "top_n", "detalle") and not entidad and not fuente and pregunta:
        p = normalizar(pregunta)
        if re.search(r"\bestados?\b|\bentidades?\b", p) and re.search(
            r"\bmas\b|\bmayor\b|mayores|alto|predomina|mayor indice", p
        ):
            operacion = "por_entidad"

    # Un año fijo con "por año" es contradictorio: es un ranking de un año.
    if operacion == "por_anio" and anio is not None and not entidad:
        operacion = "por_entidad"

    # "gráfica de X" -> usar una operación que produzca varios valores
    if (
        pregunta
        and "grafic" in normalizar(pregunta)
        and operacion in ("detalle", "promedio", "maximo", "minimo", "por_anio")
        and not entidad
    ):
        operacion = "por_entidad"

    # Indicador SESNSP por término (feminicidio, 911, etc.)
    id_indicador = interp.get("_id_indicador")
    if not id_indicador and not interp.get("indicador") and pregunta:
        id_indicador = terminos_sesnsp.indicador_id(pregunta)

    return {
        "operacion": operacion,
        "metrica": _metrica_de_operacion(operacion),
        "fuente": fuente,
        "entidad": entidad,
        "entidad_id": entidad_id,
        "entidad_b": interp.get("entidad_b"),
        "anio": anio,
        "grupo": interp.get("grupo") or [],
        "orden": "desc",
        "limite": 100,
        "indicador": interp.get("indicador"),
        "tipo_violencia": tipo_violencia,
        "filtro_texto": interp.get("filtro_texto"),
        "_id_indicador": id_indicador,
    }
