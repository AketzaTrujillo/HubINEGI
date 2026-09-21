import json
import re

import mysql.connector
import numpy as np

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer


# ============================================================
# CONFIGURACIÓN
# ============================================================

NOMBRE_MODELO = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Por ahora mostramos 10 para observar mejor los resultados.
TOP_K = 10

# Pesos iniciales.
# Después los evaluaremos con varias preguntas.
PESO_SEMANTICO = 0.70
PESO_LEXICO = 0.30


# ============================================================
# SIGLAS
# ============================================================

SIGLAS = {
    "banavim": (
        "Banco Nacional de Datos e Información "
        "sobre Casos de Violencia contra las Mujeres"
    ),

    "cjm": (
        "Centros de Justicia para las Mujeres"
    ),

    "conavim": (
        "Comisión Nacional para Prevenir y Erradicar "
        "la Violencia contra las Mujeres"
    ),

    "endireh": (
        "Encuesta Nacional sobre la Dinámica de las "
        "Relaciones en los Hogares"
    ),

    "sesnsp": (
        "Secretariado Ejecutivo del Sistema Nacional "
        "de Seguridad Pública"
    ),

    "inmujeres": (
        "Instituto Nacional de las Mujeres"
    ),

    "lgamvlv": (
        "Ley General de Acceso de las Mujeres "
        "a una Vida Libre de Violencia"
    ),
}


# ============================================================
# EXPANSIÓN DE SIGLAS
# ============================================================

def expandir_siglas(pregunta):

    pregunta_expandida = pregunta

    for sigla, significado in SIGLAS.items():

        patron = rf"\b{re.escape(sigla)}\b"

        if re.search(
            patron,
            pregunta,
            flags=re.IGNORECASE
        ):
            pregunta_expandida += f" ({significado})"

    return pregunta_expandida


# ============================================================
# CONEXIÓN MYSQL
# ============================================================

print("Conectando con MySQL...")

conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Chelsea1302*",
    database="HUBDATOS"
)

cursor = conexion.cursor()

print("✓ Conexión establecida")


# ============================================================
# CARGAR MODELO
# ============================================================

print("\nCargando modelo de embeddings...")

modelo = SentenceTransformer(
    NOMBRE_MODELO
)

print("✓ Modelo cargado")


# ============================================================
# CARGAR FRAGMENTOS
# ============================================================

print("\nCargando fragmentos desde MySQL...")

cursor.execute("""
    SELECT
        f.id_fragmento,
        f.texto,
        f.pagina,
        f.embedding,
        d.nombre AS documento,
        fu.nombre AS fuente
    FROM fragmentos_documentos AS f
    INNER JOIN documentos AS d
        ON f.id_documento = d.id_documento
    INNER JOIN fuentes AS fu
        ON d.id_fuente = fu.id_fuente
    WHERE f.embedding IS NOT NULL
      AND d.incluido_rag = 1
    ORDER BY f.id_fragmento
""")

filas = cursor.fetchall()

print(
    f"✓ Fragmentos cargados: {len(filas)}"
)


# ============================================================
# PREPARAR INFORMACIÓN
# ============================================================

ids = []
textos = []
paginas = []
documentos = []
fuentes = []
embeddings = []


for fila in filas:

    (
        id_fragmento,
        texto,
        pagina,
        embedding_json,
        documento,
        fuente
    ) = fila

    try:

        vector = json.loads(
            embedding_json
        )

    except (json.JSONDecodeError, TypeError):

        print(
            f"⚠ Embedding inválido: "
            f"{id_fragmento}"
        )

        continue

    if len(vector) != 384:

        print(
            f"⚠ Fragmento {id_fragmento} "
            f"tiene {len(vector)} dimensiones."
        )

        continue

    ids.append(id_fragmento)
    textos.append(texto)
    paginas.append(pagina)
    documentos.append(documento)
    fuentes.append(fuente)
    embeddings.append(vector)


# ============================================================
# MATRIZ DE EMBEDDINGS
# ============================================================

matriz_embeddings = np.asarray(
    embeddings,
    dtype=np.float32
)

print(
    "✓ Matriz de embeddings:",
    matriz_embeddings.shape
)


# ============================================================
# CREAR ÍNDICE TF-IDF
# ============================================================

print("\nCreando índice léxico TF-IDF...")


vectorizador_tfidf = TfidfVectorizer(

    # Pasamos todo a minúsculas.
    lowercase=True,

    # Elimina palabras muy comunes del español.
    stop_words=None,

    # Unigramas y bigramas.
    # Esto es importante porque permite representar:
    #
    # "violencia"
    # "sexual"
    # "violencia sexual"
    #
    ngram_range=(1, 2),

    # Ignoramos términos extremadamente raros.
    min_df=1,

    # Ignoramos términos que aparezcan prácticamente
    # en todo el corpus.
    max_df=0.95
)


