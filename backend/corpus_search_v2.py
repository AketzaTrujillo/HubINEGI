"""Recuperación del corpus v2 (Fase 3 mejorada).

Cambios frente a v1:
- Fragmentos re-cortados (~350 tokens) y limpios de encabezados/pies.
- Embeddings con `intfloat/multilingual-e5-small` (512 tokens, 384 dims),
  guardados como BLOB float32.
- BM25 en memoria con análisis español (acentos, stopwords y stemming).
- Expansión de siglas y sinónimos.
- Fusión RRF configurable.
- Reranker cross-encoder multilingüe sobre el top-N.
- Deduplicación por página en el resultado final.

La tabla `fragmentos_documentos_v2` convive con la v1; no se modifica nada
de la versión anterior.

Modos: ``fulltext``, ``bm25``, ``embedding``, ``hybrid_rrf`` y ``hybrid``.
"""
import heapq
import math
import os
import re
import threading
import time
import unicodedata
from collections import Counter

from database import ejecutar_select
import expansion_consultas

try:
    import snowballstemmer
except ImportError:  # pragma: no cover
    snowballstemmer = None

MODELO_DEFECTO = os.environ.get(
    "MHUB_V2_EMBEDDING_MODEL", "intfloat/multilingual-e5-small"
)
RERANKER_DEFECTO = os.environ.get(
    "MHUB_RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
)
TOP_K_DEFECTO = 3
RRF_K_DEFECTO = 60
MODOS = ("fulltext", "bm25", "embedding", "hybrid", "hybrid_rrf", "hybrid_rerank")
VERSION = "v2"

STOPWORDS = {
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con",
    "contra", "cual", "cuales", "cuando", "cuanta", "cuantas", "cuanto",
    "cuantos", "de", "del", "desde", "donde", "dos", "el", "ella", "ellas",
    "ello", "ellos", "en", "entre", "era", "es", "esa", "esas", "ese", "eso",
    "esos", "esta", "estas", "este", "esto", "estos", "fue", "ha", "hasta",
    "hay", "la", "las", "le", "les", "lo", "los", "mas", "me", "mi", "mis",
    "mucho", "muy", "no", "nos", "o", "otra", "otras", "otro", "otros",
    "para", "pero", "poco", "por", "porque", "que", "quien", "quienes",
    "se", "sea", "segun", "ser", "si", "sin", "sobre", "son", "su", "sus",
    "tal", "tambien", "te", "tiene", "tu", "tus", "un", "una", "unas", "uno",
    "unos", "y", "ya", "yo", "durante", "mediante", "hacia", "despues",
}

_indice = None
_bm25 = None
_meta_bm25 = None
_modelo = None
_modelo_info = None
_reranker = None
_reranker_error = None
_lock = threading.RLock()
_ultima = {"modo_solicitado": None, "modo_efectivo": None, "fallback": False,
           "motivo": None, "rerank": False}

_stemmer = None


def _stem(token):
    global _stemmer
    if snowballstemmer is None:
        return token
    if _stemmer is None:
        _stemmer = snowballstemmer.stemmer("spanish")
    return _stemmer.stemWord(token)


def _normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9ñ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tokenizar(texto):
    tokens = []
    for token in _normalizar(texto).split():
        if len(token) < 2 or token in STOPWORDS:
            continue
        tokens.append(_stem(token))
    return tokens


