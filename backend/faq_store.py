"""Acceso al catálogo de FAQ y al corpus documental (Fase 3)."""
import difflib
import re
import unicodedata

from database import ejecutar_select


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def cargar_faqs():
    try:
        return ejecutar_select(
            "SELECT id_faq, pregunta, patron, sinonimos, id_intencion, "
            "respuesta, consulta_sql, requiere_bd, prioridad "
            "FROM faq WHERE activo = 1 ORDER BY prioridad, id_faq",
            database="mhub_meta",
        )
    except Exception as error:
        print(f"[faq_store] faq no disponible: {error}")
        return []


def buscar_exacta(texto):
    """Coincidencia por frase patrón. Ignora alternativas de una sola palabra."""
    n = normalizar(texto)
    for faq in cargar_faqs():
        patron = faq.get("patron") or ""
        for alternativa in patron.split("|"):
            alternativa = normalizar(alternativa)
            if not alternativa or " " not in alternativa:
                continue
            if alternativa in n:
                return faq
    return None


def _similitud(pregunta_n, faq):
    objetivos = [normalizar(faq["pregunta"])]
    if faq.get("sinonimos"):
        objetivos.append(normalizar(faq["sinonimos"]))

    mejor = 0.0
    for objetivo in objetivos:
        if not objetivo:
            continue
        ratio = difflib.SequenceMatcher(None, pregunta_n, objetivo).ratio()
        tokens_q = set(pregunta_n.split())
        tokens_o = set(objetivo.split())
        if tokens_o:
            cobertura = len(tokens_q & tokens_o) / len(tokens_o)
        else:
            cobertura = 0.0
        mejor = max(mejor, 0.5 * ratio + 0.5 * cobertura)
    return mejor


def buscar_semantica(texto, umbral=0.62):
    n = normalizar(texto)
    if len(n) < 4:
        return None

    mejor_faq = None
    mejor_score = 0.0
    for faq in cargar_faqs():
        score = _similitud(n, faq)
        if score > mejor_score:
            mejor_score = score
            mejor_faq = faq

    if mejor_faq and mejor_score >= umbral:
        mejor_faq = dict(mejor_faq)
        mejor_faq["_score"] = round(mejor_score, 3)
        return mejor_faq
    return None


def buscar_corpus(texto, limite=3):
    n = normalizar(texto)
    if len(n) < 4:
        return []
    try:
        return ejecutar_select(
            """
            SELECT
              f.texto,
              d.nombre AS documento,
              fu.nombre AS fuente,
              MATCH(f.texto) AGAINST (%s IN NATURAL LANGUAGE MODE) AS score
            FROM fragmentos_documentos f
            JOIN documentos d ON d.id_documento = f.id_documento
            JOIN fuentes fu ON fu.id_fuente = d.id_fuente
            WHERE d.incluido_faq = 1
              AND MATCH(f.texto) AGAINST (%s IN NATURAL LANGUAGE MODE)
            ORDER BY score DESC
            LIMIT %s
            """,
            database="HUBDATOS",
            params=(texto, texto, limite),
        )
    except Exception as error:
        print(f"[faq_store] corpus no disponible: {error}")
        return []


def cargar_glosario():
    try:
        return ejecutar_select(
            "SELECT termino, definicion, categoria, sinonimos FROM glosario",
            database="mhub_meta",
        )
    except Exception as error:
        print(f"[faq_store] glosario no disponible: {error}")
        return []


def buscar_glosario(texto):
    n = normalizar(texto)
    for entrada in cargar_glosario():
        candidatos = [entrada["termino"]]
        if entrada.get("sinonimos"):
            candidatos += [s.strip() for s in entrada["sinonimos"].split(",")]
        for candidato in candidatos:
            c = normalizar(candidato)
            if c and re.search(rf"\b{re.escape(c)}\b", n):
                return entrada
    return None


def glosario_relevante(texto, limite=6):
    """Términos del glosario con mayor solapamiento con el texto."""
    n = normalizar(texto)
    tokens = set(n.split())
    puntuados = []
    for entrada in cargar_glosario():
        objetivo = normalizar(entrada["termino"])
        if entrada.get("sinonimos"):
            objetivo += " " + normalizar(entrada["sinonimos"])
        objetivo_tokens = set(objetivo.split())
        if not objetivo_tokens:
            continue
        solape = len(tokens & objetivo_tokens)
        if solape:
            puntuados.append((solape, entrada))
    puntuados.sort(key=lambda x: x[0], reverse=True)
    return [entrada for _, entrada in puntuados[:limite]]