matriz_tfidf = vectorizador_tfidf.fit_transform(
    textos
)


print(
    "✓ Matriz TF-IDF:",
    matriz_tfidf.shape
)


# ============================================================
# PREGUNTA DEL USUARIO
# ============================================================

pregunta = input(
    "\nEscribe tu pregunta: "
).strip()


if not pregunta:

    print("La pregunta está vacía.")

    cursor.close()
    conexion.close()

    exit()


# ============================================================
# EXPANDIR SIGLAS
# ============================================================

pregunta_expandida = expandir_siglas(
    pregunta
)


if pregunta_expandida != pregunta:

    print("\nSigla detectada.")

    print(
        "Consulta expandida:"
    )

    print(
        pregunta_expandida
    )


# ============================================================
# 1. BÚSQUEDA SEMÁNTICA
# ============================================================

embedding_pregunta = modelo.encode(
    pregunta_expandida,
    normalize_embeddings=True
)

embedding_pregunta = np.asarray(
    embedding_pregunta,
    dtype=np.float32
)


scores_semanticos = (
    matriz_embeddings
    @ embedding_pregunta
)


# ============================================================
# 2. BÚSQUEDA LÉXICA TF-IDF
# ============================================================

vector_pregunta_tfidf = (
    vectorizador_tfidf.transform(
        [pregunta_expandida]
    )
)


# Como los vectores TF-IDF de sklearn están normalizados,
# el producto punto equivale a similitud coseno.

scores_lexicos = (
    matriz_tfidf
    @ vector_pregunta_tfidf.T
).toarray().flatten()


# ============================================================
# NORMALIZACIÓN DE SCORES
# ============================================================
# Los scores semánticos y léxicos no necesariamente tienen
# exactamente la misma escala.
#
# Los llevamos al rango 0-1 antes de combinarlos.


def normalizar_scores(scores):

    minimo = np.min(scores)
    maximo = np.max(scores)

    if maximo == minimo:
        return np.zeros_like(scores)

    return (
        (scores - minimo)
        / (maximo - minimo)
    )


scores_semanticos_norm = normalizar_scores(
    scores_semanticos
)

scores_lexicos_norm = normalizar_scores(
    scores_lexicos
)


# ============================================================
# 3. COMBINAR LOS DOS MÉTODOS
# ============================================================

scores_finales = (

    PESO_SEMANTICO
    * scores_semanticos_norm

    +

    PESO_LEXICO
    * scores_lexicos_norm
)

# ============================================================
# DIAGNÓSTICO DE FRAGMENTOS ESPERADOS
# ============================================================

ids_esperados = [692, 1347, 2207, 2391]

ranking_completo = np.argsort(scores_finales)[::-1]

print("\n" + "=" * 80)
print("DIAGNÓSTICO DE DEFINICIONES")
print("=" * 80)

for id_buscado in ids_esperados:

    if id_buscado in ids:

        indice = ids.index(id_buscado)

        posicion = (
            np.where(ranking_completo == indice)[0][0]
            + 1
        )

        print(
            f"\nID {id_buscado}"
            f"\nPosición híbrida: {posicion}"
            f"\nScore final: {scores_finales[indice]:.4f}"
            f"\nSemántico: {scores_semanticos_norm[indice]:.4f}"
            f"\nLéxico: {scores_lexicos_norm[indice]:.4f}"
        )

    else:
        print(
            f"\nID {id_buscado}: no encontrado"
        )

# ============================================================
# TOP-K
# ============================================================

cantidad_resultados = min(
    TOP_K,
    len(scores_finales)
)


indices = np.argsort(
    scores_finales
)[::-1][:cantidad_resultados]


# ============================================================
# RESULTADOS
# ============================================================

print("\n" + "=" * 80)

print("RESULTADOS DE BÚSQUEDA HÍBRIDA")

print("=" * 80)


for posicion, indice in enumerate(
    indices,
    start=1
):

    score_semantico = float(
        scores_semanticos_norm[indice]
    )

    score_lexico = float(
        scores_lexicos_norm[indice]
    )

    score_final = float(
        scores_finales[indice]
    )


    print(
        f"\nRESULTADO {posicion}"
    )

    print(
        f"Score final: {score_final:.4f}"
    )

    print(
        f"Semántico: {score_semantico:.4f}"
    )

    print(
        f"Léxico: {score_lexico:.4f}"
    )

    print(
        f"ID fragmento: {ids[indice]}"
    )

    print(
        f"Fuente: {fuentes[indice]}"
    )

    print(
        f"Documento: {documentos[indice]}"
    )

    print(
        f"Página: {paginas[indice]}"
    )

    print("\nTexto:")

    print(
        textos[indice]
    )

    print("-" * 80)


# ============================================================
# CERRAR MYSQL
# ============================================================

cursor.close()

conexion.close()

print("\n✓ Búsqueda híbrida terminada")