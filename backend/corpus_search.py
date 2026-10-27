"""Recuperación del corpus documental en tres modos (Fase 3).

Modos:
- ``fulltext``  : MATCH ... AGAINST de MySQL, comportamiento oficial.
- ``embedding`` : similitud vectorial con sentence-transformers.
- ``hybrid``    : Reciprocal Rank Fusion (RRF) de ambos rankings.

El modo se elige con el argumento ``modo`` o con ``MHUB_CORPUS_MODE``.
Si el modelo o el índice no están disponibles, se cae a ``fulltext`` y se
registra el fallback en el resultado (``fallback=True``).
"""
import json
import os
import threading
import time

from database import ejecutar_select

MODELO_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONES = 384
TOP_K_DEFECTO = 3
RRF_K_DEFECTO = 60
MODOS = ("fulltext", "embedding", "hybrid")

_indice = None
_indice_lock = threading.Lock()
_modelo = None
_modelo_lock = threading.Lock()
_ultima_busqueda = {"modo_solicitado": None, "fallback": False, "motivo": None}


def _entero_env(nombre, defecto):
    try:
        return int(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def modo_por_defecto():
    modo = (os.environ.get("MHUB_CORPUS_MODE") or "fulltext").strip().lower()
    return modo if modo in MODOS else "fulltext"


def _registrar_ultima(modo_solicitado, fallback=False, motivo=None):
    global _ultima_busqueda
    _ultima_busqueda = {
        "modo_solicitado": modo_solicitado,
        "fallback": bool(fallback),
        "motivo": motivo,
    }


def ultima_busqueda():
    """Copia del estado de la última llamada a ``buscar_corpus``."""
    return dict(_ultima_busqueda)


def _normalizar_texto(texto):
    return str(texto or "").strip()


def limpiar_cache():
    """Olvida el índice y el modelo cargados (útil tras regenerar embeddings)."""
    global _indice, _modelo
    with _indice_lock:
        _indice = None
    with _modelo_lock:
        _modelo = None


def cargar_indice(forzar=False):
    """Carga textos, metadatos y embeddings desde MySQL y los cachea."""
    global _indice

    if _indice is not None and not forzar:
        return _indice

    with _indice_lock:
        if _indice is not None and not forzar:
            return _indice

        import numpy as np

        inicio = time.perf_counter()
        filas = ejecutar_select(
            """
            SELECT f.id_fragmento, f.id_documento, f.texto, f.pagina,
                   f.embedding, f.modelo_embedding, f.dimensiones,
                   d.nombre AS documento, fu.nombre AS fuente
            FROM fragmentos_documentos f
            JOIN documentos d ON d.id_documento = f.id_documento
            JOIN fuentes fu ON fu.id_fuente = d.id_fuente
            WHERE d.incluido_faq = 1
              AND f.embedding IS NOT NULL
              AND f.texto IS NOT NULL
              AND TRIM(f.texto) <> ''
            ORDER BY f.id_fragmento
            """,
            database="HUBDATOS",
        )

        if not filas:
            raise RuntimeError(
                "No hay embeddings en fragmentos_documentos. "
                "Ejecuta ingestion/embeddings/generar_embeddings.py."
            )

        conteo_modelos = {}
        for fila in filas:
            modelo = fila.get("modelo_embedding") or "(sin modelo)"
            conteo_modelos[modelo] = conteo_modelos.get(modelo, 0) + 1
        modelo_dominante = max(conteo_modelos, key=conteo_modelos.get)

        vectores = []
        meta = []
        omitidos = 0
        for fila in filas:
            if (fila.get("modelo_embedding") or "(sin modelo)") != modelo_dominante:
                omitidos += 1
                continue
            try:
                vector = np.asarray(json.loads(fila["embedding"]), dtype=np.float32)
            except (TypeError, ValueError, json.JSONDecodeError):
                omitidos += 1
                continue
            if vector.shape != (DIMENSIONES,):
                omitidos += 1
                continue

            norma = float(np.linalg.norm(vector))
            if norma > 0:
                vector = vector / norma
            vectores.append(vector)
            meta.append({
                "id_fragmento": int(fila["id_fragmento"]),
                "id_documento": int(fila["id_documento"]),
                "texto": fila["texto"],
                "documento": fila["documento"],
                "pagina": fila["pagina"],
                "fuente": fila["fuente"],
            })

        if not vectores:
            raise RuntimeError("Los embeddings disponibles no tienen 384 dimensiones.")

        matriz = np.vstack(vectores).astype(np.float32)
        _indice = {
            "matriz": matriz,
            "meta": meta,
            "modelo": modelo_dominante,
            "omitidos": omitidos,
            "cargado_en": time.time(),
            "carga_segundos": round(time.perf_counter() - inicio, 3),
        }
        if omitidos:
            print(f"[corpus_search] índice: {omitidos} fragmentos omitidos por modelo/dimensión")
        print(
            f"[corpus_search] índice listo: {len(meta)} fragmentos, "
            f"{matriz.shape[1]} dimensiones, {_indice['carga_segundos']} s"
        )
        return _indice


def cargar_modelo():
    """Carga sentence-transformers una sola vez."""
    global _modelo

    if _modelo is not None:
        return _modelo

    with _modelo_lock:
        if _modelo is not None:
            return _modelo

        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from sentence_transformers import SentenceTransformer

        nombre = os.environ.get("MHUB_EMBEDDING_MODEL", MODELO_DEFECTO)
        inicio = time.perf_counter()
        modelo = SentenceTransformer(nombre, device="cpu")
        _modelo = modelo
        print(
            f"[corpus_search] modelo listo: {nombre} "
            f"en {time.perf_counter() - inicio:.2f} s"
        )
        return _modelo


def _fila_salida(meta, score, modo, rank, fallback=False):
    return {
        "id_fragmento": meta["id_fragmento"],
        "id_documento": meta["id_documento"],
        "texto": meta["texto"],
        "documento": meta["documento"],
        "pagina": meta["pagina"],
        "fuente": meta["fuente"],
        "score": float(score),
        "modo": modo,
        "rank": rank,
        "fallback": bool(fallback),
    }


def buscar_fulltext(texto, limite=TOP_K_DEFECTO):
    """Recuperación léxica con MATCH ... AGAINST (comportamiento actual)."""
    limite = max(1, min(int(limite), 50))
    filas = ejecutar_select(
        """
        SELECT f.id_fragmento, f.id_documento, f.texto, f.pagina,
               d.nombre AS documento, fu.nombre AS fuente,
               MATCH(f.texto) AGAINST (%s IN NATURAL LANGUAGE MODE) AS score
        FROM fragmentos_documentos f
        JOIN documentos d ON d.id_documento = f.id_documento
        JOIN fuentes fu ON fu.id_fuente = d.id_fuente
        WHERE d.incluido_faq = 1
          AND f.texto IS NOT NULL
          AND TRIM(f.texto) <> ''
          AND MATCH(f.texto) AGAINST (%s IN NATURAL LANGUAGE MODE)
        ORDER BY score DESC
        LIMIT %s
        """,
        database="HUBDATOS",
        params=(texto, texto, limite),
    )

    salida = []
    for rank, fila in enumerate(filas, 1):
        meta = {
            "id_fragmento": int(fila["id_fragmento"]),
            "id_documento": int(fila["id_documento"]),
            "texto": fila["texto"],
            "documento": fila["documento"],
            "pagina": fila["pagina"],
            "fuente": fila["fuente"],
        }
        salida.append(_fila_salida(meta, fila["score"], "fulltext", rank))
    return salida


def buscar_embedding(texto, limite=TOP_K_DEFECTO):
    """Recuperación semántica por producto punto con vectores normalizados."""
    limite = max(1, min(int(limite), 50))
    indice = cargar_indice()
    modelo = cargar_modelo()

    vector = modelo.encode(
        [texto],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    vector = vector.astype("float32")
    scores = indice["matriz"] @ vector
    orden = scores.argsort()[::-1][:limite]

    salida = []
    for rank, pos in enumerate(orden, 1):
        salida.append(
            _fila_salida(indice["meta"][int(pos)], float(scores[pos]),
                         "embedding", rank)
        )
    return salida


def buscar_hibrido(texto, limite=TOP_K_DEFECTO, k_rrf=None):
    """Fusiona los rankings léxico y semántico con Reciprocal Rank Fusion."""
    limite = max(1, min(int(limite), 50))
    k_rrf = int(k_rrf or _entero_env("MHUB_HYBRID_K", RRF_K_DEFECTO))
    candidatos = max(limite * 5, 20)

    lexicos = buscar_fulltext(texto, limite=candidatos)
    semanticos = buscar_embedding(texto, limite=candidatos)

    fusion = {}
    for lista, clave in ((lexicos, "lexico"), (semanticos, "semantico")):
        for fila in lista:
            item = fusion.get(fila["id_fragmento"])
            if item is None:
                item = {
                    **fila,
                    "score": 0.0,
                    "score_lexico": 0.0,
                    "score_semantico": 0.0,
                }
                fusion[fila["id_fragmento"]] = item
            item[f"score_{clave}"] = fila["score"]
            item["score"] += 1.0 / (k_rrf + fila["rank"])

    ordenados = sorted(
        fusion.values(),
        key=lambda f: (
            -f["score"],
            -f.get("score_semantico", 0.0),
            -f.get("score_lexico", 0.0),
        ),
    )

    salida = []
    for rank, fila in enumerate(ordenados[:limite], 1):
        fila = dict(fila)
        fila["modo"] = "hybrid"
        fila["rank"] = rank
        fila["fallback"] = False
        salida.append(fila)
    return salida


def buscar_corpus(texto, limite=None, modo=None):
    """Punto de entrada único.

    Devuelve hasta ``limite`` fragmentos con documento, página, fuente,
    score, modo y rank. Si el modo semántico falla, cae a fulltext.
    """
    texto = _normalizar_texto(texto)
    if limite is None:
        limite = _entero_env("MHUB_CORPUS_TOP_K", TOP_K_DEFECTO)
    if len(texto) < 4:
        _registrar_ultima(modo or modo_por_defecto())
        return []

    solicitado = (modo or modo_por_defecto()).strip().lower()
    if solicitado not in MODOS:
        print(f"[corpus_search] modo desconocido '{solicitado}', se usa fulltext")
        solicitado = "fulltext"

    if solicitado == "fulltext":
        resultados = buscar_fulltext(texto, limite=limite)
        _registrar_ultima("fulltext")
        return resultados

    try:
        if solicitado == "embedding":
            resultados = buscar_embedding(texto, limite=limite)
        else:
            resultados = buscar_hibrido(texto, limite=limite)
        _registrar_ultima(solicitado)
        return resultados
    except Exception as error:
        print(f"[corpus_search] fallback a fulltext ({solicitado}): {error}")
        try:
            resultados = buscar_fulltext(texto, limite=limite)
        except Exception as error_fulltext:
            print(f"[corpus_search] fulltext también falló: {error_fulltext}")
            resultados = []
        for fila in resultados:
            fila["fallback"] = True
        _registrar_ultima(solicitado, fallback=True, motivo=str(error))
        return resultados


def estado_indice():
    """Diagnóstico sin cargar el modelo."""
    try:
        indice = cargar_indice()
        return {
            "disponible": True,
            "fragmentos": len(indice["meta"]),
            "dimensiones": int(indice["matriz"].shape[1]),
            "modelo": indice["modelo"],
            "omitidos": indice["omitidos"],
            "carga_segundos": indice["carga_segundos"],
            "modo_por_defecto": modo_por_defecto(),
        }
    except Exception as error:
        return {
            "disponible": False,
            "detalle": str(error),
            "modo_por_defecto": modo_por_defecto(),
        }
