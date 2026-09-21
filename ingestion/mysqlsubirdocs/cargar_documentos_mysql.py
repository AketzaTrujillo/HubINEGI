from pathlib import Path
import json
import mysql.connector
import unicodedata
import fitz


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_CHUNKS = (
    BASE_DIR
    / "data"
    / "processed"
    / "pdfs_chunks_limpios"
)

CARPETA_PDFS = (
    BASE_DIR
    / "data"
    / "raw"
    / "pdfs"
)


# ============================================================
# CONEXIÓN A MYSQL
# ============================================================

conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Chelsea1302*",
    database="HUBDATOS"
)

cursor = conexion.cursor()


# ============================================================
# MAPA DOCUMENTO → id_fuente
# ============================================================

MAPA_FUENTES = {

    "01ModeloCJM_Secretariado_Ejecutivo": 7,

    "03ProtocoloEstandarizadoCJM": 7,

    "Apoyo para Espacios de Refugio Especializados para Mujeres Víctimas de Violencia de Género": 8,

    "DIRECTORIO NACIONAL DE LOS CENTROS DE JUSTICIA PARA LAS MUJERES": 6,

    "Directorio_Nacional_CJM_2024": 6,

    "LEY GENERAL DE ACCESO DE LAS MUJERES A UNA VIDA LIBRE DE VIOLENCIA": 9,

    "Lineamientos BANAVIM 16_08_2018": 10,

    "MODELO_DE_ATENCION": 11,

    "MODELO_DE_SANCION": 11,

    "Modelo_Prevencion_de_Violencias_Contra_Mujeres": 12,

    "ProtocoloAtencionCJM": 7,

    "Que_te_agrada_y_que_te_agrade_en_las_relaciones": 6,

    "Violencia_de_Genero_Contra_Mujeres_en_Zonas_Ind_genas_en_M_xico": 6,

    "noestassola_conavim": 6
}

MAPA_FUENTES = {
    unicodedata.normalize("NFC", nombre): id_fuente
    for nombre, id_fuente in MAPA_FUENTES.items()
}

# ============================================================
# CARGAR ARCHIVOS DE CHUNKS
# ============================================================

archivos_json = sorted(CARPETA_CHUNKS.glob("*.json"))

print(f"\nArchivos JSON encontrados: {len(archivos_json)}")


total_fragmentos = 0


for archivo_json in archivos_json:

    print("\n" + "=" * 70)
    print(f"Procesando: {archivo_json.name}")

    with open(archivo_json, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        print("⚠ Archivo sin chunks.")
        continue

    # El nombre del documento ya viene guardado en cada chunk.
    nombre_documento = chunks[0]["documento"]
    nombre_documento = unicodedata.normalize("NFC", nombre_documento)

    if nombre_documento not in MAPA_FUENTES:
        print(f"❌ No existe fuente para: {nombre_documento}")
        continue

    id_fuente = MAPA_FUENTES[nombre_documento]

    nombre_archivo = f"{nombre_documento}.pdf"

    ruta_pdf = CARPETA_PDFS / nombre_archivo

    # Obtener el número máximo de página presente en los chunks.
    if ruta_pdf.exists():
        with fitz.open(ruta_pdf) as pdf:
            total_paginas = len(pdf)
    else:
        total_paginas = None
    print(f"⚠ No se encontró el PDF original: {ruta_pdf}")
    total_chunks = len(chunks)


    # ========================================================
    # INSERTAR DOCUMENTO
    # ========================================================

    sql_documento = """
        INSERT INTO documentos (
            id_fuente,
            nombre,
            nombre_archivo,
            ruta_archivo,
            total_paginas,
            total_chunks,
            incluido_rag,
            observaciones
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    valores_documento = (
        id_fuente,
        nombre_documento,
        nombre_archivo,
        str(ruta_pdf),
        total_paginas,
        total_chunks,
        True,
        "Documento incluido en el corpus textual para recuperación semántica."
    )

    cursor.execute(sql_documento, valores_documento)

    id_documento = cursor.lastrowid

    print(f"Documento insertado con ID: {id_documento}")


    # ========================================================
    # INSERTAR CHUNKS
    # ========================================================

    sql_fragmento = """
        INSERT INTO fragmentos_documentos (
            id_documento,
            chunk_id,
            pagina,
            texto
        )
        VALUES (%s, %s, %s, %s)
    """

    valores_fragmentos = []

    for chunk in chunks:

        valores_fragmentos.append(
            (
                id_documento,
                chunk["chunk_id"],
                chunk.get("pagina"),
                chunk["texto"]
            )
        )

    cursor.executemany(
        sql_fragmento,
        valores_fragmentos
    )

    total_fragmentos += len(valores_fragmentos)

    print(f"Chunks insertados: {len(valores_fragmentos)}")


# ============================================================
# CONFIRMAR CAMBIOS
# ============================================================

conexion.commit()

print("\n" + "=" * 70)
print("CARGA TERMINADA")
print("=" * 70)

print(f"Documentos procesados: {len(archivos_json)}")
print(f"Fragmentos insertados: {total_fragmentos}")


cursor.close()
conexion.close()