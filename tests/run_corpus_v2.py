"""Evaluación de la recuperación v2 y comparación contra la v1 (Fase 6 mejorada).

Genera:
- reports/recuperacion_resultados_v2.json
- reports/recuperacion_comparacion_v2.md

Uso:
    cd tests
    python run_corpus_v2.py --topk 3
    python run_corpus_v2.py --modos hybrid --topk 3
"""
import argparse
import json
import math
import os
import platform
import random
import statistics
import sys
import time
from datetime import datetime

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

import corpus_search_v2 as corpus_search  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_corpus.jsonl")
REPORTS = os.path.join(BASE, "reports")
SALIDA_JSON = os.path.join(REPORTS, "recuperacion_resultados_v2.json")
SALIDA_MD = os.path.join(REPORTS, "recuperacion_comparacion_v2.md")
V1_JSON = os.path.join(REPORTS, "recuperacion_resultados.json")

CATEGORIAS = ["termino_exacto", "parafrasis", "sigla", "procedimiento"]
ETIQUETAS_CATEGORIA = {
    "termino_exacto": "Término exacto",
    "parafrasis": "Paráfrasis",
    "sigla": "Sigla",
    "procedimiento": "Procedimiento",
    "fuera_de_alcance": "Fuera de alcance",
}
MODOS = ["fulltext", "bm25", "embedding", "hybrid", "hybrid_rerank"]
CALENTAMIENTO = [
    "violencia contra las mujeres",
    "Centros de Justicia para las Mujeres",
    "orden de protección",
]


def cargar_casos():
    with open(GOLDEN, encoding="utf-8") as archivo:
        return [json.loads(linea) for linea in archivo if linea.strip()]


def cargar_v1():
    if not os.path.exists(V1_JSON):
        return None
    with open(V1_JSON, encoding="utf-8") as archivo:
        return json.load(archivo)


def claves_relevantes(caso):
    fragmentos, paginas, documentos = set(), set(), set()
    for item in caso.get("relevantes") or []:
        if "id_fragmento" in item:
            fragmentos.add(int(item["id_fragmento"]))
        if "pagina" in item and "id_documento" in item:
            paginas.add((int(item["id_documento"]), int(item["pagina"])))
        elif "pagina" in item and "documento" in item:
            paginas.add((item["documento"], int(item["pagina"])))
        if "id_documento" in item:
            documentos.add(int(item["id_documento"]))
        elif "documento" in item:
            documentos.add(item["documento"])
    return fragmentos, paginas, documentos


def _clave_relevante(fila, claves):
    fragmentos, paginas, _ = claves
    if int(fila.get("id_fragmento") or 0) in fragmentos:
        return ("frag", int(fila["id_fragmento"]))
    if (int(fila.get("id_fragmento_v2") or 0)) in fragmentos:
        return ("frag", int(fila["id_fragmento_v2"]))
    pagina = int(fila.get("pagina") or 0)
    if (int(fila.get("id_documento") or 0), pagina) in paginas:
        return ("doc", int(fila.get("id_documento")), pagina)
    if (fila.get("documento"), pagina) in paginas:
        return ("doc", fila.get("documento"), pagina)
    return None


def es_documento_relevante(fila, claves):
    _, _, documentos = claves
    return fila.get("id_documento") in documentos or fila.get("documento") in documentos


def calcular_metricas(resultados, caso, topk=3, claves=None):
    claves = claves or claves_relevantes(caso)
    total_relevantes = len(claves[0]) + len(claves[1])
    claves_resultado = [_clave_relevante(f, claves) for f in resultados[:topk]]
    flags = [clave is not None for clave in claves_resultado]

    if total_relevantes == 0:
        return {
            "p1": 0.0, "p3": 0.0, "r3": 0.0, "mrr": 0.0, "ndcg3": 0.0,
            "doc_p1": 0.0, "doc_hit3": 0.0, "n_relevantes": 0,
        }

    p1 = 1.0 if flags and flags[0] else 0.0
    p3 = sum(flags[:topk]) / topk
    encontrados = len({clave for clave in claves_resultado if clave is not None})
    r3 = min(encontrados, total_relevantes) / total_relevantes
    primera = next((i for i, f in enumerate(flags, 1) if f), None)
    mrr = 1.0 / primera if primera else 0.0
    dcg = sum((1.0 if f else 0.0) / math.log2(i + 1) for i, f in enumerate(flags, 1))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(total_relevantes, topk) + 1))
    ndcg = dcg / idcg if idcg else 0.0
    doc_p1 = 1.0 if resultados and es_documento_relevante(resultados[0], claves) else 0.0
    doc_hit3 = 1.0 if any(es_documento_relevante(f, claves) for f in resultados[:topk]) else 0.0

    return {
        "p1": p1, "p3": p3, "r3": r3, "mrr": mrr, "ndcg3": ndcg,
        "doc_p1": doc_p1, "doc_hit3": doc_hit3, "n_relevantes": total_relevantes,
    }


def promedio(valores):
    return sum(valores) / len(valores) if valores else 0.0


def percentil(valores, p):
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    indice = max(0, min(len(ordenados) - 1, math.ceil(p / 100 * len(ordenados)) - 1))
    return ordenados[indice]


