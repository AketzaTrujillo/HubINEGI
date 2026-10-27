"""Verifica la integridad de los embeddings del corpus (Fase 2).

Comprueba:
- fragmentos con incluido_faq = 1;
- embeddings no nulos y con 384 dimensiones;
- hash_texto vigente contra SHA-256 del texto;
- modelo y fecha de generación;
- norma de los vectores;
- similitud de muestra entre fragmentos relacionados y no relacionados.

Uso:
    cd ingestion/embeddings
    python verificar_embeddings.py
"""
import hashlib
import json
import os
import sys

import numpy as np

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

from database import obtener_conexion  # noqa: E402

DIMENSIONES = 384


def sha256(texto):
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()


def main():
    conexion = obtener_conexion("HUBDATOS")
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS n
        FROM fragmentos_documentos f
        JOIN documentos d ON d.id_documento = f.id_documento
        WHERE d.incluido_faq = 1
          AND f.texto IS NOT NULL
          AND TRIM(f.texto) <> ''
    """)
    total = cursor.fetchone()["n"]

    cursor.execute("""
        SELECT f.id_fragmento, f.texto, f.embedding, f.modelo_embedding,
               f.dimensiones, f.hash_texto, f.fecha_embedding
        FROM fragmentos_documentos f
        JOIN documentos d ON d.id_documento = f.id_documento
        WHERE d.incluido_faq = 1
          AND f.texto IS NOT NULL
          AND TRIM(f.texto) <> ''
        ORDER BY f.id_fragmento
    """)
    filas = cursor.fetchall()
    cursor.close()
    conexion.close()

    nulos = 0
    dimensiones_malas = 0
    hashes_malos = 0
    modelos = {}
    fechas = []
    normas = []
    vectores = {}

    for fila in filas:
        if not fila["embedding"]:
            nulos += 1
            continue
        try:
            vector = np.asarray(json.loads(fila["embedding"]), dtype=np.float32)
        except (TypeError, ValueError, json.JSONDecodeError):
            dimensiones_malas += 1
            continue

        if vector.shape != (DIMENSIONES,):
            dimensiones_malas += 1
            continue
        if int(fila["dimensiones"] or 0) != DIMENSIONES:
            dimensiones_malas += 1

        if fila["hash_texto"] != sha256(fila["texto"]):
            hashes_malos += 1

        modelos[fila["modelo_embedding"]] = modelos.get(fila["modelo_embedding"], 0) + 1
        if fila["fecha_embedding"]:
            fechas.append(fila["fecha_embedding"])
        normas.append(float(np.linalg.norm(vector)))
        vectores[fila["id_fragmento"]] = vector

    print("=" * 62)
    print("VERIFICACIÓN DE EMBEDDINGS — HUBDATOS.fragmentos_documentos")
    print("=" * 62)
    print(f"Fragmentos con incluido_faq = 1 : {total}")
    print(f"Filas leídas                    : {len(filas)}")
    print(f"Embeddings no nulos             : {len(vectores)}")
    print(f"Embeddings nulos               : {nulos}")
    print(f"Dimensiones incorrectas         : {dimensiones_malas}")
    print(f"Hashes desactualizados          : {hashes_malos}")
    print(f"Modelos                        : {modelos or '(ninguno)'}")
    if fechas:
        print(f"Fechas de generación           : {min(fechas)} → {max(fechas)}")
    if normas:
        print(f"Norma L2 (min / media / max)   : "
              f"{min(normas):.6f} / {sum(normas) / len(normas):.6f} / {max(normas):.6f}")

    # Muestra de similitud: dos fragmentos del mismo documento y uno ajeno.
    ids = sorted(vectores)
    if len(ids) >= 3:
        a, b, c = ids[100], ids[101], ids[-1]
        sim_rel = float(np.dot(vectores[a], vectores[b]))
        sim_ajena = float(np.dot(vectores[a], vectores[c]))
        print("\nMuestra de similitud (producto punto, vectores normalizados):")
        print(f"  fragmento {a} vs {b} (contiguos) : {sim_rel:.4f}")
        print(f"  fragmento {a} vs {c} (distante) : {sim_ajena:.4f}")

    errores = (
        (nulos != 0)
        or (dimensiones_malas != 0)
        or (hashes_malos != 0)
        or (len(vectores) != total)
    )

    print("\n" + "=" * 62)
    if errores:
        print("RESULTADO: CON ERRORES — revisar los conteos anteriores.")
        raise SystemExit(1)
    print("RESULTADO: OK")
    print(f"  {total} fragmentos con embedding de {DIMENSIONES} dimensiones,")
    print("  hashes vigentes y sin nulos inesperados.")
    print("=" * 62)


if __name__ == "__main__":
    main()
