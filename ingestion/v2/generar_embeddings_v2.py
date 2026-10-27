"""Genera los embeddings de los fragmentos v2 (Fase 2 mejorada).

- Lee fragmentos_documentos_v2.
- Usa un modelo de retrieval multilingüe (por defecto e5-small, 512 tokens).
- Guarda el vector como BLOB float32 (384 * 4 bytes), no como JSON.
- Es idempotente por hash de texto, modelo y dimensiones.

Uso:
    cd ingestion/v2
    python generar_embeddings_v2.py
    python generar_embeddings_v2.py --force
    python generar_embeddings_v2.py --dry-run
"""
import argparse
import hashlib
import os
import sys
import time
from datetime import datetime

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

from database import obtener_conexion  # noqa: E402

MODELO = os.environ.get("MHUB_V2_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
BATCH = int(os.environ.get("MHUB_V2_EMBEDDING_BATCH", "32"))


def sha256(texto):
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()


def prefijo_pasaje(modelo):
    return "passage: " if "e5" in modelo.lower() else ""


def leer_fragmentos(limite=None):
    sql = """
        SELECT id_fragmento_v2, texto, embedding, hash_texto,
               modelo_embedding, dimensiones
        FROM fragmentos_documentos_v2
        WHERE texto IS NOT NULL AND TRIM(texto) <> ''
        ORDER BY id_fragmento_v2
    """
    if limite:
        sql += f" LIMIT {int(limite)}"
    conexion = obtener_conexion("HUBDATOS")
    cursor = conexion.cursor(dictionary=True)
    cursor.execute(sql)
    filas = cursor.fetchall()
    cursor.close()
    conexion.close()
    return filas


def pendientes(filas, modelo, dimensiones, force=False):
    objetivo = []
    for fila in filas:
        if force:
            objetivo.append(fila)
            continue
        if not fila["embedding"] or not fila["hash_texto"]:
            objetivo.append(fila)
            continue
        if fila["hash_texto"] != sha256(fila["texto"]):
            objetivo.append(fila)
            continue
        if fila["modelo_embedding"] != modelo:
            objetivo.append(fila)
            continue
        if int(fila["dimensiones"] or 0) != dimensiones:
            objetivo.append(fila)
            continue
    return objetivo


def cargar_modelo(nombre):
    from sentence_transformers import SentenceTransformer

    inicio = time.perf_counter()
    modelo = SentenceTransformer(nombre, device="cpu")
    dimensiones = modelo.get_sentence_embedding_dimension()
    print(f"[v2] modelo {nombre} cargado en {time.perf_counter() - inicio:.2f} s")
    print(f"[v2] dimensiones: {dimensiones}; max_seq_length: {modelo.max_seq_length}")
    return modelo, dimensiones


def guardar_lote(conexion, lote, vectores, modelo, dimensiones):
    cursor = conexion.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    datos = []
    for fila, vector in zip(lote, vectores):
        datos.append((
            vector.astype("float32").tobytes(),
            modelo,
            dimensiones,
            sha256(fila["texto"]),
            ahora,
            fila["id_fragmento_v2"],
        ))
    cursor.executemany("""
        UPDATE fragmentos_documentos_v2
        SET embedding = %s,
            modelo_embedding = %s,
            dimensiones = %s,
            hash_texto = %s,
            fecha_embedding = %s
        WHERE id_fragmento_v2 = %s
    """, datos)
    conexion.commit()
    cursor.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=MODELO)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    inicio = time.perf_counter()
    filas = leer_fragmentos(args.limite)
    print(f"[v2] fragmentos leídos: {len(filas)}")
    if not filas:
        raise SystemExit("No hay fragmentos v2. Ejecuta primero rechunk_corpus.py.")

    # Se cargan dimensiones del modelo solo si hay trabajo; para el filtro
    # inicial se asume 384 y se corrige después de cargar el modelo.
    objetivo = pendientes(filas, args.modelo, 384, force=args.force)
    print(f"[v2] por procesar (estimado): {len(objetivo)}")

    if args.dry_run:
        print("[v2] dry-run: no se genera nada.")
        return

    if not objetivo and not args.force:
        print("[v2] todos los embeddings están actualizados.")
        return

    modelo, dimensiones = cargar_modelo(args.modelo)
    objetivo = pendientes(filas, args.modelo, dimensiones, force=args.force)
    print(f"[v2] por procesar: {len(objetivo)} | omitidos: {len(filas) - len(objetivo)}")

    if not objetivo:
        print("[v2] no hay nada pendiente con las dimensiones del modelo.")
        return

    prefijo = prefijo_pasaje(args.modelo)
    conexion = obtener_conexion("HUBDATOS")
    procesados = 0
    errores = 0
    inicio_cod = time.perf_counter()

    for i in range(0, len(objetivo), args.batch):
        lote = objetivo[i:i + args.batch]
        try:
            vectores = modelo.encode(
                [prefijo + f["texto"] for f in lote],
                batch_size=args.batch,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            guardar_lote(conexion, lote, vectores, args.modelo, dimensiones)
            procesados += len(lote)
            if procesados % (args.batch * 20) == 0 or procesados == len(objetivo):
                print(f"[v2] {procesados}/{len(objetivo)} guardados")
        except Exception as error:
            errores += len(lote)
            print(f"[v2] error en lote {i // args.batch + 1}: {error}")

    conexion.close()
    print("\n" + "=" * 60)
    print(f"Fragmentos leídos:     {len(filas)}")
    print(f"Fragmentos procesados: {procesados}")
    print(f"Errores:               {errores}")
    print(f"Tiempo codificación:   {time.perf_counter() - inicio_cod:.2f} s")
    print(f"Tiempo total:          {time.perf_counter() - inicio:.2f} s")
    print(f"Modelo:                {args.modelo}")
    print(f"Dimensiones:           {dimensiones}")


if __name__ == "__main__":
    main()
