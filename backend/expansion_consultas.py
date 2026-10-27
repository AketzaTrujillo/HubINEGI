"""Expansión de siglas y sinónimos para la recuperación v2.

La expansión se aplica solo cuando la consulta contiene la sigla o el término.
Así se evita contaminar consultas que ya son claras.
"""
import re
import unicodedata

ACRONIMOS = {
    "cjm": "centros de justicia para las mujeres",
    "banavim": "banco nacional de datos e informacion sobre casos de violencia contra las mujeres",
    "sesnsp": "secretariado ejecutivo del sistema nacional de seguridad publica",
    "conavim": "comision nacional para prevenir y erradicar la violencia contra las mujeres",
    "avgm": "alerta de violencia de genero contra las mujeres",
    "paimef": "programa de apoyo a las instancias de mujeres en las entidades federativas",
    "lgamvlv": "ley general de acceso de las mujeres a una vida libre de violencia",
    "inmujeres": "instituto nacional de las mujeres",
    "endireh": "encuesta nacional sobre la dinamica de las relaciones en los hogares",
    "uep": "unidad especializada de la policia",
    "tsj": "tribunal superior de justicia",
    "mp": "ministerio publico",
    "cami": "casa de la mujer indigena",
    "c4": "centro de control comando computo y comunicaciones",
}

SINONIMOS = {
    "refugio": [
        "albergue",
        "casa de emergencia",
        "espacio de refugio especializado",
    ],
    "denuncia": ["denunciar", "carpeta de investigacion", "querella"],
    "orden de proteccion": ["medidas de proteccion", "ordenes de proteccion"],
    "violencia economica": ["control economico", "violencia patrimonial"],
    "violencia psicologica": ["violencia emocional", "maltrato psicologico"],
    "ayuda legal": ["asesoria juridica", "representacion legal"],
    "trabajo social": ["trabajadora social"],
    "ciudad de mexico": ["cdmx"],
    "estado de mexico": ["edomex"],
}

# Expansiones por intención: frases coloquiales que no comparten términos
# con el vocabulario institucional del corpus.
INTENCIONES = [
    (
        ("no tengo dinero", "no tengo a donde ir", "no se a donde ir",
         "no tengo donde ir", "ni a donde ir"),
        ["refugio", "albergue", "casa de emergencia"],
    ),
    (
        ("me golpea", "me pega", "me agrede", "violencia fisica"),
        ["denuncia", "orden de proteccion", "refugio"],
    ),
    (
        ("me da miedo denunciar", "miedo denunciar"),
        ["acompanamiento", "asesoria juridica", "denuncia"],
    ),
    (
        ("mi vecino", "mi vecina", "vecino golpea", "vecina golpea"),
        ["911", "denuncia"],
    ),
    (
        ("me controla el dinero", "controla el dinero", "no me da dinero"),
        ["violencia economica", "violencia patrimonial"],
    ),
]

PALABRAS_INICIALES = {
    "que", "cual", "cuales", "como", "cuanto", "cuanta", "cuantos",
    "cuantas", "quien", "quienes", "donde", "cuando", "porque",
    "significa", "significan", "es", "son", "un", "una", "unos",
    "unas", "el", "la", "los", "las", "de", "del", "en", "para",
    "por", "con", "sobre",
}


def frase_consulta(texto):
    """Extrae la parte útil de la pregunta para buscar la frase exacta."""
    tokens = normalizar(texto).split()
    while tokens and tokens[0] in PALABRAS_INICIALES:
        tokens.pop(0)
    while tokens and tokens[-1] in {"me", "pueden", "ayudar", "hacer", "hay"}:
        tokens.pop()
    return " ".join(tokens)


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9ñ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def expandir(texto):
    """Devuelve una lista de expansiones aplicables a la consulta."""
    normalizado = normalizar(texto)
    if not normalizado:
        return []

    expansiones = []
    for sigla, expansion in ACRONIMOS.items():
        if re.search(rf"\b{re.escape(normalizar(sigla))}\b", normalizado):
            expansiones.append(expansion)

    for termino, alternativas in SINONIMOS.items():
        if normalizar(termino) in normalizado:
            expansiones.extend(alternativas)

    for disparadores, alternativas in INTENCIONES:
        if any(normalizar(disparador) in normalizado for disparador in disparadores):
            expansiones.extend(alternativas)

    # Deduplicar conservando orden.
    vistos = set()
    salida = []
    for expansion in expansiones:
        if expansion in vistos:
            continue
        vistos.add(expansion)
        salida.append(expansion)
    return salida


def texto_expandido(texto):
    expansiones = expandir(texto)
    if not expansiones:
        return texto
    return f"{texto} {' '.join(expansiones)}"
