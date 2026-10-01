"""Router de intención (Fase 3 + Fase 6).

Orden de resolución:
  conversación → explicar → ayuda → FAQ exacta → definición (FAQ/glosario/corpus)
  → seguir → datos (agregación/detalle) → FAQ semántica → seguimiento → corpus
  → clarificación.
"""
import re
import unicodedata

import semantic_loader
import faq_store
from contexto_conversacional import pregunta_parece_seguimiento_directo


SALUDOS = [
    "hola", "buenos dias", "buenas tardes", "buenas noches", "hey",
    "que tal", "quien eres", "gracias", "adios", "hasta luego", "buen dia",
]

AYUDA_FRASES = ["que puedo preguntar", "que preguntar", "que sabes hacer"]
AYUDA_PATRONES = [
    r"\bayuda\b",
    r"que\s+(cosas|mas|puedo|puedes|podria)\b.*pregunt",
    r"que\s+(datos|informacion)\b",
    r"que\s+(me\s+)?puedes\s+(decir|contestar|responder|ofrecer)",
    r"en\s+que\s+(me\s+)?puedes\s+ayudar",
    r"que\s+opciones\s+tengo",
    r"como\s+funciona",
    r"que\s+haces",
    r"para\s+que\s+sirves",
]

DEFINICION = [
    "que es", "que significa", "define", "definicion", "a que se refiere",
    "que quiere decir", "que son",
]

EXPLICAR_MARCADORES = [
    "explicame", "explica eso", "explica esto", "explica mejor",
    "no entiendo", "no lo entiendo", "no le entiendo", "no comprendo",
    "no me queda claro", "en otras palabras", "a que te refieres",
    "que quisiste decir", "reformula", "de otra forma", "mas simple",
    "mas claro", "que significa eso", "y eso que significa",
    "que quiere decir eso", "no se entiende",
]

SEGUIR_MARCADORES = [
    "muestrame", "muestra los", "muestra las", "dame los", "dame las",
    "dame el detalle", "cuales son", "cuales fueron", "listame", "lista ",
    "desglosa", "los indicadores", "el detalle", "ver los", "muestralos",
]

PISTAS_DATOS = [
    "indicador", "endireh", "siesvim", "inmujeres", "promedio", "cuantos",
    "cuantas", "valor", "entidad", "estado", "publicacion", "publicaciones",
    "registro", "registros", "fuente", "tipo", "anio", "ano",
]

DOMINIO = [
    "violencia", "mujer", "mujeres", "genero", "ley", "derecho", "denuncia",
    "refugio", "atencion", "victima", "acoso", "feminicidio", "agresion",
    "cjm", "banavim", "conavim", "endireh", "siesvim", "inmujeres",
    "protocolo", "proteccion", "alerta", "hostigamiento", "abuso",
]

GRUPO = [
    "por anio", "cada anio", "por ano", "cada ano", "por entidad",
    "por estado", "por tipo",
]

OPERACION_AGREGACION = {"conteo", "promedio", "maximo", "minimo", "suma", "top_n"}

MARCADORES_SEGUIMIENTO = [
    "cada anio", "por anio", "cada ano", "por ano", "y en", "tambien",
    "de esos", "de esas", "ese ", "esa ", "el mismo", "la misma",
    "ahora", "entonces", "y el", "y la", "de cada", "por cada",
]


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _es_conversacion(texto):
    if len(texto.split()) > 4:
        return False
    return any(s in texto for s in SALUDOS)


def _es_ayuda(texto):
    if any(f in texto for f in AYUDA_FRASES):
        return True
    return any(re.search(p, texto) for p in AYUDA_PATRONES)


