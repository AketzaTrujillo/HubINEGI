"""Evaluación comparativa de recuperación del corpus (Fase 6).

Ejecuta el golden set en los modos fulltext, embedding e hybrid, calcula
métricas de ranking y latencia, y genera:

- reports/recuperacion_resultados.json
- reports/recuperacion_comparacion.md

Uso:
    cd tests
    python run_corpus.py --modo all --topk 3
    python run_corpus.py --modo fulltext --topk 3
    python run_corpus.py --modo embedding --topk 3
    python run_corpus.py --modo hybrid --topk 3
"""
import argparse
import json
import math
import os
import platform
import statistics
import sys
import time
from datetime import datetime

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

import corpus_search  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_corpus.jsonl")
REPORTS = os.path.join(BASE, "reports")
SALIDA_JSON = os.path.join(REPORTS, "recuperacion_resultados.json")
SALIDA_MD = os.path.join(REPORTS, "recuperacion_comparacion.md")

CATEGORIAS = ["termino_exacto", "parafrasis", "sigla", "procedimiento"]
ETIQUETAS_CATEGORIA = {
    "termino_exacto": "Término exacto",
    "parafrasis": "Paráfrasis",
    "sigla": "Sigla",
    "procedimiento": "Procedimiento",
    "fuera_de_alcance": "Fuera de alcance",
}
MODOS = ["fulltext", "embedding", "hybrid"]
CALENTAMIENTO = [
    "violencia contra las mujeres",
    "Centros de Justicia para las Mujeres",
    "orden de protección",
]


def cargar_casos():
    with open(GOLDEN, encoding="utf-8") as archivo:
        return [json.loads(linea) for linea in archivo if linea.strip()]


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


def es_relevante(fila, caso, claves=None):
    return _clave_relevante(fila, caso, claves) is not None


def _clave_relevante(fila, caso, claves=None):
    fragmentos, paginas, _ = claves or claves_relevantes(caso)
    if int(fila.get("id_fragmento") or 0) in fragmentos:
        return ("frag", int(fila["id_fragmento"]))
    pagina = int(fila.get("pagina") or 0)
    if (int(fila.get("id_documento") or 0), pagina) in paginas:
        return ("doc", int(fila.get("id_documento")), pagina)
    if (fila.get("documento"), pagina) in paginas:
        return ("doc", fila.get("documento"), pagina)
    return None


def es_documento_relevante(fila, caso, claves=None):
    _, _, documentos = claves or claves_relevantes(caso)
    return fila.get("id_documento") in documentos or fila.get("documento") in documentos


