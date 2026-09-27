import json
from pathlib import Path

# =========================
# RUTAS
# =========================

ENTRADA = Path("data/processed/911_SESPC.json")

SALIDA = Path("data/processed/pdfs_chunks_limpios/911_SESPC_chunks.json")


# =========================
# CARGAR JSON
# =========================

with open(ENTRADA, "r", encoding="utf-8") as f:
    documento = json.load(f)


# =========================
# CREAR CHUNKS
# =========================

chunks = []

for registro in documento["registros"]:

    # Solo usamos registros destinados al RAG
    if not registro.get("incluir_rag", False):
        continue

    texto = registro.get("texto_rag", "").strip()

    # Evitar chunks vacíos
    if not texto:
        continue

    chunk = {
        "documento": documento["documento"],
        "pagina": registro["pagina"],
        "chunk_id": len(chunks),
        "tema": registro.get("tema"),
        "tipo_contenido": registro.get("tipo_contenido"),
        "tipo_registro": registro.get("tipo_registro"),
        "periodo": registro.get("periodo"),
        "ambito_geografico": registro.get("ambito_geografico"),
        "texto": texto
    }

    chunks.append(chunk)


# =========================
# GUARDAR
# =========================

with open(SALIDA, "w", encoding="utf-8") as f:
    json.dump(
        chunks,
        f,
        ensure_ascii=False,
        indent=2
    )


# =========================
# RESUMEN
# =========================

print("\n==============================")
print("CHUNKS 911_SESPC GENERADOS")
print("==============================")

print(f"Documento: {documento['documento']}")
print(f"Registros originales: {len(documento['registros'])}")
print(f"Chunks para RAG: {len(chunks)}")
print(f"Archivo generado: {SALIDA}")

if chunks:
    print(f"Primer chunk: página {chunks[0]['pagina']}")
    print(f"Último chunk: página {chunks[-1]['pagina']}")