RUTAS_MARCADORES = [
    "sufriendo violencia", "sufro violencia", "estoy sufriendo", "vivo violencia",
    "donde puedo", "donde acudo", "a donde acudo", "a donde puedo", "donde acudir",
    "a donde acudir", "donde denunciar", "como denuncio", "quiero denunciar",
    "necesito ayuda", "me pueden ayudar", "me puede ayudar", "pueden ayudarme",
    "busco ayuda", "conseguir ayuda", "ayuda legal", "ayuda psicologica",
    "refugio", "linea de ayuda", "telefono de ayuda", "numero de emergencia",
    "que hago si", "que puedo hacer si",
]

RUTAS_CLAVES = [
    "violencia", "agred", "agres", "maltrat", "denunci", "refugio", "peligro",
    "proteccion", "ayuda", "abuso", "golpe", "amenaz",
]


def _es_rutas(texto):
    if any(m in texto for m in RUTAS_MARCADORES) and any(
        k in texto for k in RUTAS_CLAVES
    ):
        return True
    return False


def _es_definicion(texto):
    return any(s in texto for s in DEFINICION)


def _es_explicar(texto, contexto):
    if not contexto or not contexto.get("pregunta"):
        return False
    if any(m in texto for m in EXPLICAR_MARCADORES):
        return True
    if re.search(r"\b(eso|esto|ello|aquello)\b", texto) and any(
        v in texto
        for v in ["significa", "explica", "entiendo", "refiere", "quiere decir", "comprendo"]
    ):
        return True
    return False


def _es_seguir(texto, contexto, señales):
    if not contexto or not contexto.get("spec"):
        return False
    if señales.get("metrica") or señales.get("agrupacion"):
        return False
    return any(m in texto for m in SEGUIR_MARCADORES)


def _es_dominio(texto):
    return any(s in texto for s in DOMINIO)


def _recurso_catalogo(texto):
    # No es un catálogo si menciona una entidad o fuente concreta:
    # "tipos de violencia en Veracruz" es una consulta de datos.
    if semantic_loader.resolver_entidad(texto) or semantic_loader.resolver_fuente(texto):
        return None

    if re.search(r"tipos?\s+de\s+violencia", texto) and not any(
        x in texto for x in ["mas comun", "predomina", "frecuente", "mayor medida"]
    ):
        if any(
            x in texto
            for x in ["cuantos", "cuantas", "cuales", "que ", "existen", "hay", "dime", "son", "lista"]
        ):
            return "tipos_violencia"
    if re.search(r"\bfuentes\b", texto) and any(
        x in texto for x in ["que ", "cuales", "cuantas", "hay", "usa", "utiliza"]
    ):
        return "fuentes"
    return None


def _senales_datos(texto):
    señales = {}
    if any(c.isdigit() for c in texto):
        señales["anio"] = True

    metrica = semantic_loader.resolver_metrica(texto)
    if metrica and metrica != "detalle":
        señales["metrica"] = metrica

    entidad = semantic_loader.resolver_entidad(texto)
    if entidad:
        señales["entidad_id"] = entidad

    fuente = semantic_loader.resolver_fuente(texto)
    if fuente:
        señales["fuente"] = fuente

    if any(p in texto for p in PISTAS_DATOS):
        señales["pista"] = True

    if any(g in texto for g in GRUPO):
        señales["agrupacion"] = True

    return señales


def _resultado(tipo, **extra):
    base = {
        "tipo": tipo,
        "faq": None,
        "fragmentos": [],
        "fuente": None,
        "entidad_id": None,
        "metrica": None,
        "recurso": None,
    }
    base.update(extra)
    return base