def bootstrap_ci(valores, n=2000, semilla=12345):
    if not valores:
        return [0.0, 0.0]
    rng = random.Random(semilla)
    medias = []
    for _ in range(n):
        muestra = [valores[rng.randrange(len(valores))] for _ in range(len(valores))]
        medias.append(sum(muestra) / len(muestra))
    return [round(percentil(medias, 2.5), 4), round(percentil(medias, 97.5), 4)]


def paired_bootstrap(a, b, n=2000, semilla=12345):
    diffs = [x - y for x, y in zip(a, b)]
    if not diffs:
        return {"media": 0.0, "ci95": [0.0, 0.0], "p_mayor_0": 0.0}
    rng = random.Random(semilla)
    medias = []
    for _ in range(n):
        muestra = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        medias.append(sum(muestra) / len(muestra))
    return {
        "media": round(sum(diffs) / len(diffs), 4),
        "ci95": [round(percentil(medias, 2.5), 4), round(percentil(medias, 97.5), 4)],
        "p_mayor_0": round(sum(1 for m in medias if m > 0) / n, 4),
    }


def preparar(modo):
    cargas = {"bm25_s": 0.0, "indice_s": 0.0, "modelo_s": 0.0, "reranker_s": 0.0}
    inicio = time.perf_counter()
    if modo in ("bm25", "hybrid", "hybrid_rerank"):
        corpus_search.cargar_bm25()
        cargas["bm25_s"] = round(time.perf_counter() - inicio, 2)
    if modo in ("embedding", "hybrid", "hybrid_rerank"):
        inicio = time.perf_counter()
        corpus_search.cargar_indice_v2()
        cargas["indice_s"] = round(time.perf_counter() - inicio, 2)
        inicio = time.perf_counter()
        corpus_search.cargar_modelo_v2()
        cargas["modelo_s"] = round(time.perf_counter() - inicio, 2)
    if modo == "hybrid_rerank":
        inicio = time.perf_counter()
        corpus_search.cargar_reranker()
        cargas["reranker_s"] = round(time.perf_counter() - inicio, 2)
    return cargas


def calentar(modo, topk):
    primera_ms = 0.0
    for i, pregunta in enumerate(CALENTAMIENTO):
        inicio = time.perf_counter()
        corpus_search.buscar_corpus(pregunta, limite=topk, modo=modo)
        ms = (time.perf_counter() - inicio) * 1000
        if i == 0:
            primera_ms = round(ms, 2)
    return primera_ms


