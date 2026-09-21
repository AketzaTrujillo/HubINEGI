from sentence_transformers import SentenceTransformer

# Modelo multilingüe que utilizaremos para generar los embeddings
NOMBRE_MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

print("Cargando modelo...")

modelo = SentenceTransformer(NOMBRE_MODELO)

texto = """
La violencia psicológica puede manifestarse mediante amenazas,
humillaciones, insultos y conductas de control.
"""

print("Generando embedding...")

embedding = modelo.encode(
    texto,
    normalize_embeddings=True
)

print("\nModelo:", NOMBRE_MODELO)
print("Dimensiones:", embedding.shape)
print("Tipo:", type(embedding))

print("\nPrimeros 10 valores:")
print(embedding[:10])