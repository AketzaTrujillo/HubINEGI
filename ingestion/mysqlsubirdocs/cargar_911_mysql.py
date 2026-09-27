import json
from pathlib import Path
import mysql.connector

# =========================
# CONFIGURACIÓN
# =========================

RUTA_JSON = Path(
    "data/processed/pdfs_chunks_limpios/911_SESPC_chunks.json"
)

ID_DOCUMENTO = 15

# Ajusta estos datos a los mismos que utilizas
# para conectarte a HUBDATOS.
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Chelsea1302*",
    database="HUBDATOS"
)

cursor = conexion.cursor()

try:
    # =========================
    # CARGAR CHUNKS
    # =========================

    with open(RUTA_JSON, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Chunks encontrados en JSON: {len(chunks)}")

    # Seguridad: esperamos exactamente 78
    if len(chunks) != 78:
        raise ValueError(
            f"Se esperaban 78 chunks, pero se encontraron {len(chunks)}."
        )

    # =========================
    # VERIFICAR DOCUMENTO
    # =========================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM documentos
        WHERE id_documento = %s
        """,
        (ID_DOCUMENTO,)
    )

    existe = cursor.fetchone()[0]

    if existe != 1:
        raise ValueError(
            f"No se encontró id_documento={ID_DOCUMENTO}."
        )

    # =========================
    # VERIFICAR QUE ESTÉ VACÍO
    # =========================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM fragmentos_documentos
        WHERE id_documento = %s
        """,
        (ID_DOCUMENTO,)
    )

    existentes = cursor.fetchone()[0]

    if existentes != 0:
        raise ValueError(
            f"El documento ya tiene {existentes} fragmentos. "
            "Se cancela la carga para evitar duplicados."
        )

    # =========================
    # INSERTAR
    # =========================

    sql = """
        INSERT INTO fragmentos_documentos
        (
            id_documento,
            chunk_id,
            pagina,
            texto,
            embedding,
            modelo_embedding,
            fecha_embedding
        )
        VALUES (%s, %s, %s, %s, NULL, NULL, NULL)
    """

    for chunk in chunks:

        cursor.execute(
            sql,
            (
                ID_DOCUMENTO,
                chunk["chunk_id"],
                chunk["pagina"],
                chunk["texto"]
            )
        )

    # =========================
    # ACTUALIZAR DOCUMENTO
    # =========================

    cursor.execute(
        """
        UPDATE documentos
        SET total_chunks = %s,
            incluido_rag = 1
        WHERE id_documento = %s
        """,
        (len(chunks), ID_DOCUMENTO)
    )

    # Guardar TODO junto
    conexion.commit()

    print("\n==============================")
    print("CARGA 911_SESPC COMPLETADA")
    print("==============================")
    print(f"Documento ID: {ID_DOCUMENTO}")
    print(f"Fragmentos insertados: {len(chunks)}")
    print("incluido_rag: 1")
    print("Embeddings: pendientes")

except Exception as e:
    conexion.rollback()

    print("\n❌ ERROR")
    print(e)
    print("No se guardaron cambios en MySQL.")

finally:
    cursor.close()
    conexion.close()