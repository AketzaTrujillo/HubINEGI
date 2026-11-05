"""Evalúa el clasificador de publicaciones críticas (objetivo 9).

Dos modos:
1. Sin argumentos: usa el piloto manual y el modelo final. Reporta métricas
   in-sample (el modelo se entrenó con el piloto) y muestra las métricas
   honestas fuera de muestra (validación cruzada) guardadas por el entrenamiento.
2. Con --csv: evalúa el modelo sobre un conjunto etiquetado nuevo, con columnas
   `texto_limpio` y `etiqueta_manual` (1 = crítica, 0 = no crítica).

Uso:
    cd tests
    python evaluar_clasificador.py
    python evaluar_clasificador.py --csv ../data/processed/mi_test.csv
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "ingestion", "X"))

import clasificador_dl as dl  # noqa: E402


def metricas(y_true, y_prob, umbral: float) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    y_pred = [1 if p >= umbral else 0 for p in y_prob]
    try:
        auc = float(roc_auc_score(y_true, y_prob))
    except Exception:
        auc = None
    return {
        "n": len(y_true),
        "positivos": int(sum(y_true)),
        "umbral": round(float(umbral), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(auc, 4) if auc is not None else None,
        "matriz_confusion": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
    }


def evaluar_csv(ruta_csv: str, modelo_dir: str, umbral: float) -> dict:
    df = pd.read_csv(ruta_csv, encoding="utf-8-sig")
    requeridas = {"texto_limpio", "etiqueta_manual"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise SystemExit(
            f"Faltan columnas en {ruta_csv}: {', '.join(sorted(faltantes))}"
        )

    df = df.dropna(subset=["etiqueta_manual"]).copy()
    df["texto_limpio"] = df["texto_limpio"].fillna("").astype(str)
    df["etiqueta_manual"] = df["etiqueta_manual"].astype(int)

    textos = df["texto_limpio"].tolist()
    y = df["etiqueta_manual"].tolist()
    probs = dl.predecir_probs(textos, modelo_dir=modelo_dir)
    if probs is None:
        raise SystemExit(
            "No se pudo cargar el modelo. Entrena con ingestion/X/entrenar_clasificador.py "
            "o revisa MHUB_MODELO_CRITICIDAD."
        )

    m = metricas(y, probs, umbral)
    tipos = df["tipo_contenido"].tolist() if "tipo_contenido" in df else [None] * len(df)
    baseline = [dl.regla_critica(texto, tipo) for texto, tipo in zip(textos, tipos)]
    m_baseline = metricas(y, baseline, 0.5)
    return {"metricas": m, "baseline": m_baseline, "archivo": ruta_csv}


def cargar_reporte_entrenamiento() -> dict | None:
    ruta = os.path.join(BASE, "reports", "clasificador_metricas.json")
    if not os.path.exists(ruta):
        return None
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa el clasificador de criticidad.")
    parser.add_argument("--csv", default=None, help="CSV con texto_limpio y etiqueta_manual")
    parser.add_argument(
        "--modelo-dir",
        default=os.path.join(BASE, "models", "clasificador_criticas"),
    )
    parser.add_argument("--umbral", type=float, default=0.5)
    parser.add_argument(
        "--reporte",
        default=os.path.join(BASE, "reports", "evaluacion_clasificador.json"),
    )
    args = parser.parse_args()

    ruta_piloto = os.path.join(
        BASE, "data", "processed", "etiquetas_criticas_piloto.csv"
    )
    ruta_csv = args.csv or ruta_piloto
    resultado = evaluar_csv(ruta_csv, args.modelo_dir, args.umbral)
    es_piloto = os.path.abspath(ruta_csv) == os.path.abspath(ruta_piloto)
    resultado["tipo_evaluacion"] = "in_sample_piloto" if es_piloto else "externa"
    if es_piloto:
        resultado["nota"] = (
            "El modelo final se entrenó con este piloto; la métrica honesta "
            "fuera de muestra está en reporte_entrenamiento.piloto_oof_05."
        )

    reporte_entrenamiento = cargar_reporte_entrenamiento()
    resultado["reporte_entrenamiento"] = (
        {
            "piloto_oof_05": reporte_entrenamiento.get("piloto_oof_05"),
            "piloto_oof_mejor": reporte_entrenamiento.get("piloto_oof_mejor"),
            "baseline_reglas_piloto": reporte_entrenamiento.get("baseline_reglas_piloto"),
        }
        if reporte_entrenamiento
        else None
    )
    resultado["modelo"] = dl.MODELO_VERSION

    os.makedirs(os.path.dirname(args.reporte), exist_ok=True)
    with open(args.reporte, "w", encoding="utf-8") as archivo:
        json.dump(resultado, archivo, ensure_ascii=False, indent=2)

    print(f"Archivo evaluado: {ruta_csv}")
    print("\nModelo final (in-sample si es el piloto):")
    for clave in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        print(f"  {clave:10} {resultado['metricas'][clave]}")
    print("  matriz    ", resultado["metricas"]["matriz_confusion"])

    print("\nBaseline por reglas:")
    for clave in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        print(f"  {clave:10} {resultado['baseline'][clave]}")
    print("  matriz    ", resultado["baseline"]["matriz_confusion"])

    if resultado["reporte_entrenamiento"]:
        oof = resultado["reporte_entrenamiento"]["piloto_oof_05"]
        print("\nValidación cruzada fuera de muestra (reporte de entrenamiento):")
        for clave in ("accuracy", "precision", "recall", "f1", "roc_auc"):
            print(f"  {clave:10} {oof[clave]}")
        print("  matriz    ", oof["matriz_confusion"])

    print(f"\nReporte guardado en: {args.reporte}")


if __name__ == "__main__":
    main()
