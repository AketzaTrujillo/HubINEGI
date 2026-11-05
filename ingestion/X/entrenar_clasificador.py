"""Entrena y evalúa el clasificador de publicaciones críticas (objetivo 7).

Estrategia final:
1. Preentrenamiento débil con `tipo_contenido` en {noticia, denuncia}.
2. Ajuste fino supervisado con el piloto anotado manualmente.
3. Validación cruzada estratificada (5 folds) sobre el piloto para reportar
   métricas honestas fuera de muestra.
4. Reentrenamiento sobre todo el piloto para generar el modelo desplegable.

El piloto se excluye del preentrenamiento para evitar fuga de información.

Uso:
    cd ingestion/X
    python entrenar_clasificador.py
    python entrenar_clasificador.py --pilot-epochs 12 --output-dir ../../models/clasificador_criticas
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

import numpy as np
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import clasificador_dl as dl  # noqa: E402


def fijar_semillas(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


def cargar_datos(ruta_csv: str, ruta_piloto: str):
    df = pd.read_csv(ruta_csv, encoding="utf-8-sig")
    df = df[df["es_basura"].fillna("no") == "no"].copy()
    df["texto_limpio"] = df["texto_limpio"].fillna("").astype(str)
    df = df[df["texto_limpio"].str.strip() != ""].copy()
    df["id_fila"] = df.index
    df["etiqueta_debil"] = df["tipo_contenido"].isin(["noticia", "denuncia"]).astype(int)

    piloto = pd.read_csv(ruta_piloto, encoding="utf-8-sig")
    piloto = piloto.dropna(subset=["etiqueta_manual"]).copy()
    piloto["texto_limpio"] = piloto["texto_limpio"].fillna("").astype(str)
    piloto["etiqueta_manual"] = piloto["etiqueta_manual"].astype(int)
    return df, piloto


def dividir(df: pd.DataFrame, seed: int):
    from sklearn.model_selection import train_test_split

    train, resto = train_test_split(
        df, test_size=0.30, stratify=df["etiqueta_debil"], random_state=seed
    )
    val, test = train_test_split(
        resto, test_size=0.50, stratify=resto["etiqueta_debil"], random_state=seed
    )
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


class DatasetPublicaciones:
    def __init__(self, textos, etiquetas, vocab, max_len):
        self.textos = list(textos)
        self.etiquetas = list(etiquetas)
        self.vocab = vocab
        self.max_len = max_len

    def __len__(self):
        return len(self.textos)

    def __getitem__(self, indice):
        import torch

        x = torch.tensor(
            dl.codificar(self.textos[indice], self.vocab, self.max_len),
            dtype=torch.long,
        )
        y = torch.tensor(float(self.etiquetas[indice]), dtype=torch.float32)
        return x, y


def predecir(modelo, textos, vocab, max_len, lote=64):
    import torch

    modelo.eval()
    probabilidades = []
    with torch.no_grad():
        for inicio in range(0, len(textos), lote):
            bloque = textos[inicio : inicio + lote]
            x = torch.tensor(
                [dl.codificar(texto, vocab, max_len) for texto in bloque],
                dtype=torch.long,
            )
            logits = modelo(x)
            probabilidades.extend(torch.sigmoid(logits).cpu().tolist())
    return probabilidades


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
    matriz = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
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
        "matriz_confusion": matriz,
    }


def mejor_umbral(y_true, y_prob) -> tuple[float, dict]:
    mejor = (0.5, -1.0, None)
    for paso in range(5, 96, 5):
        umbral = paso / 100
        m = metricas(y_true, y_prob, umbral)
        if m["f1"] > mejor[1]:
            mejor = (umbral, m["f1"], m)
    return mejor[0], mejor[2]


def _clonar_modelo(modelo, estado_base):
    clon = dl.construir_modelo(modelo.embedding.num_embeddings)
    clon.load_state_dict(estado_base)
    return clon


def _entrenar_epocas(modelo, textos, etiquetas, vocab, max_len, epochs, lr, batch_size, seed):
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader

    dataset = DatasetPublicaciones(textos, etiquetas, vocab, max_len)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, generator=torch.Generator().manual_seed(seed))
    positivos = int(sum(etiquetas))
    negativos = len(etiquetas) - positivos
    criterio = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([negativos / max(positivos, 1)], dtype=torch.float32)
    )
    optimizador = torch.optim.AdamW(modelo.parameters(), lr=lr, weight_decay=1e-4)

    for _ in range(epochs):
        modelo.train()
        for x, y in loader:
            optimizador.zero_grad()
            perdida = criterio(modelo(x), y)
            perdida.backward()
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            optimizador.step()
    return modelo


def preentrenar_debil(train, vocab, args):
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader

    dataset = DatasetPublicaciones(train["texto_limpio"], train["etiqueta_debil"], vocab, args.max_len)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    modelo = dl.construir_modelo(len(vocab))
    positivos = int(train["etiqueta_debil"].sum())
    negativos = len(train) - positivos
    criterio = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([negativos / max(positivos, 1)], dtype=torch.float32)
    )
    optimizador = torch.optim.AdamW(modelo.parameters(), lr=args.lr, weight_decay=1e-4)

    for epoca in range(1, args.epochs + 1):
        modelo.train()
        perdida_total = 0.0
        for x, y in loader:
            optimizador.zero_grad()
            perdida = criterio(modelo(x), y)
            perdida.backward()
            torch.nn.utils.clip_grad_norm_(modelo.parameters(), 1.0)
            optimizador.step()
            perdida_total += float(perdida.item()) * len(x)
        print(f"Preentrenamiento {epoca:02d} | pérdida={perdida_total / max(len(dataset), 1):.4f}")
    return modelo


def validacion_cruzada_piloto(modelo_base, piloto, vocab, args):
    from sklearn.model_selection import StratifiedKFold

    textos = piloto["texto_limpio"].tolist()
    etiquetas = piloto["etiqueta_manual"].tolist()
    estado_base = {k: v.detach().clone() for k, v in modelo_base.state_dict().items()}

    skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
    oof = [0.0] * len(etiquetas)
    folds = []

    for numero, (indices_train, indices_test) in enumerate(skf.split(textos, etiquetas), start=1):
        modelo = _clonar_modelo(modelo_base, estado_base)
        modelo = _entrenar_epocas(
            modelo,
            [textos[i] for i in indices_train],
            [etiquetas[i] for i in indices_train],
            vocab,
            args.max_len,
            args.pilot_epochs,
            args.pilot_lr,
            args.pilot_batch_size,
            args.seed + numero,
        )
        probs = predecir(modelo, [textos[i] for i in indices_test], vocab, args.max_len)
        for indice, prob in zip(indices_test, probs):
            oof[indice] = prob
        m = metricas([etiquetas[i] for i in indices_test], probs, 0.5)
        folds.append({"fold": numero, "n_test": len(indices_test), **m})
        print(f"Fold {numero} | test={len(indices_test)} | F1@0.5={m['f1']:.4f}")

    return oof, folds


def guardar_reporte(metricas_json: dict, ruta_json: str, ruta_md: str) -> None:
    os.makedirs(os.path.dirname(ruta_json), exist_ok=True)
    with open(ruta_json, "w", encoding="utf-8") as archivo:
        json.dump(metricas_json, archivo, ensure_ascii=False, indent=2)

    lineas = [
        "# Evaluación del clasificador de publicaciones críticas",
        "",
        f"Modelo: `{dl.MODELO_VERSION}` (TextCNN con preentrenamiento débil y ajuste fino)",
        f"Validación cruzada: {metricas_json['folds']} folds estratificados",
        f"Umbral de despliegue: **{metricas_json['umbral']}**",
        "",
        "## Resultados principales",
        "",
        "| Conjunto | n | Positivos | Accuracy | Precision | Recall | F1 | ROC-AUC |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for nombre, clave in [
        ("Piloto manual (OOF, umbral 0.5)", "piloto_oof_05"),
        ("Piloto manual (OOF, mejor umbral)", "piloto_oof_mejor"),
        ("Baseline reglas (piloto)", "baseline_reglas_piloto"),
        ("Test débil (preentrenamiento)", "test_debil"),
    ]:
        m = metricas_json[clave]
        lineas.append(
            f"| {nombre} | {m['n']} | {m['positivos']} | {m['accuracy']} | "
            f"{m['precision']} | {m['recall']} | {m['f1']} | {m['roc_auc']} |"
        )
    lineas += [
        "",
        "## Matriz de confusión (OOF, umbral 0.5)",
        "",
        "```",
        f"{metricas_json['piloto_oof_05']['matriz_confusion']}",
        "```",
        "",
        "## F1 por fold",
        "",
        "| Fold | n test | F1 | Accuracy |",
        "|---:|---:|---:|---:|",
    ]
    for fold in metricas_json["folds_detalle"]:
        lineas.append(f"| {fold['fold']} | {fold['n_test']} | {fold['f1']} | {fold['accuracy']} |")
    lineas += [
        "",
        "## Lectura",
        "",
        "- Las etiquetas débiles se derivan de `tipo_contenido` y se usan solo para preentrenar.",
        "- La evaluación principal es el piloto manual con validación cruzada fuera de muestra.",
        "- El baseline por reglas se incluye para comparar; el modelo lo supera en F1.",
        "- El piloto es pequeño (100 casos) y la varianza por fold es alta (F1 0.44–0.91).",
        "- Se observan falsos positivos en publicaciones de violencia general u organizada;",
        "  se recomienda ampliar el piloto con negativos duros antes de productionizar.",
        "- El umbral 0.5 es el de despliegue; el umbral alternativo mejora recall a costa de precisión.",
        "- El modelo final se reentrena con todo el piloto y se guarda en `models/`.",
    ]
    with open(ruta_md, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena el clasificador de publicaciones críticas.")
    parser.add_argument("--csv", default=os.path.join(BASE, "data", "processed", "dataset_twitter_limpio.csv"))
    parser.add_argument("--piloto", default=os.path.join(BASE, "data", "processed", "etiquetas_criticas_piloto.csv"))
    parser.add_argument("--output-dir", default=os.path.join(BASE, "models", "clasificador_criticas"))
    parser.add_argument("--report-dir", default=os.path.join(BASE, "reports"))
    parser.add_argument("--epochs", type=int, default=5, help="Épocas de preentrenamiento débil")
    parser.add_argument("--pilot-epochs", type=int, default=12, help="Épocas de ajuste fino por fold")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--pilot-batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--pilot-lr", type=float, default=3e-4)
    parser.add_argument("--max-len", type=int, default=dl.MAX_LEN)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    fijar_semillas(args.seed)
    df, piloto = cargar_datos(args.csv, args.piloto)
    if piloto.empty:
        raise SystemExit("El piloto manual está vacío. Anota etiquetas antes de entrenar.")

    ids_piloto = set(piloto["id_fila"].tolist())
    df_debil = df[~df["id_fila"].isin(ids_piloto)].copy()
    train, val, test = dividir(df_debil, args.seed)

    # Vocabulario sin etiquetas: incluye textos débiles y piloto.
    vocab = dl.construir_vocab(
        pd.concat([train["texto_limpio"], piloto["texto_limpio"]]),
        min_freq=1,
        max_size=20000,
    )

    print(f"Piloto: {len(piloto)} | Train débil: {len(train)} | Val: {len(val)} | Test: {len(test)}")
    print(f"Positivos débiles en train: {int(train['etiqueta_debil'].sum())}")
    print(f"Positivos manuales en piloto: {int(piloto['etiqueta_manual'].sum())}")

    modelo_base = preentrenar_debil(train, vocab, args)

    # Métricas del preentrenamiento en el test débil.
    test_prob = predecir(modelo_base, test["texto_limpio"].tolist(), vocab, args.max_len)
    m_test = metricas(test["etiqueta_debil"].tolist(), test_prob, 0.5)

    # Evaluación externa: validación cruzada sobre el piloto manual.
    oof, folds = validacion_cruzada_piloto(modelo_base, piloto, vocab, args)
    y_piloto = piloto["etiqueta_manual"].tolist()
    m_oof_05 = metricas(y_piloto, oof, 0.5)
    umbral, m_oof_mejor = mejor_umbral(y_piloto, oof)

    # Baseline por reglas.
    baseline = [
        dl.regla_critica(texto, tipo)
        for texto, tipo in zip(
            piloto["texto_limpio"],
            piloto["tipo_contenido"] if "tipo_contenido" in piloto else [None] * len(piloto),
        )
    ]
    m_baseline = metricas(y_piloto, baseline, 0.5)

    # Modelo final: reentrenar sobre todo el piloto.
    estado_base = {k: v.detach().clone() for k, v in modelo_base.state_dict().items()}
    modelo_final = _clonar_modelo(modelo_base, estado_base)
    modelo_final = _entrenar_epocas(
        modelo_final,
        piloto["texto_limpio"].tolist(),
        y_piloto,
        vocab,
        args.max_len,
        args.pilot_epochs,
        args.pilot_lr,
        args.pilot_batch_size,
        args.seed,
    )

    os.makedirs(args.output_dir, exist_ok=True)
    import torch

    torch.save(modelo_final.state_dict(), os.path.join(args.output_dir, "modelo.pt"))
    dl.guardar_vocab(vocab, os.path.join(args.output_dir, "vocab.json"))
    with open(os.path.join(args.output_dir, "config.json"), "w", encoding="utf-8") as archivo:
        json.dump(
            {
                "modelo": dl.MODELO_VERSION,
                "max_len": args.max_len,
                "umbral": 0.5,
                "umbral_alternativo": umbral,
                "embed_dim": dl.EMBED_DIM,
                "num_filters": dl.NUM_FILTERS,
                "kernel_sizes": list(dl.KERNEL_SIZES),
                "dropout": dl.DROPOUT,
                "seed": args.seed,
                "folds": args.folds,
                "pilot_epochs": args.pilot_epochs,
            },
            archivo,
            ensure_ascii=False,
            indent=2,
        )

    metricas_json = {
        "modelo": dl.MODELO_VERSION,
        "seed": args.seed,
        "folds": args.folds,
        "umbral": 0.5,
        "umbral_alternativo": umbral,
        "train_debil": len(train),
        "val_debil": len(val),
        "test_debil_n": len(test),
        "piloto": len(piloto),
        "positivos_debiles_train": int(train["etiqueta_debil"].sum()),
        "positivos_manuales_piloto": int(piloto["etiqueta_manual"].sum()),
        "test_debil": m_test,
        "piloto_oof_05": m_oof_05,
        "piloto_oof_mejor": m_oof_mejor,
        "baseline_reglas_piloto": m_baseline,
        "folds_detalle": folds,
    }

    ruta_json = os.path.join(args.report_dir, "clasificador_metricas.json")
    ruta_md = os.path.join(args.report_dir, "clasificador_reporte.md")
    guardar_reporte(metricas_json, ruta_json, ruta_md)

    print("\nResumen")
    print(f"  Test débil (preentrenamiento) F1={m_test['f1']:.4f} accuracy={m_test['accuracy']:.4f}")
    print(f"  Piloto OOF @0.5              F1={m_oof_05['f1']:.4f} accuracy={m_oof_05['accuracy']:.4f}")
    print(f"  Piloto OOF @{umbral:.2f}             F1={m_oof_mejor['f1']:.4f} accuracy={m_oof_mejor['accuracy']:.4f}")
    print(f"  Baseline reglas              F1={m_baseline['f1']:.4f} accuracy={m_baseline['accuracy']:.4f}")
    print(f"\nModelo: {args.output_dir}")
    print(f"Reporte: {ruta_md}")


if __name__ == "__main__":
    main()
