"""Verifica los embeddings de fragmentos_documentos_v2.

Uso:
    cd ingestion/v2
    python verificar_v2.py
"""
import hashlib
import json
import os
import sys

import numpy as np

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

from database import obtener_conexion  # noqa: E402


def sha256(texto):
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()


def main():
    conexion = obtener_conexion("HUBDATOS")
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT id_fragmento_v2, texto, embedding, modelo_embedding,
               dimensiones, hash_texto, fecha_embedding
        FROM fragmentos_documentos_v2
        WHERE texto IS NOT NULL AND TRIM(texto) <> ''
        ORDER BY id_fragmento_v2
    """)
    filas = cursor.fetchall()
    cursor.close()
    conexion.close()

    nulos = 0
    dimensiones_malas = 0
    hashes_malos = 0
    modelos = {}
    normas = []
    vectores = {}

    for fila in filas:
        dimensiones = int(fila["dimensiones"] or 0)
        if not fila["embedding"]:
            nulos += 1
            continue
        if dimensiones <= 0 or len(fila["embedding"]) != dimensiones * 4:
            dimensiones_malas += 1
            continue
        vector = np.frombuffer(fila["embedding"], dtype=np.float32)
        if vector.shape != (dimensiones,):
            dimensiones_malas += 1
            continue
        if fila["hash_texto"] != sha256(fila["texto"]):
            hashes_malos += 1
        modelos[fila["modelo_embedding"]] = modelos.get(fila["modelo_embedding"], 0) + 1
        normas.append(float(np.linalg.norm(vector)))
        vectores[fila["id_fragmento_v2"]] = vector

    print("=" * 64)
    print("VERIFICACIÓN DE EMBEDDINGS v2 — HUBDATOS.fragmentos_documentos_v2")
    print("=" * 64)
    print(f"Fragmentos v2                   : {len(filas)}")
    print(f"Embeddings no nulos             : {len(vectores)}")
    print(f"Embeddings nulos                : {nulos}")
    print(f"Dimensiones/longitud incorrectas : {dimensiones_malas}")
    print(f"Hashes desactualizados          : {hashes_malos}")
    print(f"Modelos                         : {modelos or '(ninguno)'}")
    if normas:
        print(f"Norma L2 (min / media / max)    : "
              f"{min(normas):.6f} / {sum(normas) / len(normas):.6f} / {max(normas):.6f}")

    ids = sorted(vectores)
    sim_rel = sim_ajena = None
    if len(ids) >= 20:
        a, b, c = ids[10], ids[11], ids[-1]
        sim_rel = float(np.dot(vectores[a], vectores[b]))
        sim_ajena = float(np.dot(vectores[a], vectores[c]))
        print("\nMuestra de similitud (producto punto):")
        print(f"  {a} vs {b} (contiguos): {sim_rel:.4f}")
        print(f"  {a} vs {c} (distante) : {sim_ajena:.4f}")

    datos = {
        "fecha": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_fragmentos": len(filas),
        "embeddings_no_nulos": len(vectores),
        "embeddings_nulos": nulos,
        "dimensiones": int(filas[0]["dimensiones"] or 0) if filas else 0,
        "dimensiones_incorrectas": dimensiones_malas,
        "hashes_desactualizados": hashes_malos,
        "modelos": modelos,
        "norma_l2": {
            "min": round(min(normas), 6) if normas else 0.0,
            "media": round(sum(normas) / len(normas), 6) if normas else 0.0,
            "max": round(max(normas), 6) if normas else 0.0,
        },
        "muestra_similitud": {
            "fragmentos_contiguos": round(sim_rel, 4) if sim_rel is not None else None,
            "fragmentos_distantes": round(sim_ajena, 4) if sim_ajena is not None else None,
        },
        "resultado": "ERROR" if (
            nulos or dimensiones_malas or hashes_malos or len(vectores) != len(filas)
        ) else "OK",
    }
    reports = os.path.join(BASE, "reports")
    os.makedirs(reports, exist_ok=True)
    with open(os.path.join(reports, "embeddings_verificacion_v2.json"), "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)

    errores = (
        nulos != 0 or dimensiones_malas != 0 or hashes_malos != 0
        or len(vectores) != len(filas)
    )
    print("\n" + "=" * 64)
    if errores:
        print("RESULTADO: CON ERRORES")
        raise SystemExit(1)
    print("RESULTADO: OK")
    print(f"  {len(filas)} fragmentos v2 con embedding y hashes vigentes.")
    print("=" * 64)


if __name__ == "__main__":
    main()