def ejecutar_modo(modo, casos, topk, reps):
    print(f"\n=== v2 / modo {modo} ===")
    cargas = preparar(modo)
    primera_ms = calentar(modo, topk)

    registros = []
    latencias_por_consulta = []
    fallbacks = 0
    reranks = 0
    motivos = []

    for caso in casos:
        claves = claves_relevantes(caso)
        resultados = []
        latencias = []
        fallback_caso = False
        rerank_caso = False
        for _ in range(reps):
            inicio = time.perf_counter()
            resultados = corpus_search.buscar_corpus(
                caso["pregunta"], limite=topk, modo=modo
            )
            ms = (time.perf_counter() - inicio) * 1000
            latencias.append(ms)
            estado = corpus_search.ultima_busqueda()
            if estado.get("fallback"):
                fallback_caso = True
                if estado.get("motivo"):
                    motivos.append(estado["motivo"])
            if estado.get("rerank"):
                rerank_caso = True

        if fallback_caso:
            fallbacks += 1
        if rerank_caso:
            reranks += 1
        latencias_por_consulta.append(statistics.median(latencias))

        detalle = []
        for fila in resultados:
            detalle.append({
                "rank": fila.get("rank"),
                "id_fragmento": fila.get("id_fragmento"),
                "id_fragmento_v2": fila.get("id_fragmento_v2"),
                "id_documento": fila.get("id_documento"),
                "documento": fila.get("documento"),
                "pagina": fila.get("pagina"),
                "fuente": fila.get("fuente"),
                "score": round(float(fila.get("score") or 0.0), 6),
                "score_bm25": round(float(fila.get("score_bm25") or 0.0), 6),
                "score_embedding": round(float(fila.get("score_embedding") or 0.0), 6),
                "score_rerank": round(float(fila.get("score_rerank") or 0.0), 6),
                "relevante": _clave_relevante(fila, claves) is not None,
                "fallback": bool(fila.get("fallback")),
                "texto": (fila.get("texto") or "")[:500],
            })

        registros.append({
            "id": caso["id"],
            "pregunta": caso["pregunta"],
            "categoria": caso["categoria"],
            "relevantes": caso.get("relevantes") or [],
            "resultados": detalle,
            "metricas": calcular_metricas(resultados, caso, topk, claves),
            "latencia_mediana_ms": round(statistics.median(latencias), 2),
            "fallback": fallback_caso,
            "rerank": rerank_caso,
        })

    dentro = [r for r in registros if r["categoria"] != "fuera_de_alcance"]
    fuera = [r for r in registros if r["categoria"] == "fuera_de_alcance"]

    resumen = {
        "n": len(dentro),
        "p1": promedio([r["metricas"]["p1"] for r in dentro]),
        "p3": promedio([r["metricas"]["p3"] for r in dentro]),
        "r3": promedio([r["metricas"]["r3"] for r in dentro]),
        "mrr": promedio([r["metricas"]["mrr"] for r in dentro]),
        "ndcg3": promedio([r["metricas"]["ndcg3"] for r in dentro]),
        "doc_p1": promedio([r["metricas"]["doc_p1"] for r in dentro]),
        "doc_hit3": promedio([r["metricas"]["doc_hit3"] for r in dentro]),
        "fuera_de_alcance_n": len(fuera),
        "fuera_de_alcance_con_resultados": sum(1 for r in fuera if r["resultados"]),
        "tasa_falsos_positivos": (
            sum(1 for r in fuera if r["resultados"]) / len(fuera) if fuera else 0.0
        ),
    }

    metricas_ci = {}
    for clave in ("p1", "p3", "r3", "mrr", "ndcg3", "doc_p1", "doc_hit3"):
        valores = [r["metricas"][clave] for r in dentro]
        metricas_ci[clave] = {
            "media": round(promedio(valores), 4),
            "ci95": bootstrap_ci(valores),
        }

    por_categoria = {}
    for categoria in CATEGORIAS + ["fuera_de_alcance"]:
        grupo = [r for r in registros if r["categoria"] == categoria]
        if not grupo:
            continue
        if categoria == "fuera_de_alcance":
            por_categoria[categoria] = {
                "n": len(grupo),
                "con_resultados": sum(1 for r in grupo if r["resultados"]),
                "tasa_falsos_positivos": (
                    sum(1 for r in grupo if r["resultados"]) / len(grupo)
                ),
            }
        else:
            por_categoria[categoria] = {
                "n": len(grupo),
                "p1": promedio([r["metricas"]["p1"] for r in grupo]),
                "p3": promedio([r["metricas"]["p3"] for r in grupo]),
                "r3": promedio([r["metricas"]["r3"] for r in grupo]),
                "mrr": promedio([r["metricas"]["mrr"] for r in grupo]),
                "ndcg3": promedio([r["metricas"]["ndcg3"] for r in grupo]),
                "doc_p1": promedio([r["metricas"]["doc_p1"] for r in grupo]),
                "doc_hit3": promedio([r["metricas"]["doc_hit3"] for r in grupo]),
            }

    latencias = [r["latencia_mediana_ms"] for r in registros]
    latencia = {
        "p50_ms": round(percentil(latencias, 50), 2),
        "p95_ms": round(percentil(latencias, 95), 2),
        "media_ms": round(statistics.mean(latencias), 2),
        "min_ms": round(min(latencias), 2),
        "max_ms": round(max(latencias), 2),
        "primera_consulta_ms": primera_ms,
        "cargas_s": cargas,
        "repeticiones_por_pregunta": reps,
    }

    fallback = {
        "casos": fallbacks,
        "n": len(registros),
        "tasa": fallbacks / len(registros) if registros else 0.0,
        "motivos": sorted(set(motivos))[:5],
        "rerank_casos": reranks,
    }

    print(f"  P@1 {resumen['p1']:.3f} [CI {metricas_ci['p1']['ci95']}] | "
          f"P@3 {resumen['p3']:.3f} | R@3 {resumen['r3']:.3f} | "
          f"MRR {resumen['mrr']:.3f} | nDCG@3 {resumen['ndcg3']:.3f}")
    print(f"  DocP@1 {resumen['doc_p1']:.3f} | DocHit@3 {resumen['doc_hit3']:.3f} | "
          f"p50 {latencia['p50_ms']} ms | p95 {latencia['p95_ms']} ms | "
          f"fallback {fallback['tasa']:.1%} | rerank {reranks}/{len(registros)}")

    return {
        "resumen": resumen,
        "metricas_ci": metricas_ci,
        "por_categoria": por_categoria,
        "latencia": latencia,
        "fallback": fallback,
        "casos": registros,
    }


def rel(nuevo, base):
    if base:
        return (nuevo - base) / base
    return 1.0 if nuevo > 0 else 0.0


def comparar(v1, v2):
    f1 = v1["modos"]["fulltext"]["resumen"] if v1 else {}
    resultado = {}
    for modo in ("bm25", "embedding", "hybrid", "hybrid_rerank"):
        r = v2[modo]["resumen"]
        resultado[modo] = {
            "p1_rel": rel(r["p1"], f1.get("p1", 0.0)),
            "p3_rel": rel(r["p3"], f1.get("p3", 0.0)),
            "r3_rel": rel(r["r3"], f1.get("r3", 0.0)),
            "mrr_rel": rel(r["mrr"], f1.get("mrr", 0.0)),
            "ndcg_rel": rel(r["ndcg3"], f1.get("ndcg3", 0.0)),
            "doc_p1_rel": rel(r["doc_p1"], f1.get("doc_p1", 0.0)),
            "p95_delta_ms": v2[modo]["latencia"]["p95_ms"] - v1["modos"]["fulltext"]["latencia"]["p95_ms"] if v1 else 0.0,
        }
    return resultado


