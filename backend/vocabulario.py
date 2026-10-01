"""Vocabulario difuso para el intérprete (Fase 9).

En vez de exigir la palabra exacta, compara de forma borrosa (tolerante a
errores de escritura) el texto del usuario contra el vocabulario de conceptos.
Devuelve una PISTA que se le da al LLM; el LLM decide, pero con ayuda.
"""
import difflib
import re
import unicodedata


VOCABULARIO = {
    "tipos_violencia": [
        "tipos de violencia", "tipo de violencia", "clases de violencia",
        "tipos de violencias", "violencias",
    ],
    "fuentes": ["fuentes", "fuente de datos", "origen de los datos"],
    "entidades": ["entidades", "estados", "entidades federativas"],
    "indicadores": ["indicadores", "indicador", "metricas"],
    "unidades": ["unidades", "unidad de medida"],
}

# Palabras clave que ayudan a decidir (con tolerancia a errores)
CLAVES = {
    "tipos_violencia": ["violencia", "violencias", "tipo", "tipos", "clase", "clases"],
    "fuentes": ["fuente", "fuentes"],
    "entidades": ["entidad", "entidades", "estado", "estados"],
    "indicadores": ["indicador", "indicadores"],
    "unidades": ["unidad", "unidades"],
}


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _parecido(a, b, corte=0.8):
    if len(b) < 4:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= corte


def pista(texto):
    """Devuelve el recurso más probable, o None."""
    n = normalizar(texto)
    tokens = n.split()
    if not tokens:
        return None

    puntajes = {}

    for recurso, frases in VOCABULARIO.items():
        claves = CLAVES.get(recurso, [])

        if recurso == "tipos_violencia":
            tiene_tipo = any(
                _parecido(token, clave, corte=0.75)
                for token in tokens
                for clave in ["tipo", "tipos", "clase", "clases"]
            )
            tiene_violencia = any(
                _parecido(token, "violencia", corte=0.75) for token in tokens
            )
            puntajes[recurso] = 1.0 if (tiene_tipo and tiene_violencia) else 0.0
            continue

        score = 0.0
        for token in tokens:
            if any(_parecido(token, clave, corte=0.75) for clave in claves):
                score = 1.0
                break

        if score == 0.0:
            score = max(
                difflib.SequenceMatcher(None, n, frase).ratio()
                for frase in frases
            )

        puntajes[recurso] = score

    mejor_recurso = max(puntajes, key=puntajes.get)
    if puntajes[mejor_recurso] >= 0.65:
        return mejor_recurso
    return None


if __name__ == "__main__":
    pruebas = [
        "cuantos tipos de violencia existen",
        "cuantos tpos de violncia existen",
        "cuantas clses de violensia hay",
        "que fuentes manejas",
        "de que estados tienes datos",
        "que indicadores tienes",
        "cuantas publicaciones de X hay en Jalisco",
    ]
    for p in pruebas:
        print(f"{str(pista(p)):18} | {p}")
