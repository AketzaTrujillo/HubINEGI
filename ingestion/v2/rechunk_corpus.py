"""Re-fragmenta el corpus para la recuperación v2 (Fase 2 mejorada).

Problema que corrige:
- Los fragmentos v1 son páginas completas (~271 tokens de mediana).
- El modelo MiniLM de v1 tiene max_seq_length=128, así que truncaba el 80.9%
  de los fragmentos.

Esta versión:
1. Reconstruye cada página concatenando sus fragmentos v1.
2. Elimina ruido típico: números de página, líneas repetidas (encabezados/pies),
   índices con puntos y líneas vacías.
3. Corta por oraciones en trozos de ~350 tokens con 50 de solapamiento
   (configurable para el modelo que se use).
4. Guarda en fragmentos_documentos_v2 sin tocar la tabla v1.

Uso:
    cd ingestion/v2
    python rechunk_corpus.py
    python rechunk_corpus.py --chunk-tokens 350 --overlap 50
    python rechunk_corpus.py --dry-run
"""
import argparse
import hashlib
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

from database import obtener_conexion  # noqa: E402

MODELO = os.environ.get("MHUB_V2_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
CHUNK_TOKENS = int(os.environ.get("MHUB_V2_CHUNK_TOKENS", "350"))
OVERLAP = int(os.environ.get("MHUB_V2_CHUNK_OVERLAP", "50"))


def normalizar_espacios(texto):
    texto = (texto or "").replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto)
    return texto.strip()


def sin_acentos(texto):
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def es_ruido(linea, nombre_documento):
    l = linea.strip()
    if not l:
        return True
    if re.fullmatch(r"\d{1,4}", l):
        return True
    if re.fullmatch(r"[-–—_.,;:()\[\]{} ]+", l):
        return True
    if re.search(r"\.{5,}", l):
        return True
    if sin_acentos(l).lower() == sin_acentos(nombre_documento).lower():
        return True
    if len(l) <= 3 and not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", l):
        return True
    return False


def lineas_frecuentes(paginas, nombre_documento):
    """Líneas que aparecen en muchas páginas suelen ser encabezados/pies."""
    apariciones = Counter()
    total_paginas = len(paginas)
    for texto in paginas:
        vistas = set()
        for linea in texto.split("\n"):
            l = linea.strip()
            if not l or len(l) > 120:
                continue
            vistas.add(l)
        apariciones.update(vistas)

    umbral = max(3, int(total_paginas * 0.30))
    frecuentes = {
        linea for linea, n in apariciones.items()
        if n >= umbral and not re.search(r"\.{5,}", linea)
    }
    frecuentes.add(nombre_documento.strip())
    return frecuentes


def limpiar_pagina(texto, nombre_documento, frecuentes):
    salida = []
    for linea in texto.split("\n"):
        if es_ruido(linea, nombre_documento):
            continue
        l = linea.strip()
        if l in frecuentes:
            continue
        salida.append(l)
    return normalizar_espacios("\n".join(salida))


def unidades_oraciones(texto):
    """Divide en oraciones y conserva los saltos de línea como cortes."""
    texto = re.sub(r"(?<=[.!?])\s+", "\n", texto)
    partes = [p.strip() for p in texto.split("\n") if p.strip()]
    return partes


class ContadorTokens:
    def __init__(self, modelo):
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(modelo)

    def contar(self, texto):
        return len(self.tokenizer(texto, add_special_tokens=False)["input_ids"])

    def contar_muchos(self, textos):
        return [
            len(ids)
            for ids in self.tokenizer(
                textos, add_special_tokens=False, truncation=False
            )["input_ids"]
        ]


def es_chunk_ruido(texto, tokens):
    """Descarta portadas, créditos e índices que no responden preguntas."""
    n = sin_acentos(texto).lower()
    if tokens < 30:
        return True
    if tokens < 40 and not re.search(r"[.!?]", texto):
        return True
    if tokens < 180 and any(
        marca in n for marca in (
            "prohibida su venta", "isbn", "impreso en mexico",
            "diseno de portada", "publicaciones@", "primera edicion",
        )
    ):
        return True
    if n.startswith("contenido") and tokens < 280 and "presentacion" in n:
        return True
    if n.startswith("bibliografia glosario apendice") and tokens < 80:
        return True
    return False


def trocear_texto(texto, pagina, id_origen, contador, chunk_tokens, overlap):
    """Corta por oraciones acumulando tokens, con solapamiento por oración."""
    unidades = unidades_oraciones(texto)
    if not unidades:
        return []

    # Si una oración es enorme, se parte por palabras.
    expandidas = []
    for unidad in unidades:
        if contador.contar(unidad) <= chunk_tokens:
            expandidas.append(unidad)
            continue
        palabras = unidad.split()
        actual = []
        for palabra in palabras:
            actual.append(palabra)
            if contador.contar(" ".join(actual)) >= chunk_tokens:
                expandidas.append(" ".join(actual))
                actual = []
        if actual:
            expandidas.append(" ".join(actual))

    chunks = []
    actual = []
    tokens_actual = 0
    for unidad in expandidas:
        n = contador.contar(unidad)
        if actual and tokens_actual + n > chunk_tokens:
            texto_chunk = " ".join(actual).strip()
            if texto_chunk:
                chunks.append(texto_chunk)
            # Solapamiento: conservar las últimas oraciones hasta `overlap`.
            solape = []
            tokens_solape = 0
            for previa in reversed(actual):
                n_previa = contador.contar(previa)
                if tokens_solape + n_previa > overlap:
                    break
                solape.insert(0, previa)
                tokens_solape += n_previa
            actual = solape
            tokens_actual = tokens_solape
        actual.append(unidad)
        tokens_actual += n

    if actual:
        texto_chunk = " ".join(actual).strip()
        if texto_chunk:
            chunks.append(texto_chunk)

    return [
        {
            "texto": chunk,
            "pagina": pagina,
            "id_fragmento_origen": id_origen,
            "tokens": contador.contar(chunk),
        }
        for chunk in chunks
        if contador.contar(chunk) >= 10
        and not es_chunk_ruido(chunk, contador.contar(chunk))
    ]