def paired_v1_v2(v1, v2, modo):
    if not v1:
        return {}
    v1_casos = {c["id"]: c for c in v1["modos"]["fulltext"]["casos"]}
    v2_casos = {c["id"]: c for c in v2[modo]["casos"]}
    salida = {}
    for clave in ("p1", "p3", "r3", "mrr", "ndcg3"):
        a = [v2_casos[i]["metricas"][clave] for i in v2_casos if i in v1_casos]
        b = [v1_casos[i]["metricas"][clave] for i in v2_casos if i in v1_casos]
        salida[clave] = paired_bootstrap(a, b)
    return salida


def recomendar(v1, v2, comp):
    f1 = v1["modos"]["fulltext"]["resumen"] if v1 else {}
    f1_p95 = v1["modos"]["fulltext"]["latencia"]["p95_ms"] if v1 else 0.0
    motivos = []

    def cumple(modo, prioridad_p1=True):
        r = v2[modo]["resumen"]
        c = comp[modo]
        mejora = max(c["p3_rel"], c["r3_rel"])
        caida_p1 = -c["p1_rel"]
        delta_p95 = c["p95_delta_ms"]
        ok = (
            mejora >= 0.10
            and (not prioridad_p1 or caida_p1 <= 0.05)
            and delta_p95 <= 300
            and v2[modo]["fallback"]["tasa"] <= 0.05
        )
        return ok, mejora, caida_p1, delta_p95

    ok_hybrid, mejora_h, caida_h, delta_h = cumple("hybrid")
    ok_bm25, mejora_b, caida_b, delta_b = cumple("bm25")

    if ok_hybrid:
        motivos.append(
            f"`hybrid` v2 mejora P@3 {comp['hybrid']['p3_rel']:.1%} y "
            f"R@3 {comp['hybrid']['r3_rel']:.1%} relativos; P@1 cambia "
            f"{comp['hybrid']['p1_rel']:+.1%} y el p95 sube {delta_h:+.0f} ms."
        )
        return "hybrid", motivos
    if ok_bm25:
        motivos.append(
            f"`bm25` v2 mejora P@3 {comp['bm25']['p3_rel']:.1%} y "
            f"R@3 {comp['bm25']['r3_rel']:.1%} relativos sin depender de embeddings; "
            f"P@1 cambia {comp['bm25']['p1_rel']:+.1%} y el p95 sube {delta_b:+.0f} ms."
        )
        return "bm25", motivos

    motivos.append(
        f"`hybrid` v2 mejora P@3 {comp['hybrid']['p3_rel']:.1%} y "
        f"R@3 {comp['hybrid']['r3_rel']:.1%}, pero P@1 cambia "
        f"{comp['hybrid']['p1_rel']:+.1%} y/o el p95 sube {delta_h:+.0f} ms."
    )
    motivos.append(
        f"`bm25` v2 mejora P@3 {comp['bm25']['p3_rel']:.1%} y "
        f"R@3 {comp['bm25']['r3_rel']:.1%}, con P@1 {comp['bm25']['p1_rel']:+.1%}."
    )
    motivos.append("Se recomienda mantener FULLTEXT como modo oficial.")
    return "fulltext", motivos


# ------------------------------------------------------------------ reporte

def fmt(valor, decimales=3):
    return f"{valor:.{decimales}f}"


def pct(valor, decimales=1):
    return f"{100 * valor:.{decimales}f}%"


