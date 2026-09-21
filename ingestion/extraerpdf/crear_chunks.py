from pathlib import Path
import json
import re

BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_TXT = BASE_DIR / "data" / "processed" / "pdfs_texto"
CARPETA_SALIDA = BASE_DIR / "data" / "processed" / "pdfs_chunks"

CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

TAM_MAX = 1200
SOLAPAMIENTO = 150


def limpiar_texto(texto):
    texto = texto.replace("\r", "\n")

    # espacios repetidos
    texto = re.sub(r"[ \t]+", " ", texto)

    # demasiados saltos
    texto = re.sub(r"\n{3,}", "\n\n", texto)

    return texto.strip()



from pathlib import Path
import json
import re

# ---------------------------------------------------------
# RUTAS DEL PROYECTO
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_TXT = BASE_DIR / "data" / "processed" / "pdfs_texto"
CARPETA_SALIDA = BASE_DIR / "data" / "processed" / "pdfs_chunks"

CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# CONFIGURACIÓN DE CHUNKS
# ---------------------------------------------------------

TAM_MAX = 1400
SOLAPAMIENTO_PARRAFOS = 1
MIN_CHARS = 100


# ---------------------------------------------------------
# LIMPIEZA DEL TEXTO
# ---------------------------------------------------------

def limpiar_texto(texto):
    """
    Limpia caracteres extraños y espacios innecesarios
    provenientes de la extracción del PDF.
    """

    texto = texto.replace("\r", "\n")

    # Eliminar caracteres de control extraños
    texto = re.sub(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
        "",
        texto
    )

    # Espacios y tabulaciones repetidas
    texto = re.sub(r"[ \t]+", " ", texto)

    # Eliminar espacios antes de signos de puntuación
    texto = re.sub(
        r"\s+([.,;:!?])",
        r"\1",
        texto
    )

    # Evitar demasiados saltos de línea
    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    return texto.strip()


# ---------------------------------------------------------
# CREACIÓN DE CHUNKS
# ---------------------------------------------------------

def crear_chunks(
    texto,
    max_chars=TAM_MAX,
    overlap_parrafos=SOLAPAMIENTO_PARRAFOS
):
    """
    Divide el texto en fragmentos conservando párrafos
    completos y evitando cortar palabras a la mitad.

    Se conserva un párrafo del chunk anterior como
    contexto para el siguiente.
    """

    parrafos = [
        p.strip()
        for p in texto.split("\n")
        if p.strip()
    ]

    chunks = []

    actual = []
    longitud_actual = 0

    for parrafo in parrafos:

        longitud_parrafo = len(parrafo)

        # -------------------------------------------------
        # CASO 1:
        # El párrafo todavía cabe en el chunk actual
        # -------------------------------------------------

        if (
            longitud_actual
            + longitud_parrafo
            + 1
            <= max_chars
        ):
            actual.append(parrafo)

            longitud_actual += (
                longitud_parrafo + 1
            )

        # -------------------------------------------------
        # CASO 2:
        # El párrafo ya no cabe
        # -------------------------------------------------

        else:

            if actual:

                chunk = "\n".join(actual).strip()

                if chunk:
                    chunks.append(chunk)

                # Mantener párrafos completos
                # como solapamiento
                actual = actual[
                    -overlap_parrafos:
                ]

                longitud_actual = sum(
                    len(p) + 1
                    for p in actual
                )

            # -------------------------------------------------
            # Si un solo párrafo es extremadamente largo
            # -------------------------------------------------

            if longitud_parrafo > max_chars:

                inicio = 0

                while inicio < longitud_parrafo:

                    fin = inicio + max_chars

                    fragmento = parrafo[
                        inicio:fin
                    ].strip()

                    if fragmento:
                        chunks.append(
                            fragmento
                        )

                    inicio = fin

                actual = []
                longitud_actual = 0

            else:

                actual.append(parrafo)

                longitud_actual += (
                    longitud_parrafo + 1
                )

    # ---------------------------------------------------------
    # Guardar último chunk
    # ---------------------------------------------------------

    if actual:

        chunk = "\n".join(actual).strip()

        if chunk:
            chunks.append(chunk)

    return chunks


# ---------------------------------------------------------
# PROCESAMIENTO DE TODOS LOS TXT
# ---------------------------------------------------------

archivos_txt = list(
    CARPETA_TXT.glob("*.txt")
)

print(
    f"\nArchivos encontrados: "
    f"{len(archivos_txt)}"
)

total_chunks = 0


for ruta_txt in archivos_txt:

    print(
        f"\nProcesando: "
        f"{ruta_txt.name}"
    )

    contenido = ruta_txt.read_text(
        encoding="utf-8"
    )

    # -----------------------------------------------------
    # Separar utilizando los marcadores:
    #
    # --- PÁGINA 1 ---
    # --- PÁGINA 2 ---
    # etc.
    # -----------------------------------------------------

    paginas = re.split(
        r"--- PÁGINA (\d+) ---",
        contenido
    )

    resultados = []

    chunk_global = 1

    paginas_procesadas = 0

    chunks_descartados = 0

    # -----------------------------------------------------
    # La estructura después del split queda:
    #
    # [texto_inicial,
    #  numero_pagina,
    #  texto,
    #  numero_pagina,
    #  texto,
    #  ...]
    # -----------------------------------------------------

    for i in range(
        1,
        len(paginas),
        2
    ):

        numero_pagina = int(
            paginas[i]
        )

        texto_pagina = limpiar_texto(
            paginas[i + 1]
        )

        # Ignorar páginas vacías
        if not texto_pagina:
            continue

        paginas_procesadas += 1

        chunks = crear_chunks(
            texto_pagina
        )

        for chunk in chunks:

            chunk = chunk.strip()

            # ---------------------------------------------
            # Descartar chunks demasiado pequeños
            # ---------------------------------------------

            if len(chunk) < MIN_CHARS:

                chunks_descartados += 1

                continue

            resultados.append({
                "documento": ruta_txt.stem,
                "pagina": numero_pagina,
                "chunk_id": chunk_global,
                "texto": chunk
            })

            chunk_global += 1

    # -----------------------------------------------------
    # GUARDAR JSON
    # -----------------------------------------------------

    ruta_salida = (
        CARPETA_SALIDA
        / f"{ruta_txt.stem}.json"
    )

    ruta_salida.write_text(
        json.dumps(
            resultados,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    total_chunks += len(
        resultados
    )

    print(
        f"Páginas procesadas: "
        f"{paginas_procesadas}"
    )

    print(
        f"Chunks creados: "
        f"{len(resultados)}"
    )

    print(
        f"Chunks descartados "
        f"por ser muy pequeños: "
        f"{chunks_descartados}"
    )

    print(
        f"Guardado en: "
        f"{ruta_salida.name}"
    )


# ---------------------------------------------------------
# RESUMEN FINAL
# ---------------------------------------------------------

print(
    "\n=============================="
)

print(
    "PROCESAMIENTO TERMINADO"
)

print(
    "=============================="
)

print(
    f"Documentos procesados: "
    f"{len(archivos_txt)}"
)

print(
    f"Chunks totales creados: "
    f"{total_chunks}"
)

print(
    f"Carpeta de salida:\n"
    f"{CARPETA_SALIDA}"
)