def clasificar(pregunta, contexto=None):
    texto = normalizar(pregunta)

    if not texto:
        return _resultado("CONVERSACION")

    if _es_conversacion(texto):
        return _resultado("CONVERSACION")

    # Rutas de atención antes que ayuda: "necesito ayuda por violencia".
    if _es_rutas(texto):
        return _resultado("RUTAS")

    # AYUDA antes que EXPLICAR: "explícame qué puedes responder" es ayuda.
    if _es_ayuda(texto):
        return _resultado("AYUDA")

    if _es_explicar(texto, contexto):
        return _resultado("EXPLICAR")

    # FAQ exacta (alta precisión) antes que datos.
    faq_exacta = faq_store.buscar_exacta(texto)
    if faq_exacta:
        return _resultado("FAQ", faq=faq_exacta)

    # Catálogos ("tipos de violencia", "fuentes")
    recurso = _recurso_catalogo(texto)
    if recurso:
        return _resultado("CATALOGO", recurso=recurso)

    # Definiciones: FAQ semántica → glosario → corpus.
    if _es_definicion(texto):
        faq = faq_store.buscar_semantica(texto)
        if faq:
            return _resultado("FAQ", faq=faq)

        entrada = faq_store.buscar_glosario(texto)
        if entrada:
            return _resultado(
                "FAQ",
                faq={
                    "pregunta": entrada["termino"],
                    "respuesta": entrada["definicion"],
                },
            )

        fragmentos = faq_store.buscar_corpus(texto)
        if fragmentos:
            return _resultado("FAQ_CORPUS", fragmentos=fragmentos)

    # Señales de datos
    señales = _senales_datos(texto)

    # Heredar la operación de agregación del contexto en seguimientos.
    previo = (contexto or {}).get("spec") or {}
    if (
        contexto
        and contexto.get("pregunta")
        and not señales.get("metrica")
        and not señales.get("agrupacion")
        and any(m in texto for m in MARCADORES_SEGUIMIENTO)
        and previo.get("metrica") in OPERACION_AGREGACION
    ):
        señales["metrica"] = previo["metrica"]

    if _es_seguir(texto, contexto, señales):
        return _resultado("SEGUIR")

    if señales.get("metrica") or señales.get("agrupacion"):
        return _resultado(
            "CONSULTA_AGREGACION",
            fuente=señales.get("fuente"),
            entidad_id=señales.get("entidad_id"),
            metrica=señales.get("metrica"),
        )

    if señales.get("fuente") or señales.get("entidad_id") or señales.get("anio"):
        return _resultado(
            "CONSULTA_DETALLE",
            fuente=señales.get("fuente"),
            entidad_id=señales.get("entidad_id"),
        )

    # Hay pista de datos pero sin filtros suficientes: pedir aclaración.
    if señales.get("pista"):
        return _resultado("CLARIFICACION")

    faq = faq_store.buscar_semantica(texto)
    if faq:
        return _resultado("FAQ", faq=faq)

    if contexto and contexto.get("pregunta") and pregunta_parece_seguimiento_directo(pregunta):
        return _resultado("SEGUIMIENTO")

    if _es_dominio(texto):
        fragmentos = faq_store.buscar_corpus(texto)
        if fragmentos:
            return _resultado("FAQ_CORPUS", fragmentos=fragmentos)

    return _resultado("CLARIFICACION")


if __name__ == "__main__":
    pruebas = [
        "hola",
        "¿qué es ENDIREH?",
        "¿qué es BANAVIM?",
        "¿qué es un CJM?",
        "promedio de ENDIREH para Jalisco en 2021",
        "cuántas publicaciones de X hay en Jalisco",
        "indicadores de Puebla",
        "indicadores",
        "dame el código de hola mundo en C",
        "¿qué cosas puedo preguntar?",
    ]
    for p in pruebas:
        r = clasificar(p)
        print(f"{r['tipo']:20} | {p}")

    print("\nCon contexto:")
    ctx = {
        "pregunta": "promedio de ENDIREH para Jalisco en 2021",
        "spec": {"operacion": "promedio", "metrica": "promedio", "fuente": "ENDIREH",
                 "entidad": "Jalisco", "entidad_id": 16, "anio": 2021, "grupo": [],
                 "orden": "desc", "limite": 100, "indicador": None},
    }
    for p in ["Y eso qué significa?", "No entiendo, explícamelo", "Muéstrame los indicadores",
              "Entonces qué cosas podría preguntar?"]:
        r = clasificar(p, ctx)
        print(f"{r['tipo']:20} | {p}")