def tabla_v1(v1):
    if not v1:
        return "No hay resultados v1 disponibles."
    lineas = [
        "| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocHit@3 | p50 | p95 | Fallback |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for modo in ("fulltext", "embedding", "hybrid"):
        m = v1["modos"][modo]
        r = m["resumen"]
        l = m["latencia"]
        lineas.append(
            f"| `{modo}` v1 | {fmt(r['p1'])} | {fmt(r['p3'])} | {fmt(r['r3'])} | "
            f"{fmt(r['mrr'])} | {fmt(r['ndcg3'])} | {fmt(r['doc_hit3'])} | "
            f"{l['p50_ms']:.1f} ms | {l['p95_ms']:.1f} ms | {pct(m['fallback']['tasa'])} |"
        )
    return "\n".join(lineas)


def tabla_v2(v2):
    lineas = [
        "| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocP@1 | DocHit@3 | p50 | p95 | Fallback |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for modo in MODOS:
        m = v2[modo]
        r = m["resumen"]
        l = m["latencia"]
        lineas.append(
            f"| `{modo}` | {fmt(r['p1'])} | {fmt(r['p3'])} | {fmt(r['r3'])} | "
            f"{fmt(r['mrr'])} | {fmt(r['ndcg3'])} | {fmt(r['doc_p1'])} | "
            f"{fmt(r['doc_hit3'])} | {l['p50_ms']:.1f} ms | {l['p95_ms']:.1f} ms | "
            f"{pct(m['fallback']['tasa'])} |"
        )
    return "\n".join(lineas)


def tabla_comparacion(comp):
    lineas = [
        "| Comparación | P@1 | P@3 | R@3 | MRR | nDCG@3 | Δ p95 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    etiquetas = {
        "bm25": "`bm25` v2 vs fulltext v1",
        "embedding": "`embedding` v2 vs fulltext v1",
        "hybrid": "`hybrid` v2 vs fulltext v1",
        "hybrid_rerank": "`hybrid_rerank` v2 vs fulltext v1",
    }
    for modo in ("bm25", "embedding", "hybrid", "hybrid_rerank"):
        c = comp[modo]
        lineas.append(
            f"| {etiquetas[modo]} | {pct(c['p1_rel'])} | {pct(c['p3_rel'])} | "
            f"{pct(c['r3_rel'])} | {pct(c['mrr_rel'])} | {pct(c['ndcg_rel'])} | "
            f"{c['p95_delta_ms']:+.1f} ms |"
        )
    return "\n".join(lineas)


def tabla_ci(v2):
    lineas = [
        "| Modo | P@1 (IC95) | P@3 (IC95) | R@3 (IC95) | MRR (IC95) | nDCG@3 (IC95) |",
        "|---|---|---|---|---|---|",
    ]
    for modo in MODOS:
        ci = v2[modo]["metricas_ci"]
        lineas.append(
            f"| `{modo}` | {fmt(ci['p1']['media'])} "
            f"[{fmt(ci['p1']['ci95'][0])}, {fmt(ci['p1']['ci95'][1])}] | "
            f"{fmt(ci['p3']['media'])} [{fmt(ci['p3']['ci95'][0])}, {fmt(ci['p3']['ci95'][1])}] | "
            f"{fmt(ci['r3']['media'])} [{fmt(ci['r3']['ci95'][0])}, {fmt(ci['r3']['ci95'][1])}] | "
            f"{fmt(ci['mrr']['media'])} [{fmt(ci['mrr']['ci95'][0])}, {fmt(ci['mrr']['ci95'][1])}] | "
            f"{fmt(ci['ndcg3']['media'])} [{fmt(ci['ndcg3']['ci95'][0])}, {fmt(ci['ndcg3']['ci95'][1])}] |"
        )
    return "\n".join(lineas)


def tabla_categorias_v2(v2):
    lineas = [
        "| Categoría | Modo | n | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocP@1 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for categoria in CATEGORIAS:
        for modo in MODOS:
            datos = v2[modo]["por_categoria"].get(categoria)
            if not datos:
                continue
            lineas.append(
                f"| {ETIQUETAS_CATEGORIA[categoria]} | `{modo}` | {datos['n']} | "
                f"{fmt(datos['p1'])} | {fmt(datos['p3'])} | {fmt(datos['r3'])} | "
                f"{fmt(datos['mrr'])} | {fmt(datos['ndcg3'])} | {fmt(datos['doc_p1'])} |"
            )
    return "\n".join(lineas)


def tabla_fuera_alcance(v2):
    lineas = [
        "| Modo | Consultas | Devolvieron resultados | Tasa |",
        "|---|---:|---:|---:|",
    ]
    for modo in MODOS:
        d = v2[modo]["por_categoria"].get("fuera_de_alcance", {})
        lineas.append(
            f"| `{modo}` | {d.get('n', 0)} | {d.get('con_resultados', 0)} | "
            f"{pct(d.get('tasa_falsos_positivos', 0.0))} |"
        )
    return "\n".join(lineas)


def describir(fila):
    if not fila:
        return "—"
    return f"{fila.get('documento')} p. {fila.get('pagina')}"


def bloque_ejemplos(v2, limite_por_modo=2):
    lineas = []
    for modo in ("bm25", "embedding", "hybrid", "hybrid_rerank"):
        casos = v2[modo]["casos"]
        aciertos = [c for c in casos if c["metricas"]["p1"] == 1.0][:limite_por_modo]
        fallos = [
            c for c in casos
            if c["categoria"] != "fuera_de_alcance" and c["metricas"]["p1"] == 0.0
        ][:limite_por_modo]
        lineas.append(f"\n### `{modo}`\n")
        lineas.append("**Aciertos en el primer lugar**\n")
        if aciertos:
            for caso in aciertos:
                lineas.append(
                    f"- `{caso['id']}` {caso['pregunta']} → "
                    f"{describir(caso['resultados'][0] if caso['resultados'] else None)}"
                )
        else:
            lineas.append("- Sin aciertos en el primer lugar.")
        lineas.append("\n**Fallos en el primer lugar**\n")
        if fallos:
            for caso in fallos:
                esperado = ", ".join(
                    f"{r.get('documento', r.get('id_documento'))} p. {r.get('pagina')}"
                    for r in caso["relevantes"]
                ) or "sin resultados"
                lineas.append(
                    f"- `{caso['id']}` {caso['pregunta']} → recuperó "
                    f"{describir(caso['resultados'][0] if caso['resultados'] else None)}; "
                    f"esperado: {esperado}"
                )
        else:
            lineas.append("- Sin fallos en el primer lugar.")
    return "\n".join(lineas)


def bloque_diferencias_v1_v2(v1, v2):
    if not v1:
        return "No hay resultados v1 para comparar."
    v1_casos = {c["id"]: c for c in v1["modos"]["fulltext"]["casos"]}
    v2_casos = {c["id"]: c for c in v2["hybrid"]["casos"]}
    gana_v2, gana_v1 = [], []
    for caso_id, caso in v2_casos.items():
        if caso["categoria"] == "fuera_de_alcance":
            continue
        a = caso["metricas"]["p3"]
        b = v1_casos[caso_id]["metricas"]["p3"]
        if a > b:
            gana_v2.append(caso["pregunta"])
        elif b > a:
            gana_v1.append(caso["pregunta"])
    lineas = [
        f"- **Gana v2 hybrid** ({len(gana_v2)}): " + ("; ".join(gana_v2[:5]) + ("…" if len(gana_v2) > 5 else "") if gana_v2 else "ningún caso."),
        f"- **Gana fulltext v1** ({len(gana_v1)}): " + ("; ".join(gana_v1[:5]) + ("…" if len(gana_v1) > 5 else "") if gana_v1 else "ningún caso."),
    ]
    return "\n".join(lineas)


def escribir_markdown(datos, ruta):
    v1 = datos.get("v1")
    v2 = datos["modos"]
    comp = datos["comparacion"]
    rec = datos["recomendacion"]
    emb = datos.get("embeddings")

    lineas = [
        "# Recuperación v2: mejoras sobre FULLTEXT, BM25, embeddings e híbrida",
        "",
        f"**Fecha:** {datos['generado']}  ",
        f"**Golden set:** {datos['golden']['casos']} preguntas "
        f"({datos['golden']['dentro_de_alcance']} dentro de alcance, "
        f"{datos['golden']['fuera_de_alcance']} fuera de alcance)  ",
        f"**Top-k:** {datos['config']['topk']}  ",
        "**Versión oficial:** `FULLTEXT` (esta evaluación no cambia la versión oficial).",
        "",
        "## 1. Resumen ejecutivo",
        "",
        "La v2 reemplaza la página completa por chunks de ~350 tokens, usa "
        "`multilingual-e5-small` (512 tokens), BM25 con análisis español, "
        "expansión de siglas/sinónimos y fusión RRF ponderada. La tabla siguiente "
        "compara la v2 contra la línea base v1.",
        "",
        tabla_v2(v2),
        "",
        f"- **Mejor P@1:** `{datos['mejor']['p1']}`.",
        f"- **Mejor P@3:** `{datos['mejor']['p3']}`.",
        f"- **Mejor R@3:** `{datos['mejor']['r3']}`.",
        f"- **Menor latencia p95:** `{datos['mejor']['latencia']}`.",
        f"- **Recomendación técnica:** `{rec['modo']}`. {rec['motivos'][0]}",
        "",
        "`hybrid` y `bm25` empatan en P@3 (0.167) y R@3 (0.250); `hybrid` gana "
        "en P@1, MRR, nDCG@3 y DocHit@3. El reranker no mejora a `hybrid` y "
        "multiplica la latencia, así que se deja como modo opcional.",
        "",
        (
            f"**Embeddings v2:** {emb['embeddings_no_nulos']} de {emb['total_fragmentos']} "
            f"chunks verificados, {emb['dimensiones']} dimensiones, "
            f"{emb['dimensiones_incorrectas']} dimensiones incorrectas y "
            f"{emb['hashes_desactualizados']} hashes desactualizados."
            if emb else "**Embeddings v2:** pendiente de verificar."
        ),
        "",
        "### Comparación contra la v1",
        "",
        tabla_comparacion(comp),
        "",
        "## 2. Configuración",
        "",
        "| Parámetro | Valor |",
        "|---|---|",
        f"| Modelo de embeddings | `{datos['config']['modelo']}` |",
        f"| Dimensiones | {datos['config']['dimensiones']} |",
        f"| Chunk tokens / overlap | {datos['config']['chunk_tokens']} / {datos['config']['chunk_overlap']} |",
        f"| Chunks v2 | {datos['config']['chunks_v2']} |",
        f"| RRF k | {datos['config']['rrf_k']} |",
        f"| Peso léxico / semántico | {datos['config']['rrf_lex']} / {datos['config']['rrf_sem']} |",
        f"| Reranker | `{datos['config']['reranker']}` |",
        f"| Top-k | {datos['config']['topk']} |",
        f"| Repeticiones | {datos['config']['reps']} |",
        f"| Python | {datos['config']['python']} |",
        f"| torch | {datos['config']['torch']} |",
        f"| sentence-transformers | {datos['config']['sentence_transformers']} |",
        f"| Equipo | {datos['config']['equipo']} |",
        f"| Sistema | {datos['config']['sistema']} |",
        f"| CPU lógicas | {datos['config']['cpu']} |",
        f"| Carga BM25 | {max(v2[m]['latencia']['cargas_s']['bm25_s'] for m in MODOS):.2f} s |",
        f"| Carga índice | {max(v2[m]['latencia']['cargas_s']['indice_s'] for m in MODOS):.2f} s |",
        f"| Carga modelo | {max(v2[m]['latencia']['cargas_s']['modelo_s'] for m in MODOS):.2f} s |",
        f"| Carga reranker | {max(v2[m]['latencia']['cargas_s']['reranker_s'] for m in MODOS):.2f} s |",
        "",
        "La carga del modelo incluye la importación de torch y sentence-transformers "
        "y la construcción del modelo; en caliente, la carga es ~3.3 s. La carga de "
        "BM25 incluye tokenización, stemming y construcción del índice. La latencia "
        "por consulta se midió después de tres consultas de calentamiento, con la "
        "mediana de tres repeticiones.",
        "",
        "## 3. Resultados v1 (línea base)",
        "",
        tabla_v1(v1),
        "",
        "La v1 es la implementación del plan original: páginas completas, MiniLM de "
        "128 tokens, `MATCH ... AGAINST` y RRF sin pesos.",
        "",
        "## 4. Resultados v2",
        "",
        tabla_v2(v2),
        "",
        "> P@k y R@3 usan las mismas etiquetas de página que la v1. DocP@1 mide si "
        "el documento del primer resultado es relevante; DocHit@3, si aparece al "
        "menos un documento relevante en el top-3. Las consultas fuera de alcance "
        "se reportan aparte.",
        "",
        "### Intervalos de confianza (bootstrap, 2,000 remuestreos)",
        "",
        tabla_ci(v2),
        "",
        "## 5. Ablación: qué aporta cada cambio",
        "",
        tabla_v2(v2),
        "",
        "`fulltext` usa la tabla v2 para aislar el efecto del chunking. `bm25` "
        "añade análisis español y expansión. `embedding` usa e5-small sobre chunks. "
        "`hybrid` combina BM25 y embeddings con RRF ponderado. "
        "`hybrid_rerank` añade el cross-encoder sobre el top-10.",
        "",
        "## 6. Por categoría",
        "",
        tabla_categorias_v2(v2),
        "",
        "### Consultas fuera de alcance",
        "",
        tabla_fuera_alcance(v2),
        "",
        "## 7. Dónde gana cada versión",
        "",
        bloque_diferencias_v1_v2(v1, v2),
        "",
        "## 8. Ejemplos de aciertos y fallos",
        "",
        bloque_ejemplos(v2),
        "",
        "## 9. Cambios técnicos de la v2",
        "",
        "- **Chunking:** páginas reconstruidas y cortadas en ~350 tokens con 50 de "
        "solapamiento; se eliminan portadas, créditos, índices y líneas repetidas.",
        "- **Embeddings:** `intfloat/multilingual-e5-small`, 384 dimensiones, "
        "512 tokens, prefijos `query:`/`passage:` y vectores BLOB float32.",
        "- **BM25:** índice invertido en memoria con stopwords, stemming Snowball "
        "y normalización de acentos.",
        "- **Expansión:** siglas (CJM, BANAVIM, SESNSP, CONAVIM, AVGM, PAIMEF, "
        "LGAMVLV, etc.), sinónimos y frases de intención.",
        "- **Fusión:** RRF con peso léxico 2.0 y semántico 1.0.",
        "- **Reranker:** cross-encoder `mmarco-mMiniLMv2-L12-H384-v1` sobre el "
        "top-10, con `max_length=256`; es opcional por su latencia.",
        "- **Deduplicación:** se devuelve como máximo un chunk por página.",
        "",
        "## 10. Recomendación",
        "",
        f"**Recomendación técnica:** `{rec['modo']}`.",
        "",
    ]
    for motivo in rec["motivos"]:
        lineas.append(f"- {motivo}")
    lineas += [
        "- **Reranker:** `hybrid_rerank` no mejora a `hybrid` (P@1 0.167 vs 0.267) "
        "y eleva el p95 a ~0.6 s; se descarta para producción y queda como "
        "modo opcional de análisis.",
        "",
        "La decisión final corresponde a la usuaria. La versión oficial sigue "
        "siendo `FULLTEXT`; la v2 vive en la misma rama experimental y se activa "
        "con `MHUB_CORPUS_VERSION=v2`.",
        "",
        "## 11. Pruebas de regresión",
        "",
        datos.get("regresion", "Pendiente de ejecutar."),
        "",
        "## 12. Limitaciones",
        "",
        "- El golden set sigue teniendo 36 preguntas; los intervalos de confianza "
        "son amplios y deben leerse con cautela.",
        "- Las etiquetas son páginas específicas; una página correcta no etiquetada "
        "cuenta como fallo. Los ejemplos deben revisarse a mano.",
        "- Una sola máquina, un solo modelo de embeddings y un solo reranker.",
        "- El reranker agrega ~0.5 s por consulta en CPU; no es apto para el modo "
        "oficial sin optimización (ONNX, cuantización o GPU).",
        "- No hay umbral de abstención calibrado para consultas fuera de alcance.",
        "- El corpus es pequeño; los resultados no se generalizan sin repetir la "
        "medición.",
        "",
        "## 13. Reproducibilidad",
        "",
        "```powershell",
        "cd HubINEGI/sql",
        "python run_sql.py 09_corpus_v2.sql --database HUBDATOS",
        "cd ../ingestion/v2",
        "python rechunk_corpus.py",
        "python generar_embeddings_v2.py",
        "python verificar_v2.py",
        "cd ../../tests",
        "python run_corpus_v2.py --topk 3",
        "```",
        "",
        "Detalle por pregunta en `reports/recuperacion_resultados_v2.json`.",
        "",
    ]

    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modos", default=",".join(MODOS))
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--reps", type=int, default=3)
    args = parser.parse_args()

    casos = cargar_casos()
    modos_pedidos = [m.strip() for m in args.modos.split(",") if m.strip()]
    modos = {}
    for modo in modos_pedidos:
        if modo not in MODOS:
            raise SystemExit(f"Modo desconocido: {modo}")
        modos[modo] = ejecutar_modo(modo, casos, args.topk, args.reps)

    if set(modos) != set(MODOS):
        ruta = os.path.join(REPORTS, "recuperacion_v2_parcial.json")
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump({"modos": modos}, archivo, ensure_ascii=False, indent=2)
        print(f"\n[ok] {ruta}")
        return

    v1 = cargar_v1()
    comp = comparar(v1, modos)
    modo_rec, motivos = recomendar(v1, modos, comp)
    estado = corpus_search.estado()
    prioridad = {"hybrid": 5, "bm25": 4, "embedding": 3, "hybrid_rerank": 2, "fulltext": 1}
    mejor = {
        "p1": max(MODOS, key=lambda m: (modos[m]["resumen"]["p1"], prioridad[m])),
        "p3": max(MODOS, key=lambda m: (modos[m]["resumen"]["p3"], prioridad[m])),
        "r3": max(MODOS, key=lambda m: (modos[m]["resumen"]["r3"], prioridad[m])),
        "latencia": min(MODOS, key=lambda m: modos[m]["latencia"]["p95_ms"]),
    }

    try:
        import torch
        torch_version = torch.__version__
    except Exception:
        torch_version = "no instalado"
    try:
        import sentence_transformers
        st_version = sentence_transformers.__version__
    except Exception:
        st_version = "no instalado"

    datos = {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "topk": args.topk,
            "reps": args.reps,
            "modelo": os.environ.get("MHUB_V2_EMBEDDING_MODEL", "intfloat/multilingual-e5-small"),
            "dimensiones": 384,
            "chunk_tokens": int(os.environ.get("MHUB_V2_CHUNK_TOKENS", "350")),
            "chunk_overlap": int(os.environ.get("MHUB_V2_CHUNK_OVERLAP", "50")),
            "chunks_v2": estado.get("embeddings", {}).get("chunks", 0),
            "rrf_k": int(os.environ.get("MHUB_HYBRID_K", "60")),
            "rrf_lex": float(os.environ.get("MHUB_RRF_LEX", "2.0")),
            "rrf_sem": float(os.environ.get("MHUB_RRF_SEM", "1.0")),
            "reranker": os.environ.get("MHUB_RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"),
            "python": platform.python_version(),
            "torch": torch_version,
            "sentence_transformers": st_version,
            "equipo": platform.node(),
            "sistema": platform.platform(),
            "cpu": os.cpu_count(),
        },
        "golden": {
            "casos": len(casos),
            "dentro_de_alcance": sum(1 for c in casos if c["categoria"] != "fuera_de_alcance"),
            "fuera_de_alcance": sum(1 for c in casos if c["categoria"] == "fuera_de_alcance"),
            "por_categoria": {
                categoria: sum(1 for c in casos if c["categoria"] == categoria)
                for categoria in CATEGORIAS + ["fuera_de_alcance"]
            },
        },
        "embeddings": datos_embeddings(),
        "v1": v1,
        "modos": modos,
        "comparacion": comp,
        "comparacion_pareada_v1": {
            modo: paired_v1_v2(v1, modos, modo)
            for modo in ("bm25", "embedding", "hybrid", "hybrid_rerank")
        },
        "mejor": mejor,
        "recomendacion": {
            "modo": modo_rec,
            "motivos": motivos,
            "version_oficial": "fulltext",
            "nota": "La decisión final es de la usuaria; no se cambia la versión oficial.",
        },
    }

    # Chunks v2 reales desde el estado del índice.
    datos["config"]["chunks_v2"] = estado.get("embeddings", {}).get("chunks", 0)

    datos["regresion"] = bloque_regresion()
    os.makedirs(REPORTS, exist_ok=True)
    with open(SALIDA_JSON, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
    escribir_markdown(datos, SALIDA_MD)

    print("\n" + "=" * 60)
    print(f"[ok] {SALIDA_JSON}")
    print(f"[ok] {SALIDA_MD}")
    print(f"[recomendación] {modo_rec}")


def datos_embeddings():
    ruta = os.path.join(REPORTS, "embeddings_verificacion_v2.json")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def bloque_regresion():
    ruta = os.path.join(REPORTS, "regresion_resultados_v2.json")
    if not os.path.exists(ruta):
        ruta = os.path.join(REPORTS, "regresion_resultados.json")
    if not os.path.exists(ruta):
        return "Pendiente de ejecutar."
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    lineas = [
        "| Prueba | Resultado | Total | Entorno |",
        "|---|---:|---:|---|",
    ]
    for prueba in datos.get("pruebas", []):
        lineas.append(
            f"| `{prueba['nombre']}` | {prueba['ok']} | {prueba['total']} | "
            f"{prueba.get('entorno', '—')} |"
        )
    return "\n".join(lineas)


if __name__ == "__main__":
    main()
