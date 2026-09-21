from pathlib import Path
import unicodedata
import fitz
import mysql.connector


# ============================================================
# RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
CARPETA_PDFS = BASE_DIR / "data" / "raw" / "pdfs"


def normalizar(texto):
    return unicodedata.normalize("NFC", texto)


# ============================================================
# CONEXIÓN MYSQL
# ============================================================

conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Chelsea1302*",
    database="HUBDATOS"
)

cursor = conexion.cursor()


# ============================================================
# PDF REALES
# ============================================================

pdfs = list(CARPETA_PDFS.glob("*.pdf"))

pdfs_normalizados = {
    normalizar(pdf.stem): pdf
    for pdf in pdfs
}

print(f"PDF encontrados: {len(pdfs)}")


# ============================================================
# DOCUMENTOS YA GUARDADOS EN MYSQL
# ============================================================

cursor.execute("""
    SELECT id_documento, nombre
    FROM documentos
""")

documentos = cursor.fetchall()


for id_documento, nombre in documentos:

    nombre_normalizado = normalizar(nombre)

    pdf = pdfs_normalizados.get(nombre_normalizado)

    if pdf is None:
        print(f"❌ No encontrado: {nombre}")
        continue

    with fitz.open(pdf) as documento_pdf:
        total_paginas = len(documento_pdf)

    cursor.execute(
        """
        UPDATE documentos
        SET nombre_archivo = %s,
            ruta_archivo = %s,
            total_paginas = %s
        WHERE id_documento = %s
        """,
        (
            pdf.name,
            str(pdf),
            total_paginas,
            id_documento
        )
    )

    print(
        f"✓ {pdf.name} "
        f"→ {total_paginas} páginas"
    )


conexion.commit()

cursor.close()
conexion.close()

print("\nActualización terminada.")