import json
import mysql.connector
from sentence_transformers import SentenceTransformer


# =========================
# CONFIGURACIÓN
# =========================

NOMBRE_MODELO = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

BATCH_SIZE = 32


# =========================
# CONEXIÓN A MYSQL
# =========================

conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Chelsea1302*",
    database="HUBDATOS"
)

cursor = conexion.cursor()


# =========================
# CARGAR MODELO
# =========================

print("Cargando modelo...")

modelo = SentenceTransformer(NOMBRE_MODELO)

print("✓ Modelo cargado")


# =========================
# OBTENER FRAGMENTOS
# =========================

cursor.execute("""
    SELECT id_fragmento, texto
    FROM fragmentos_documentos
    WHERE embedding IS NULL
    ORDER BY id_fragmento
""")

fragmentos = cursor.fetchall()

print(f"Fragmentos pendientes: {len(fragmentos)}")


if not fragmentos:
    print("No hay fragmentos pendientes de procesar.")
    cursor.close()
    conexion.close()
    exit()


# =========================
# GENERAR EMBEDDINGS
# =========================

ids = [fila[0] for fila in fragmentos]
textos = [fila[1] for fila in fragmentos]

print("\nGenerando embeddings...")

embeddings = modelo.encode(
    textos,
    batch_size=BATCH_SIZE,
    normalize_embeddings=True,
    show_progress_bar=True
)

print(f"✓ Embeddings generados: {len(embeddings)}")
print(f"✓ Dimensiones: {embeddings.shape[1]}")


# =========================
# GUARDAR EN MYSQL
# =========================

print("\nGuardando embeddings en MySQL...")

sql = """
    UPDATE fragmentos_documentos
    SET embedding = %s,
        modelo_embedding = %s,
        fecha_embedding = NOW()
    WHERE id_fragmento = %s
"""

for id_fragmento, embedding in zip(ids, embeddings):

    embedding_json = json.dumps(
        embedding.tolist()
    )

    cursor.execute(
        sql,
        (
            embedding_json,
            NOMBRE_MODELO,
            id_fragmento
        )
    )


conexion.commit()

print(f"✓ {len(ids)} embeddings guardados correctamente.")


# =========================
# CERRAR CONEXIÓN
# =========================

cursor.close()
conexion.close()

print("\nProceso terminado.")