def leer_paginas(conexion):
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT f.id_fragmento, f.id_documento, f.pagina, f.texto,
               d.nombre AS documento
        FROM fragmentos_documentos f
        JOIN documentos d ON d.id_documento = f.id_documento
        WHERE d.incluido_faq = 1
          AND f.texto IS NOT NULL
          AND TRIM(f.texto) <> ''
        ORDER BY f.id_documento, f.pagina, f.id_fragmento
    """)
    filas = cursor.fetchall()
    cursor.close()
    return filas


def agrupar(filas):
    grupos = defaultdict(list)
    for fila in filas:
        clave = (fila["id_documento"], fila["documento"], fila["pagina"])
        grupos[clave].append(fila)
    return grupos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=MODELO)
    parser.add_argument("--chunk-tokens", type=int, default=CHUNK_TOKENS)
    parser.add_argument("--overlap", type=int, default=OVERLAP)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"[v2] modelo/tokenizer: {args.modelo}")
    print(f"[v2] chunk_tokens={args.chunk_tokens} overlap={args.overlap}")
    contador = ContadorTokens(args.modelo)

    conexion = obtener_conexion("HUBDATOS")
    filas = leer_paginas(conexion)
    grupos = agrupar(filas)
    print(f"[v2] fragmentos v1 leídos: {len(filas)}")
    print(f"[v2] páginas a reconstruir: {len(grupos)}")

    # Líneas frecuentes por documento.
    por_documento = defaultdict(list)
    for (id_doc, nombre, pagina), fragmentos in grupos.items():
        por_documento[(id_doc, nombre)].append("\n".join(f["texto"] for f in fragmentos))
    frecuentes_por_doc = {
        clave: lineas_frecuentes(paginas, clave[1])
        for clave, paginas in por_documento.items()
    }

    chunks = []
    for (id_doc, nombre, pagina), fragmentos in sorted(grupos.items()):
        texto = "\n".join(f["texto"] for f in fragmentos)
        limpio = limpiar_pagina(texto, nombre, frecuentes_por_doc[(id_doc, nombre)])
        if not limpio:
            continue
        id_origen = min(f["id_fragmento"] for f in fragmentos)
        for chunk in trocear_texto(
            limpio, pagina, id_origen, contador, args.chunk_tokens, args.overlap
        ):
            chunk["id_documento"] = id_doc
            chunk["documento"] = nombre
            chunks.append(chunk)

    # Orden estable por documento/página y deduplicación exacta.
    chunks.sort(key=lambda c: (c["id_documento"], c["pagina"] or 0, c["id_fragmento_origen"] or 0))
    vistos = set()
    unicos = []
    for chunk in chunks:
        clave = (chunk["id_documento"], chunk["pagina"], hashlib.sha256(chunk["texto"].encode("utf-8")).hexdigest())
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(chunk)

    for orden, chunk in enumerate(unicos):
        chunk["orden"] = orden

    tokens = [c["tokens"] for c in unicos]
    tokens.sort()
    n = len(tokens)
    print(f"[v2] chunks generados: {n}")
    if n:
        print(f"[v2] tokens min/mediana/p90/max: "
              f"{tokens[0]} / {tokens[n // 2]} / {tokens[int(n * 0.9)]} / {tokens[-1]}")
        print(f"[v2] chunks con más de {args.chunk_tokens} tokens: "
              f"{sum(1 for t in tokens if t > args.chunk_tokens)}")

    if args.dry_run:
        print("\n[v2] muestra de chunks:")
        for chunk in unicos[:5]:
            print(f"\n--- doc={chunk['id_documento']} p={chunk['pagina']} "
                  f"tokens={chunk['tokens']} ---")
            print(chunk["texto"][:500])
        conexion.close()
        return

    cursor = conexion.cursor()
    cursor.execute("DELETE FROM fragmentos_documentos_v2")
    version = f"v2-{args.chunk_tokens}-{args.overlap}"
    datos = [
        (
            c["id_documento"], c["id_fragmento_origen"], c["pagina"], c["orden"],
            c["texto"], version,
        )
        for c in unicos
    ]
    cursor.executemany("""
        INSERT INTO fragmentos_documentos_v2
          (id_documento, id_fragmento_origen, pagina, orden, texto, version_chunk)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, datos)
    conexion.commit()
    cursor.close()
    conexion.close()
    print(f"[v2] insertados {len(datos)} chunks en fragmentos_documentos_v2")


if __name__ == "__main__":
    main()
