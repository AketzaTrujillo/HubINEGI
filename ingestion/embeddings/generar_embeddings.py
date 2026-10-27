"""Genera y actualiza los embeddings del corpus documental (Fase 2).

- Lee la conexión de backend/.env (vía backend/database.py).
- Solo procesa fragmentos de documentos con incluido_faq = 1.
- Es idempotente: omite filas cuyo hash de texto no cambió, cuyo modelo
  coincide y que ya tienen un embedding de las dimensiones esperadas.
- Guarda embedding (JSON), modelo_embedding, dimensiones, hash_texto y
  fecha_embedding.

Uso:
    cd ingestion/embeddings
    python generar_embeddings.py
    python generar_embeddings.py --force
    python generar_embeddings.py --limite 20 --dry-run
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

from database import obtener_conexion  # noqa: E402

MODELO = os.environ.get(
    "MHUB_EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
DIMENSIONES = 384
BATCH = int(os.environ.get("MHUB_EMBEDDING_BATCH", "32"))


def sha256(texto):
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()


def leer_fragmentos(limite=None):
    sql = """
        SELECT f.id_fragmento, f.texto, f.embedding, f.hash_texto,
               f.modelo_embedding, f.dimensiones, d.nombre AS documento
        FROM fragmentos_documentos f
        JOIN documentos d ON d.id_documento = f.id_documento
        WHERE d.incluido_faq = 1
          AND f.texto IS NOT NULL
          AND TRIM(f.texto) <> ''
        ORDER BY f.id_fragmento
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


def pendientes(filas, modelo_nombre, force=False):
    objetivo = []
    for fila in filas:
        hash_actual = sha256(fila["texto"])
        if force:
            objetivo.append(fila)
            continue
        if fila["embedding"] is None or not fila["hash_texto"]:
            objetivo.append(fila)
            continue
        if fila["hash_texto"] != hash_actual:
            objetivo.append(fila)
            continue
        if fila["modelo_embedding"] != modelo_nombre:
            objetivo.append(fila)
            continue
        if int(fila["dimensiones"] or 0) != DIMENSIONES:
            objetivo.append(fila)
            continue
    return objetivo


def cargar_modelo(modelo_nombre):
    from sentence_transformers import SentenceTransformer

    inicio = time.perf_counter()
    modelo = SentenceTransformer(modelo_nombre, device="cpu")
    print(f"[modelo] {modelo_nombre} cargado en {time.perf_counter() - inicio:.2f} s")
    print(f"[modelo] dimensión reportada: {modelo.get_sentence_embedding_dimension()}")
    return modelo


def guardar_lote(conexion, lote, vectores, modelo_nombre):
    cursor = conexion.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    datos = []
    for fila, vector in zip(lote, vectores):
        datos.append((
            json.dumps([float(x) for x in vector]),
            modelo_nombre,
            DIMENSIONES,
            sha256(fila["texto"]),
            ahora,
            fila["id_fragmento"],
        ))
    cursor.executemany(
        """
        UPDATE fragmentos_documentos
        SET embedding = %s,
            modelo_embedding = %s,
            dimensiones = %s,
            hash_texto = %s,
            fecha_embedding = %s
        WHERE id_fragmento = %s
        """,
        datos,
    )
    conexion.commit()
    cursor.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=MODELO)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="regenerar todo")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    modelo_nombre = args.modelo

    inicio = time.perf_counter()
    print(f"[corpus] leyendo fragmentos de HUBDATOS…")
    filas = leer_fragmentos(args.limite)
    print(f"[corpus] fragmentos leídos: {len(filas)}")

    objetivo = pendientes(filas, modelo_nombre, force=args.force)
    omitidos = len(filas) - len(objetivo)
    print(f"[corpus] por procesar: {len(objetivo)} | omitidos: {omitidos}")

    if args.dry_run:
        print("[dry-run] no se generó ni guardó ningún embedding.")
        return

    if not objetivo:
        print("[ok] todos los embeddings están actualizados.")
        print(f"[tiempo] {time.perf_counter() - inicio:.2f} s")
        return

    modelo = cargar_modelo(modelo_nombre)

    conexion = obtener_conexion("HUBDATOS")
    procesados = 0
    errores = 0
    inicio_codificacion = time.perf_counter()

    for i in range(0, len(objetivo), args.batch):
        lote = objetivo[i:i + args.batch]
        try:
            vectores = modelo.encode(
                [f["texto"] for f in lote],
                batch_size=args.batch,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            guardar_lote(conexion, lote, vectores, modelo_nombre)
            procesados += len(lote)
            print(f"[lote] {procesados}/{len(objetivo)} guardados")
        except Exception as error:
            errores += len(lote)
            print(f"[error] lote {i // args.batch + 1}: {error}")

    conexion.close()
    transcurrido = time.perf_counter() - inicio
    codificacion = time.perf_counter() - inicio_codificacion

    print("\n" + "=" * 60)
    print(f"Fragmentos leídos:      {len(filas)}")
    print(f"Fragmentos procesados:  {procesados}")
    print(f"Fragmentos omitidos:    {omitidos}")
    print(f"Errores:                {errores}")
    print(f"Tiempo codificación:    {codificacion:.2f} s")
    print(f"Tiempo total:           {transcurrido:.2f} s")
    print(f"Modelo:                 {MODELO}")
    print(f"Dimensiones:            {DIMENSIONES}")


if __name__ == "__main__":
    main()