def calcular_metricas(resultados, caso, topk=3, claves=None):
    claves = claves or claves_relevantes(caso)
    total_relevantes = len(claves[0]) + len(claves[1])
    claves_resultado = [_clave_relevante(f, caso, claves) for f in resultados[:topk]]
    flags = [clave is not None for clave in claves_resultado]

    if total_relevantes == 0:
        return {
            "p1": 0.0, "p3": 0.0, "r3": 0.0, "mrr": 0.0, "ndcg3": 0.0,
            "doc_hit3": 0.0, "n_relevantes": 0,
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
    doc_hit = 1.0 if any(es_documento_relevante(f, caso, claves) for f in resultados[:topk]) else 0.0

    return {
        "p1": p1, "p3": p3, "r3": r3, "mrr": mrr, "ndcg3": ndcg,
        "doc_hit3": doc_hit, "n_relevantes": total_relevantes,
    }


def promedio(valores):
    return sum(valores) / len(valores) if valores else 0.0


def percentil(valores, p):
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    indice = max(0, min(len(ordenados) - 1, math.ceil(p / 100 * len(ordenados)) - 1))
    return ordenados[indice]


def preparar_modelo(modo):
    cargas = {"indice_s": 0.0, "modelo_s": 0.0}
    if modo == "fulltext":
        return cargas
    inicio = time.perf_counter()
    corpus_search.cargar_indice()
    cargas["indice_s"] = round(time.perf_counter() - inicio, 2)
    inicio = time.perf_counter()
    corpus_search.cargar_modelo()
    cargas["modelo_s"] = round(time.perf_counter() - inicio, 2)
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
    print(f"\n=== Modo {modo} ===")
    cargas = preparar_modelo(modo)
    primera_ms = calentar(modo, topk)

    registros = []
    latencias_por_consulta = []
    fallbacks = 0
    motivos_fallback = []

    for caso in casos:
        claves = claves_relevantes(caso)
        resultados = []
        latencias = []
        fallback_caso = False
        for repeticion in range(reps):
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
                    motivos_fallback.append(estado["motivo"])

        if fallback_caso:
            fallbacks += 1
        latencias_por_consulta.append(statistics.median(latencias))

        detalle = []
        for fila in resultados:
            detalle.append({
                "rank": fila.get("rank"),
                "id_fragmento": fila.get("id_fragmento"),
                "id_documento": fila.get("id_documento"),
                "documento": fila.get("documento"),
                "pagina": fila.get("pagina"),
                "fuente": fila.get("fuente"),
                "score": round(float(fila.get("score") or 0.0), 6),
                "relevante": es_relevante(fila, caso, claves),
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
        "doc_hit3": promedio([r["metricas"]["doc_hit3"] for r in dentro]),
        "fuera_de_alcance_n": len(fuera),
        "fuera_de_alcance_con_resultados": sum(1 for r in fuera if r["resultados"]),
        "tasa_falsos_positivos": (
            sum(1 for r in fuera if r["resultados"]) / len(fuera) if fuera else 0.0
        ),
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
        "carga_indice_s": cargas["indice_s"],
        "carga_modelo_s": cargas["modelo_s"],
        "repeticiones_por_pregunta": reps,
    }

    fallback = {
        "casos": fallbacks,
        "n": len(registros),
        "tasa": fallbacks / len(registros) if registros else 0.0,
        "motivos": sorted(set(motivos_fallback))[:5],
    }

    print(f"  P@1 {resumen['p1']:.3f} | P@3 {resumen['p3']:.3f} | "
          f"R@3 {resumen['r3']:.3f} | MRR {resumen['mrr']:.3f} | "
          f"nDCG@3 {resumen['ndcg3']:.3f}")
    print(f"  latencia p50 {latencia['p50_ms']} ms | p95 {latencia['p95_ms']} ms | "
          f"primera {latencia['primera_consulta_ms']} ms | fallback {fallback['tasa']:.1%}")

    return {
        "resumen": resumen,
        "por_categoria": por_categoria,
        "latencia": latencia,
        "fallback": fallback,
        "casos": registros,
    }


def comparar(modos):
    f = modos["fulltext"]["resumen"]
    e = modos["embedding"]["resumen"]
    h = modos["hybrid"]["resumen"]
    rel = lambda nuevo, base: ((nuevo - base) / base) if base else (1.0 if nuevo > 0 else 0.0)
    return {
        "hybrid_vs_fulltext": {
            "p1_rel": rel(h["p1"], f["p1"]),
            "p3_rel": rel(h["p3"], f["p3"]),
            "r3_rel": rel(h["r3"], f["r3"]),
            "mrr_rel": rel(h["mrr"], f["mrr"]),
            "ndcg_rel": rel(h["ndcg3"], f["ndcg3"]),
            "latencia_p95_delta_ms": modos["hybrid"]["latencia"]["p95_ms"] - modos["fulltext"]["latencia"]["p95_ms"],
        },
        "embedding_vs_fulltext": {
            "p1_rel": rel(e["p1"], f["p1"]),
            "p3_rel": rel(e["p3"], f["p3"]),
            "r3_rel": rel(e["r3"], f["r3"]),
            "mrr_rel": rel(e["mrr"], f["mrr"]),
            "ndcg_rel": rel(e["ndcg3"], f["ndcg3"]),
            "latencia_p95_delta_ms": modos["embedding"]["latencia"]["p95_ms"] - modos["fulltext"]["latencia"]["p95_ms"],
        },
    }


def recomendar(modos, comparacion):
    f = modos["fulltext"]
    e = modos["embedding"]
    h = modos["hybrid"]
    cf = comparacion["hybrid_vs_fulltext"]
    ce = comparacion["embedding_vs_fulltext"]

    h_mejora = max(cf["p3_rel"], cf["r3_rel"])
    h_p1_cae = -cf["p1_rel"]  # positivo = caída
    h_lat = cf["latencia_p95_delta_ms"]
    h_ok = (
        h_mejora >= 0.10
        and h_p1_cae <= 0.05
        and h_lat <= 300
        and h["fallback"]["tasa"] <= 0.05
    )

    f_exacto = f["por_categoria"].get("termino_exacto", {}).get("p1", 0.0)
    e_exacto = e["por_categoria"].get("termino_exacto", {}).get("p1", 0.0)
    e_ok = (
        e["resumen"]["p3"] > f["resumen"]["p3"]
        and e["resumen"]["r3"] > f["resumen"]["r3"]
        and (
            e["resumen"]["p3"] > h["resumen"]["p3"]
            or e["resumen"]["r3"] > h["resumen"]["r3"]
            or e["resumen"]["mrr"] > h["resumen"]["mrr"]
        )
        and (f_exacto == 0 or e_exacto >= 0.95 * f_exacto)
        and ce["latencia_p95_delta_ms"] <= 300
        and e["fallback"]["tasa"] <= 0.05
    )

    motivos = []
    if h_ok:
        motivos.append(
            f"hybrid mejora P@3 {cf['p3_rel']:.1%} y R@3 {cf['r3_rel']:.1%} "
            f"en términos relativos, la caída de P@1 es {h_p1_cae:.1%} y "
            f"el p95 sube {h_lat:.0f} ms."
        )
        return "hybrid", motivos
    if e_ok:
        motivos.append("embedding supera a fulltext en P@3 y R@3 y no destruye la precisión exacta.")
        return "embedding", motivos

    if h_mejora >= 0.10:
        motivos.append(
            f"hybrid mejora P@3 {cf['p3_rel']:.1%} y R@3 {cf['r3_rel']:.1%} "
            f"en términos relativos, pero no cumple todas las condiciones: "
            f"P@1 cae {h_p1_cae:.1%}, p95 sube {h_lat:.0f} ms, "
            f"fallback {h['fallback']['tasa']:.1%}."
        )
    elif h_mejora > 0:
        motivos.append(
            f"la mejora de hybrid en P@3/R@3 es {h_mejora:.1%}, por debajo del 10% exigido."
        )
    else:
        motivos.append("hybrid no mejora P@3 ni R@3 frente a fulltext.")

    if ce["p3_rel"] <= 0 or ce["r3_rel"] <= 0:
        motivos.append("embedding no supera a fulltext en P@3 y R@3.")
    if f_exacto > 0 and e_exacto < 0.95 * f_exacto:
        motivos.append(
            f"embedding reduce P@1 en término exacto de {f_exacto:.3f} a {e_exacto:.3f}."
        )
    motivos.append("Se recomienda mantener FULLTEXT como modo oficial.")
    return "fulltext", motivos


# ---------------------------------------------------------------- reporte

def fmt(valor, decimales=3):
    return f"{valor:.{decimales}f}"


def pct(valor, decimales=1):
    return f"{100 * valor:.{decimales}f}%"


def tabla_general(modos):
    lineas = [
        "| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocHit@3 | Latencia p50 | Latencia p95 | Fallback |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for modo in MODOS:
        m = modos[modo]
        r = m["resumen"]
        l = m["latencia"]
        f = m["fallback"]
        lineas.append(
            f"| `{modo}` | {fmt(r['p1'])} | {fmt(r['p3'])} | {fmt(r['r3'])} | "
            f"{fmt(r['mrr'])} | {fmt(r['ndcg3'])} | {fmt(r['doc_hit3'])} | "
            f"{l['p50_ms']:.1f} ms | {l['p95_ms']:.1f} ms | {pct(f['tasa'])} |"
        )
    return "\n".join(lineas)


def tabla_categorias(modos):
    lineas = [
        "| Categoría | Modo | n | P@1 | P@3 | R@3 | MRR | nDCG@3 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for categoria in CATEGORIAS:
        for modo in MODOS:
            datos = modos[modo]["por_categoria"].get(categoria)
            if not datos:
                continue
            lineas.append(
                f"| {ETIQUETAS_CATEGORIA[categoria]} | `{modo}` | {datos['n']} | "
                f"{fmt(datos['p1'])} | {fmt(datos['p3'])} | {fmt(datos['r3'])} | "
                f"{fmt(datos['mrr'])} | {fmt(datos['ndcg3'])} |"
            )
    return "\n".join(lineas)


def tabla_fuera_alcance(modos):
    lineas = [
        "| Modo | Consultas | Devolvieron resultados | Tasa de falsos positivos |",
        "|---|---:|---:|---:|",
    ]
    for modo in MODOS:
        datos = modos[modo]["por_categoria"].get("fuera_de_alcance", {})
        lineas.append(
            f"| `{modo}` | {datos.get('n', 0)} | {datos.get('con_resultados', 0)} | "
            f"{pct(datos.get('tasa_falsos_positivos', 0.0))} |"
        )
    return "\n".join(lineas)


def describir_resultado(fila):
    if not fila:
        return "—"
    return f"{fila.get('documento')} p. {fila.get('pagina')}"


def bloque_ejemplos(modos, limite_por_modo=2):
    lineas = []
    for modo in MODOS:
        casos = modos[modo]["casos"]
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
                    f"{describir_resultado(caso['resultados'][0] if caso['resultados'] else None)}"
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
                    f"- `{caso['id']}` {caso['pregunta']} → "
                    f"recuperó {describir_resultado(caso['resultados'][0] if caso['resultados'] else None)}; "
                    f"esperado: {esperado}"
                )
        else:
            lineas.append("- Sin fallos en el primer lugar.")
    return "\n".join(lineas)


def bloque_diferencias(modos):
    por_id = {}
    for modo in MODOS:
        por_id[modo] = {c["id"]: c for c in modos[modo]["casos"]}

    gana_full, gana_emb, gana_hybrid = [], [], []
    for caso_id, caso in por_id["fulltext"].items():
        if caso["categoria"] == "fuera_de_alcance":
            continue
        p3 = {modo: por_id[modo][caso_id]["metricas"]["p3"] for modo in MODOS}
        if p3["fulltext"] > max(p3["embedding"], p3["hybrid"]):
            gana_full.append(caso["pregunta"])
        if p3["embedding"] > max(p3["fulltext"], p3["hybrid"]):
            gana_emb.append(caso["pregunta"])
        if p3["hybrid"] > max(p3["fulltext"], p3["embedding"]):
            gana_hybrid.append(caso["pregunta"])

    def lista(titulo, preguntas):
        if not preguntas:
            return f"- **{titulo}:** ningún caso con P@3 estrictamente mayor."
        return f"- **{titulo}** ({len(preguntas)}): " + "; ".join(preguntas[:4]) + (
            "…" if len(preguntas) > 4 else ""
        )

    return "\n".join([
        lista("Gana FULLTEXT", gana_full),
        lista("Gana embedding", gana_emb),
        lista("Gana hybrid", gana_hybrid),
    ])


def bloque_regresion():
    ruta = os.path.join(REPORTS, "regresion_resultados.json")
    if not os.path.exists(ruta):
        return "Pendiente de ejecutar `run_golden.py`, `run_conversacion.py` y `run_interprete.py`."
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


def escribir_markdown(datos, ruta):
    modos = datos["modos"]
    cfg = datos["config"]
    comp = datos["comparacion"]
    rec = datos["recomendacion"]

    lineas = [
        "# Comparación de recuperación: FULLTEXT, embeddings e híbrida",
        "",
        f"**Fecha:** {datos['generado']}  ",
        f"**Golden set:** {datos['golden']['casos']} preguntas "
        f"({datos['golden']['dentro_de_alcance']} dentro de alcance, "
        f"{datos['golden']['fuera_de_alcance']} fuera de alcance)  ",
        f"**Top-k:** {cfg['topk']}  ",
        "**Versión oficial:** `FULLTEXT` (esta evaluación no cambia la versión oficial).",
        "",
        "## 1. Resumen ejecutivo",
        "",
        f"Se evaluaron los tres modos sobre el mismo golden set de "
        f"{datos['golden']['casos']} preguntas. La tabla principal usa las "
        f"{datos['golden']['dentro_de_alcance']} preguntas con respuesta en el corpus; "
        "las consultas fuera de alcance se reportan aparte porque no tienen fragmentos "
        "relevantes etiquetados.",
        "",
        tabla_general(modos),
        "",
        f"- **Mejor P@1:** `{datos['mejor']['p1']}`.",
        f"- **Mejor P@3:** `{datos['mejor']['p3']}`.",
        f"- **Mejor R@3:** `{datos['mejor']['r3']}`.",
        f"- **Menor latencia p95:** `{datos['mejor']['latencia']}`.",
        f"- **Recomendación técnica:** `{rec['modo']}`. {rec['motivos'][0]}",
        "",
        "## 2. Configuración",
        "",
        "| Parámetro | Valor |",
        "|---|---|",
        f"| Modelo de embeddings | `{cfg['modelo']}` |",
        f"| Dimensiones | {cfg['dimensiones']} |",
        f"| Top-k | {cfg['topk']} |",
        f"| Repeticiones por pregunta | {cfg['reps']} |",
        f"| Python | {cfg['python']} |",
        f"| torch | {cfg['torch']} |",
        f"| sentence-transformers | {cfg['sentence_transformers']} |",
        f"| numpy | {cfg['numpy']} |",
        f"| Equipo | {cfg['equipo']} |",
        f"| Sistema | {cfg['sistema']} |",
        f"| CPU lógicas | {cfg['cpu']} |",
        f"| Carga del índice | {modos['embedding']['latencia']['carga_indice_s']:.2f} s |",
        f"| Carga del modelo | {modos['embedding']['latencia']['carga_modelo_s']:.2f} s |",
        f"| Primera consulta (embedding) | {modos['embedding']['latencia']['primera_consulta_ms']:.1f} ms |",
        f"| Arranque en frío (carga + primera consulta) | "
        f"{modos['embedding']['latencia']['carga_modelo_s'] + modos['embedding']['latencia']['primera_consulta_ms'] / 1000:.2f} s |",
        "",
        "La carga del modelo incluye la importación de torch y sentence-transformers y "
        "la construcción del modelo. La primera consulta de la tabla ya tiene el modelo "
        "cargado; el arranque en frío completo es la suma de la carga y esa primera "
        "consulta. La latencia por consulta se midió después de tres consultas de "
        "calentamiento, con la mediana de tres repeticiones por pregunta.",
        "",
        "## 3. Tabla general por modo",
        "",
        tabla_general(modos),
        "",
        "> P@k y R@3 se calculan solo sobre las preguntas con respuesta en el corpus. "
        "DocHit@3 indica si al menos un documento relevante aparece en el top-3. "
        "La tasa de fallback es la proporción de consultas que tuvieron que usar "
        "FULLTEXT porque el modelo o el índice no estaban disponibles.",
        "",
        "## 4. Tabla por categoría",
        "",
        tabla_categorias(modos),
        "",
        "### Consultas fuera de alcance",
        "",
        tabla_fuera_alcance(modos),
        "",
        "El corpus no contiene respuestas a estas preguntas. Ningún modo implementa "
        "abstención por umbral, así que todos devuelven fragmentos; la columna mide "
        "cuántas veces ocurrió. Es una limitación del experimento, no una métrica de "
        "ranking.",
        "",
        "## 5. Incrementos relativos",
        "",
        "| Comparación | P@1 | P@3 | R@3 | MRR | nDCG@3 | Δ p95 |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| hybrid vs fulltext | {pct(comp['hybrid_vs_fulltext']['p1_rel'])} | "
        f"{pct(comp['hybrid_vs_fulltext']['p3_rel'])} | {pct(comp['hybrid_vs_fulltext']['r3_rel'])} | "
        f"{pct(comp['hybrid_vs_fulltext']['mrr_rel'])} | {pct(comp['hybrid_vs_fulltext']['ndcg_rel'])} | "
        f"{comp['hybrid_vs_fulltext']['latencia_p95_delta_ms']:+.1f} ms |",
        f"| embedding vs fulltext | {pct(comp['embedding_vs_fulltext']['p1_rel'])} | "
        f"{pct(comp['embedding_vs_fulltext']['p3_rel'])} | {pct(comp['embedding_vs_fulltext']['r3_rel'])} | "
        f"{pct(comp['embedding_vs_fulltext']['mrr_rel'])} | {pct(comp['embedding_vs_fulltext']['ndcg_rel'])} | "
        f"{comp['embedding_vs_fulltext']['latencia_p95_delta_ms']:+.1f} ms |",
        "",
        "## 6. Dónde gana cada modo",
        "",
        bloque_diferencias(modos),
        "",
        "## 7. Ejemplos de aciertos y fallos",
        "",
        bloque_ejemplos(modos),
        "",
        "## 8. Interpretación",
        "",
    ]

    f = modos["fulltext"]
    e = modos["embedding"]
    h = modos["hybrid"]

    def cat(modo, categoria, clave):
        return modo["por_categoria"].get(categoria, {}).get(clave, 0.0)

    lineas += [
        "### ¿Dónde gana FULLTEXT?",
        "",
        f"En término exacto, FULLTEXT obtiene P@1 {fmt(cat(f, 'termino_exacto', 'p1'))} "
        f"frente a {fmt(cat(e, 'termino_exacto', 'p1'))} de embedding y "
        f"{fmt(cat(h, 'termino_exacto', 'p1'))} de hybrid. "
        f"En procedimiento, las P@1 son FULLTEXT {fmt(cat(f, 'procedimiento', 'p1'))}, "
        f"embedding {fmt(cat(e, 'procedimiento', 'p1'))} y hybrid "
        f"{fmt(cat(h, 'procedimiento', 'p1'))}; "
        + (
            "FULLTEXT es el único que acierta en el primer lugar."
            if cat(f, "procedimiento", "p1") > max(cat(e, "procedimiento", "p1"), cat(h, "procedimiento", "p1"))
            else "ningún modo acierta en el primer lugar, así que no hay ganador claro."
        ),
        "",
        "### ¿Dónde ganan los embeddings?",
        "",
        (
            f"En paráfrasis, embedding obtiene P@1 {fmt(cat(e, 'parafrasis', 'p1'))}, "
            f"P@3 {fmt(cat(e, 'parafrasis', 'p3'))} y R@3 {fmt(cat(e, 'parafrasis', 'r3'))}, "
            f"frente a FULLTEXT P@1 {fmt(cat(f, 'parafrasis', 'p1'))}, "
            f"P@3 {fmt(cat(f, 'parafrasis', 'p3'))} y R@3 {fmt(cat(f, 'parafrasis', 'r3'))}. "
            "Embedding sí mejora la paráfrasis en este conjunto."
            if (cat(e, "parafrasis", "p3") > cat(f, "parafrasis", "p3")
                or cat(e, "parafrasis", "r3") > cat(f, "parafrasis", "r3"))
            else f"En este conjunto embedding no gana en paráfrasis: obtiene P@1 "
                 f"{fmt(cat(e, 'parafrasis', 'p1'))}, P@3 {fmt(cat(e, 'parafrasis', 'p3'))} "
                 f"y R@3 {fmt(cat(e, 'parafrasis', 'r3'))}, frente a FULLTEXT P@1 "
                 f"{fmt(cat(f, 'parafrasis', 'p1'))}, P@3 {fmt(cat(f, 'parafrasis', 'p3'))} "
                 f"y R@3 {fmt(cat(f, 'parafrasis', 'r3'))}. La ventaja esperada de los "
                 "embeddings no se materializó con este modelo y este golden set."
        ),
        "",
        "### ¿La híbrida mejora sin destruir la precisión exacta?",
        "",
        f"En el conjunto general, hybrid tiene P@3 {fmt(h['resumen']['p3'])} y "
        f"R@3 {fmt(h['resumen']['r3'])}; FULLTEXT tiene P@3 {fmt(f['resumen']['p3'])} "
        f"y R@3 {fmt(f['resumen']['r3'])}. En término exacto, la P@1 de hybrid es "
        f"{fmt(cat(h, 'termino_exacto', 'p1'))} y la de FULLTEXT es "
        f"{fmt(cat(f, 'termino_exacto', 'p1'))}. En acierto de documento (DocHit@3), "
        f"hybrid obtiene {fmt(h['resumen']['doc_hit3'])} y FULLTEXT "
        f"{fmt(f['resumen']['doc_hit3'])}. La ganancia de ranking no compensa la "
        f"caída de P@1 de {pct(-comp['hybrid_vs_fulltext']['p1_rel'])}.",
        "",
        "## 9. Recomendación",
        "",
        f"**Recomendación técnica:** `{rec['modo']}`.",
        "",
    ]
    for motivo in rec["motivos"]:
        lineas.append(f"- {motivo}")
    lineas += [
        "",
        "La decisión final corresponde a la usuaria. Mientras no se revise este "
        "reporte, la versión oficial sigue siendo `FULLTEXT` y las ramas "
        "`experimento/recuperacion-hibrida` no se fusionan con `jaz` ni con `main`.",
        "",
        "## 10. Pruebas de regresión",
        "",
        bloque_regresion(),
        "",
        "## 11. Limitaciones",
        "",
        "- El golden set tiene 36 preguntas y fue definido antes de ejecutar la línea base.",
        "- Las etiquetas de relevancia son páginas específicas; una página que también "
        "responde puede no estar etiquetada. Esto afecta los valores absolutos, no la "
        "comparación entre modos, porque los tres usan las mismas etiquetas.",
        "- En los ejemplos, un resultado de otra página del mismo tema puede aparecer "
        "como fallo aunque sea útil para la persona usuaria.",
        "- Una sola máquina, un solo modelo y una sola configuración de top-k.",
        "- No hay umbral de abstención para consultas fuera de alcance.",
        "- La latencia es de CPU y puede variar con la carga del equipo.",
        "- El corpus es pequeño (3,170 fragmentos); los resultados no se generalizan "
        "a corpus mucho mayores sin repetir la medición.",
        "",
        "## 12. Reproducibilidad",
        "",
        "```powershell",
        "cd HubINEGI/ingestion/embeddings",
        "python generar_embeddings.py",
        "python verificar_embeddings.py",
        "cd ../../tests",
        "python run_corpus.py --modo all --topk 3",
        "```",
        "",
        "El detalle por pregunta, incluidos los fragmentos recuperados y sus scores, "
        "está en `reports/recuperacion_resultados.json`.",
        "",
    ]

    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modo", choices=MODOS + ["all"], default="all")
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--reps", type=int, default=3)
    args = parser.parse_args()

    casos = cargar_casos()
    modos_a_ejecutar = MODOS if args.modo == "all" else [args.modo]

    modos = {}
    for modo in modos_a_ejecutar:
        modos[modo] = ejecutar_modo(modo, casos, args.topk, args.reps)

    if args.modo != "all":
        ruta = os.path.join(REPORTS, f"recuperacion_{args.modo}.json")
        os.makedirs(REPORTS, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump({"modo": args.modo, "topk": args.topk, **modos[args.modo]},
                      archivo, ensure_ascii=False, indent=2)
        print(f"\n[ok] {ruta}")
        return

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
    try:
        import numpy
        numpy_version = numpy.__version__
    except Exception:
        numpy_version = "no instalado"

    comparacion = comparar(modos)
    modo_recomendado, motivos = recomendar(modos, comparacion)

    def mejor(clave):
        return max(MODOS, key=lambda m: modos[m]["resumen"][clave])

    datos = {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "topk": args.topk,
            "reps": args.reps,
            "modelo": os.environ.get(
                "MHUB_EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
            "dimensiones": 384,
            "python": platform.python_version(),
            "torch": torch_version,
            "sentence_transformers": st_version,
            "numpy": numpy_version,
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
        "modos": modos,
        "comparacion": comparacion,
        "mejor": {
            "p1": mejor("p1"),
            "p3": mejor("p3"),
            "r3": mejor("r3"),
            "mrr": mejor("mrr"),
            "ndcg3": mejor("ndcg3"),
            "latencia": min(MODOS, key=lambda m: modos[m]["latencia"]["p95_ms"]),
        },
        "recomendacion": {
            "modo": modo_recomendado,
            "motivos": motivos,
            "criterio": (
                "hybrid requiere +10% relativo en P@3 o R@3, caída de P@1 <=5%, "
                "aumento de p95 <=300 ms y fallback <=5%. embedding requiere superar "
                "a fulltext en P@3 y R@3, superar a hybrid en al menos una métrica "
                "principal y no destruir la precisión exacta."
            ),
            "version_oficial": "fulltext",
            "nota": "La decisión final es de la usuaria; no se cambia la versión oficial.",
        },
    }

    os.makedirs(REPORTS, exist_ok=True)
    with open(SALIDA_JSON, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
    escribir_markdown(datos, SALIDA_MD)

    print("\n" + "=" * 60)
    print(f"[ok] {SALIDA_JSON}")
    print(f"[ok] {SALIDA_MD}")
    print(f"[recomendación] {modo_recomendado}")


if __name__ == "__main__":
    main()