def _entero_env(nombre, defecto):
    try:
        return int(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def _float_env(nombre, defecto):
    try:
        return float(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def _registrar_ultima(modo_solicitado, modo_efectivo, fallback=False,
                      motivo=None, rerank=False):
    global _ultima
    _ultima = {
        "modo_solicitado": modo_solicitado,
        "modo_efectivo": modo_efectivo,
        "fallback": bool(fallback),
        "motivo": motivo,
        "rerank": bool(rerank),
    }


def ultima_busqueda():
    return dict(_ultima)


def limpiar_cache():
    global _indice, _bm25, _meta_bm25, _modelo, _modelo_info, _reranker, _reranker_error
    with _lock:
        _indice = None
        _bm25 = None
        _meta_bm25 = None
        _modelo = None
        _modelo_info = None
        _reranker = None
        _reranker_error = None


# ------------------------------------------------------------------ índice

def _meta_desde_fila(fila):
    return {
        "id_fragmento_v2": int(fila["id_fragmento_v2"]),
        "id_documento": int(fila["id_documento"]),
        "texto": fila["texto"],
        "documento": fila["documento"],
        "pagina": fila["pagina"],
        "fuente": fila["fuente"],
        "orden": fila.get("orden"),
    }


def cargar_indice_v2(forzar=False):
    global _indice
    if _indice is not None and not forzar:
        return _indice

    with _lock:
        if _indice is not None and not forzar:
            return _indice

        import numpy as np

        inicio = time.perf_counter()
        filas = ejecutar_select("""
            SELECT f.id_fragmento_v2, f.id_documento, f.texto, f.pagina, f.orden,
                   f.embedding, f.modelo_embedding, f.dimensiones,
                   d.nombre AS documento, fu.nombre AS fuente
            FROM fragmentos_documentos_v2 f
            JOIN documentos d ON d.id_documento = f.id_documento
            JOIN fuentes fu ON fu.id_fuente = d.id_fuente
            WHERE f.embedding IS NOT NULL
              AND f.texto IS NOT NULL
              AND TRIM(f.texto) <> ''
            ORDER BY f.id_fragmento_v2
        """, database="HUBDATOS")

        if not filas:
            raise RuntimeError(
                "No hay embeddings v2. Ejecuta ingestion/v2/rechunk_corpus.py "
                "y generar_embeddings_v2.py."
            )

        conteo = Counter(f.get("modelo_embedding") or "(sin modelo)" for f in filas)
        modelo_dominante = conteo.most_common(1)[0][0]
        dimensiones_dominante = Counter(
            int(f.get("dimensiones") or 0) for f in filas
            if (f.get("modelo_embedding") or "(sin modelo)") == modelo_dominante
        ).most_common(1)[0][0]

        vectores = []
        meta = []
        omitidos = 0
        for fila in filas:
            if (fila.get("modelo_embedding") or "(sin modelo)") != modelo_dominante:
                omitidos += 1
                continue
            if int(fila.get("dimensiones") or 0) != dimensiones_dominante:
                omitidos += 1
                continue
            vector = np.frombuffer(fila["embedding"], dtype=np.float32)
            if vector.size != dimensiones_dominante:
                omitidos += 1
                continue
            norma = float(np.linalg.norm(vector))
            if norma > 0:
                vector = vector / norma
            vectores.append(vector)
            meta.append(_meta_desde_fila(fila))

        if not vectores:
            raise RuntimeError("Los embeddings v2 no tienen dimensiones válidas.")

        matriz = np.vstack(vectores).astype(np.float32)
        _indice = {
            "matriz": matriz,
            "meta": meta,
            "modelo": modelo_dominante,
            "dimensiones": dimensiones_dominante,
            "omitidos": omitidos,
            "carga_s": round(time.perf_counter() - inicio, 3),
        }
        print(f"[corpus_search_v2] índice: {len(meta)} chunks, "
              f"{dimensiones_dominante} dims, {_indice['carga_s']} s")
        return _indice


def _titulo_normalizado(nombre):
    """Normaliza el título y expande sus siglas (CJM, BANAVIM, etc.)."""
    titulo = expansion_consultas.normalizar(nombre)
    for sigla, expansion in expansion_consultas.ACRONIMOS.items():
        titulo = re.sub(
            rf"\b{re.escape(sigla)}\b",
            expansion_consultas.normalizar(expansion),
            titulo,
        )
    return titulo


class BM25:
    def __init__(self, documentos, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.N = len(documentos)
        self.tfs = [Counter(d["tokens"]) for d in documentos]
        self.doc_len = [len(d["tokens"]) for d in documentos]
        self.avgdl = sum(self.doc_len) / max(1, self.N)
        self.textos_norm = [expansion_consultas.normalizar(d["texto"]) for d in documentos]
        self.titulos_norm = [
            _titulo_normalizado(d.get("documento", "")) for d in documentos
        ]
        df = Counter()
        for tokens in (d["tokens"] for d in documentos):
            df.update(set(tokens))
        self.idf = {
            termino: math.log(1 + (self.N - n + 0.5) / (n + 0.5))
            for termino, n in df.items()
        }

    def buscar(self, pesos, limite, frases_bonus=(), titulos_bonus=(), definiciones=()):
        frases = [
            (expansion_consultas.normalizar(frase), float(bonus))
            for frase, bonus in frases_bonus
            if frase and frase.strip()
        ]
        titulos = [
            (expansion_consultas.normalizar(termino), float(bonus))
            for termino, bonus in titulos_bonus
            if termino and termino.strip()
        ]
        patrones_def = []
        for frase, bonus in definiciones:
            f = expansion_consultas.normalizar(frase)
            if not f:
                continue
            patrones_def.append((
                bonus,
                (
                    f"{f} es ", f"{f} son ", f"{f} se refiere", f"{f} consiste",
                    f"que es {f}", f"que son {f}", f"que significa {f}",
                ),
            ))

        resultados = []
        for i, tf in enumerate(self.tfs):
            dl = self.doc_len[i]
            score = 0.0
            for termino, peso in pesos.items():
                frecuencia = tf.get(termino)
                if not frecuencia:
                    continue
                idf = self.idf.get(termino)
                if not idf:
                    continue
                score += (
                    peso * idf
                    * (frecuencia * (self.k1 + 1))
                    / (frecuencia + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                )
            for frase, bonus in frases:
                if frase in self.textos_norm[i]:
                    score += bonus
            for termino, bonus in titulos:
                titulo = self.titulos_norm[i]
                if len(titulo) >= 5 and (termino in titulo or titulo in termino):
                    score += bonus
            for bonus, patrones in patrones_def:
                if any(patron in self.textos_norm[i] for patron in patrones):
                    score += bonus
            if score > 0:
                resultados.append((score, i))
        return heapq.nlargest(limite, resultados, key=lambda x: x[0])


def cargar_bm25(forzar=False):
    global _bm25, _meta_bm25
    if _bm25 is not None and not forzar:
        return _bm25

    with _lock:
        if _bm25 is not None and not forzar:
            return _bm25

        inicio = time.perf_counter()
        filas = ejecutar_select("""
            SELECT f.id_fragmento_v2, f.id_documento, f.texto, f.pagina, f.orden,
                   d.nombre AS documento, fu.nombre AS fuente
            FROM fragmentos_documentos_v2 f
            JOIN documentos d ON d.id_documento = f.id_documento
            JOIN fuentes fu ON fu.id_fuente = d.id_fuente
            WHERE f.texto IS NOT NULL AND TRIM(f.texto) <> ''
            ORDER BY f.id_fragmento_v2
        """, database="HUBDATOS")

        if not filas:
            raise RuntimeError(
                "No hay fragmentos v2. Ejecuta ingestion/v2/rechunk_corpus.py."
            )

        meta = []
        documentos = []
        for fila in filas:
            item = _meta_desde_fila(fila)
            meta.append(item)
            documentos.append({
                "tokens": tokenizar(fila["texto"]),
                "texto": fila["texto"],
                "documento": fila["documento"],
            })

        _meta_bm25 = meta
        _bm25 = BM25(documentos)
        _bm25.carga_s = round(time.perf_counter() - inicio, 3)
        print(f"[corpus_search_v2] BM25: {len(meta)} chunks, "
              f"{len(_bm25.idf)} términos, {_bm25.carga_s} s")
        return _bm25


def cargar_modelo_v2():
    global _modelo, _modelo_info
    if _modelo is not None:
        return _modelo_info

    with _lock:
        if _modelo is not None:
            return _modelo_info

        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from sentence_transformers import SentenceTransformer

        nombre = os.environ.get("MHUB_V2_EMBEDDING_MODEL", MODELO_DEFECTO)
        inicio = time.perf_counter()
        modelo = SentenceTransformer(nombre, device="cpu")
        _modelo = modelo
        _modelo_info = {
            "nombre": nombre,
            "dimensiones": modelo.get_sentence_embedding_dimension(),
            "max_seq_length": modelo.max_seq_length,
            "prefijo_query": "query: " if "e5" in nombre.lower() else "",
            "carga_s": round(time.perf_counter() - inicio, 3),
        }
        print(f"[corpus_search_v2] modelo: {nombre} "
              f"({_modelo_info['dimensiones']} dims, "
              f"{_modelo_info['max_seq_length']} tokens) en "
              f"{_modelo_info['carga_s']} s")
        return _modelo_info


def cargar_reranker():
    global _reranker, _reranker_error
    if os.environ.get("MHUB_RERANKER", "1").strip().lower() in ("0", "false", "no"):
        return None
    if _reranker is not None:
        return _reranker
    if _reranker_error:
        return None

    with _lock:
        if _reranker is not None:
            return _reranker
        if _reranker_error:
            return None
        try:
            from sentence_transformers import CrossEncoder

            nombre = os.environ.get("MHUB_RERANKER_MODEL", RERANKER_DEFECTO)
            inicio = time.perf_counter()
            try:
                _reranker = CrossEncoder(nombre, device="cpu", max_length=256)
            except TypeError:
                _reranker = CrossEncoder(nombre, device="cpu")
                _reranker.max_length = 256
            print(f"[corpus_search_v2] reranker: {nombre} en "
                  f"{time.perf_counter() - inicio:.2f} s")
        except Exception as error:
            _reranker_error = str(error)
            print(f"[corpus_search_v2] reranker no disponible: {error}")
            return None
    return _reranker


# ------------------------------------------------------------------ salida

def _fila(meta, score, modo, rank, **extra):
    fila = {
        "id_fragmento": meta["id_fragmento_v2"],
        "id_fragmento_v2": meta["id_fragmento_v2"],
        "id_documento": meta["id_documento"],
        "texto": meta["texto"],
        "documento": meta["documento"],
        "pagina": meta["pagina"],
        "fuente": meta["fuente"],
        "score": float(score),
        "modo": modo,
        "rank": rank,
        "fallback": False,
        "version": VERSION,
    }
    fila.update(extra)
    return fila


def _pesos_bm25(texto):
    pesos = Counter()
    for token in tokenizar(texto):
        pesos[token] = max(pesos[token], 2.0)
    for expansion in expansion_consultas.expandir(texto):
        for token in tokenizar(expansion):
            pesos[token] = max(pesos[token], 1.0)
    return dict(pesos)


def _es_definicion(texto):
    normalizado = expansion_consultas.normalizar(texto)
    return any(
        marca in normalizado
        for marca in ("que es", "que son", "que significa", "definicion", "concepto")
    )


def buscar_bm25(texto, limite=TOP_K_DEFECTO):
    limite = max(1, min(int(limite), 100))
    bm25 = cargar_bm25()
    pesos = _pesos_bm25(texto)
    if not pesos:
        return []

    expansiones = expansion_consultas.expandir(texto)
    frases_bonus = [(expansion, 12.0) for expansion in expansiones]
    frase = expansion_consultas.frase_consulta(texto)
    if 2 <= len(frase.split()) <= 10:
        frases_bonus.append((frase, 6.0))
    elif len(frase.split()) == 1:
        frases_bonus.append((frase, 4.0))

    normalizado = expansion_consultas.normalizar(texto)
    titulos_bonus = []
    for sigla, expansion in expansion_consultas.ACRONIMOS.items():
        if re.search(rf"\b{re.escape(sigla)}\b", normalizado):
            titulos_bonus.append((expansion_consultas.normalizar(expansion), 10.0))
    if 2 <= len(frase.split()) <= 12:
        titulos_bonus.append((expansion_consultas.normalizar(frase), 10.0))

    definiciones = []
    if _es_definicion(texto):
        candidatas = [frase] + expansiones
        definiciones = [(candidata, 8.0) for candidata in candidatas if candidata]

    pares = bm25.buscar(
        pesos, limite, frases_bonus, titulos_bonus, definiciones
    )
    salida = []
    for rank, (score, pos) in enumerate(pares, 1):
        salida.append(_fila(_meta_bm25[pos], score, "bm25", rank,
                            score_bm25=float(score)))
    return salida


def buscar_embedding(texto, limite=TOP_K_DEFECTO):
    limite = max(1, min(int(limite), 100))
    indice = cargar_indice_v2()
    info = cargar_modelo_v2()
    consulta = info["prefijo_query"] + expansion_consultas.texto_expandido(texto)
    vector = _modelo.encode(
        [consulta],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0].astype("float32")
    scores = indice["matriz"] @ vector
    orden = scores.argsort()[::-1][:limite]
    return [
        _fila(indice["meta"][int(pos)], float(scores[pos]), "embedding", rank,
              score_embedding=float(scores[pos]))
        for rank, pos in enumerate(orden, 1)
    ]


def buscar_fulltext(texto, limite=TOP_K_DEFECTO):
    limite = max(1, min(int(limite), 100))
    filas = ejecutar_select("""
        SELECT f.id_fragmento_v2, f.id_documento, f.texto, f.pagina, f.orden,
               d.nombre AS documento, fu.nombre AS fuente,
               MATCH(f.texto) AGAINST (%s IN NATURAL LANGUAGE MODE) AS score
        FROM fragmentos_documentos_v2 f
        JOIN documentos d ON d.id_documento = f.id_documento
        JOIN fuentes fu ON fu.id_fuente = d.id_fuente
        WHERE f.texto IS NOT NULL AND TRIM(f.texto) <> ''
          AND MATCH(f.texto) AGAINST (%s IN NATURAL LANGUAGE MODE)
        ORDER BY score DESC
        LIMIT %s
    """, database="HUBDATOS", params=(texto, texto, limite))
    salida = []
    for rank, fila in enumerate(filas, 1):
        meta = _meta_desde_fila(fila)
        salida.append(_fila(meta, fila["score"], "fulltext", rank,
                            score_lexico=float(fila["score"])))
    return salida


def _fusionar_rrf(listas, k=60):
    fusion = {}
    for lista, peso, clave in listas:
        for fila in lista:
            item = fusion.get(fila["id_fragmento_v2"])
            if item is None:
                item = {
                    **fila,
                    "score": 0.0,
                    "score_bm25": 0.0,
                    "score_embedding": 0.0,
                }
                fusion[fila["id_fragmento_v2"]] = item
            item[f"score_{clave}"] = fila["score"]
            item["score"] += peso / (k + fila["rank"])
    return sorted(
        fusion.values(),
        key=lambda f: (
            -f["score"],
            -f.get("score_embedding", 0.0),
            -f.get("score_bm25", 0.0),
        ),
    )


def _rerank(texto, candidatos):
    reranker = cargar_reranker()
    if reranker is None or not candidatos:
        return None
    try:
        import numpy as np

        pares = [(texto, c["texto"]) for c in candidatos]
        scores = reranker.predict(
            pares,
            batch_size=_entero_env("MHUB_RERANK_BATCH", 16),
            show_progress_bar=False,
        )
        scores = np.asarray(scores).reshape(len(candidatos), -1)[:, -1]
        for candidato, score in zip(candidatos, scores):
            candidato["score_rerank"] = float(score)
            candidato["score"] = float(score)
            candidato["rerank"] = True
        return sorted(candidatos, key=lambda c: -c["score_rerank"])
    except Exception as error:
        print(f"[corpus_search_v2] reranker falló: {error}")
        return None


def _dedup_pagina(candidatos, limite):
    salida = []
    vistos = set()
    for candidato in candidatos:
        clave = (candidato.get("id_documento"), candidato.get("pagina"))
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(candidato)
        if len(salida) >= limite:
            break
    return salida


def buscar_hibrido(texto, limite=TOP_K_DEFECTO, rerank=False):
    limite = max(1, min(int(limite), 100))
    candidatos_n = max(limite * 10, _entero_env("MHUB_V2_CANDIDATOS", 40))
    lexicos = buscar_bm25(texto, candidatos_n)
    semanticos = buscar_embedding(texto, candidatos_n)

    w_lex = _float_env("MHUB_RRF_LEX", 2.0)
    w_sem = _float_env("MHUB_RRF_SEM", 1.0)
    k_rrf = _entero_env("MHUB_HYBRID_K", RRF_K_DEFECTO)
    fusion = _fusionar_rrf(
        [(lexicos, w_lex, "bm25"), (semanticos, w_sem, "embedding")],
        k=k_rrf,
    )

    if rerank:
        top_n = max(limite, _entero_env("MHUB_RERANK_TOP_N", 10))
        reordenados = _rerank(texto, fusion[:top_n])
        if reordenados is not None:
            fusion = reordenados + fusion[top_n:]

    salida = _dedup_pagina(fusion, limite)
    modo_final = "hybrid_rerank" if (rerank and salida and salida[0].get("rerank")) else "hybrid"
    for rank, fila in enumerate(salida, 1):
        fila = dict(fila)
        fila["rank"] = rank
        fila["modo"] = modo_final
        fila["fallback"] = False
        fila["version"] = VERSION
        salida[rank - 1] = fila
    return salida


def buscar_corpus(texto, limite=None, modo=None):
    """Punto de entrada v2."""
    texto = str(texto or "").strip()
    if limite is None:
        limite = _entero_env("MHUB_CORPUS_TOP_K", TOP_K_DEFECTO)
    if len(texto) < 4:
        _registrar_ultima(modo or "hybrid", modo or "hybrid")
        return []

    solicitado = (modo or os.environ.get("MHUB_V2_MODE") or "hybrid").strip().lower()
    if solicitado not in MODOS:
        solicitado = "hybrid"
    if solicitado == "hybrid_rrf":
        solicitado = "hybrid"
    if solicitado == "hybrid_rerank" and os.environ.get("MHUB_RERANKER", "1").strip().lower() in ("0", "false", "no"):
        solicitado = "hybrid"

    def _fallback(motivo):
        print(f"[corpus_search_v2] fallback ({solicitado}): {motivo}")
        try:
            filas = buscar_bm25(texto, limite)
            efectivo = "bm25"
        except Exception as error_bm25:
            print(f"[corpus_search_v2] BM25 también falló: {error_bm25}")
            try:
                filas = buscar_fulltext(texto, limite)
                efectivo = "fulltext"
            except Exception as error_ft:
                print(f"[corpus_search_v2] fulltext también falló: {error_ft}")
                filas = []
                efectivo = "none"
        for fila in filas:
            fila["fallback"] = True
        _registrar_ultima(solicitado, efectivo, fallback=True, motivo=motivo)
        return filas

    try:
        if solicitado == "fulltext":
            filas = buscar_fulltext(texto, limite)
            _registrar_ultima(solicitado, "fulltext")
        elif solicitado == "bm25":
            filas = buscar_bm25(texto, limite)
            _registrar_ultima(solicitado, "bm25")
        elif solicitado == "embedding":
            filas = buscar_embedding(texto, limite)
            _registrar_ultima(solicitado, "embedding")
        elif solicitado == "hybrid":
            filas = buscar_hibrido(texto, limite, rerank=False)
            _registrar_ultima(solicitado, "hybrid", rerank=False)
        else:
            filas = buscar_hibrido(texto, limite, rerank=True)
            hizo_rerank = bool(filas and filas[0].get("rerank"))
            _registrar_ultima(
                solicitado,
                "hybrid_rerank" if hizo_rerank else "hybrid",
                rerank=hizo_rerank,
            )
        return filas
    except Exception as error:
        return _fallback(str(error))


def estado():
    """Diagnóstico de la v2 sin cargar modelos si no hace falta."""
    estado = {
        "version": VERSION,
        "modo_por_defecto": os.environ.get("MHUB_V2_MODE", "hybrid"),
        "disponible": False,
    }
    try:
        bm25 = cargar_bm25()
        estado["bm25"] = {
            "chunks": len(_meta_bm25),
            "terminos": len(bm25.idf),
            "carga_s": bm25.carga_s,
        }
        estado["disponible"] = True
    except Exception as error:
        estado["bm25_error"] = str(error)

    try:
        indice = cargar_indice_v2()
        estado["embeddings"] = {
            "chunks": len(indice["meta"]),
            "dimensiones": indice["dimensiones"],
            "modelo": indice["modelo"],
            "carga_s": indice["carga_s"],
        }
    except Exception as error:
        estado["embeddings_error"] = str(error)

    if _modelo_info:
        estado["modelo"] = _modelo_info
    if _reranker is not None:
        estado["reranker"] = {"disponible": True,
                              "modelo": os.environ.get("MHUB_RERANKER_MODEL", RERANKER_DEFECTO)}
    elif _reranker_error:
        estado["reranker"] = {"disponible": False, "detalle": _reranker_error}
    return estado


def precargar():
    """Carga índice, BM25 y modelo. El reranker es opcional."""
    try:
        cargar_bm25()
        cargar_indice_v2()
        cargar_modelo_v2()
        if os.environ.get("MHUB_PRECARGAR_RERANKER", "0").strip().lower() in ("1", "true", "si"):
            cargar_reranker()
    except Exception as error:
        print(f"[corpus_search_v2] precarga incompleta: {error}")
    return estado()
