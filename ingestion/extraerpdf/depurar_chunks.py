from pathlib import Path
import json
import re


# ============================================================
# 1. RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_ENTRADA = (
    BASE_DIR
    / "data"
    / "processed"
    / "pdfs_chunks"
)

CARPETA_SALIDA = (
    BASE_DIR
    / "data"
    / "processed"
    / "pdfs_chunks_limpios"
)

CARPETA_SALIDA.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 2. DOCUMENTOS EXCLUIDOS DEL RAG TEXTUAL
# ============================================================

# 911_SESPC se conserva en los datos originales,
# pero no se utilizará por ahora para embeddings porque
# su contenido principal se encuentra en gráficas.

DOCUMENTOS_EXCLUIDOS = {
    "911_SESPC"
}


# ============================================================
# 3. ENCABEZADOS CONOCIDOS
# ============================================================

# IMPORTANTE:
# Solo agregamos elementos que sabemos que son encabezados
# editoriales repetitivos.
#
# NO eliminamos palabras como:
# Artículo, Ley, Capítulo, Fracción, Decreto, etc.

ENCABEZADOS_EXACTOS = {

    "CÁMARA DE DIPUTADOS DEL H. CONGRESO DE LA UNIÓN",

    "Secretaría General",

    "Secretaría de Servicios Parlamentarios",

    "DIARIO OFICIAL",

}


# ============================================================
# 4. FUNCIONES DE LIMPIEZA
# ============================================================

def limpiar_espacios(texto):
    """
    Normaliza espacios y saltos de línea sin modificar
    el contenido semántico.
    """

    texto = re.sub(
        r"[ \t]+",
        " ",
        texto
    )

    texto = re.sub(
        r"\n{3,}",
        "\n\n",
        texto
    )

    return texto.strip()


def eliminar_encabezados_exactos(texto):
    """
    Elimina únicamente líneas que coinciden exactamente
    con encabezados editoriales conocidos.
    """

    lineas = texto.split("\n")

    resultado = []

    for linea in lineas:

        linea_limpia = linea.strip()

        if linea_limpia in ENCABEZADOS_EXACTOS:
            continue

        resultado.append(linea)

    return "\n".join(resultado)


def limpiar_ley_general(texto):
    """
    Limpieza específica para la Ley General.

    Elimina elementos editoriales repetitivos, pero
    conserva artículos, fracciones, capítulos y el
    contenido jurídico.
    """

    # --------------------------------------------------------
    # Nombre repetitivo del documento
    # --------------------------------------------------------

    texto = re.sub(
        r"LEY GENERAL DE ACCESO DE LAS MUJERES "
        r"A UNA VIDA LIBRE DE VIOLENCIAS?",
        "",
        texto,
        flags=re.IGNORECASE
    )

    # --------------------------------------------------------
    # Última Reforma DOF + fecha
    #
    # Ejemplo:
    # Última Reforma DOF 15-01-2026
    # --------------------------------------------------------

    texto = re.sub(
        r"Última Reforma DOF\s+"
        r"\d{1,2}-\d{1,2}-\d{4}",
        "",
        texto,
        flags=re.IGNORECASE
    )

    # --------------------------------------------------------
    # Numeración editorial:
    #
    # 20 de 88
    # 31 de 88
    #
    # Se restringe específicamente a este documento.
    # --------------------------------------------------------

    texto = re.sub(
        r"\b\d{1,2}\s+de\s+88\b",
        "",
        texto
    )

    return texto


def depurar_texto(texto, documento):
    """
    Aplica la limpieza correspondiente a cada chunk.
    """

    # Limpieza general muy conservadora
    texto = eliminar_encabezados_exactos(texto)

    # --------------------------------------------------------
    # Reglas específicas por documento
    # --------------------------------------------------------

    if documento == (
        "LEY GENERAL DE ACCESO DE LAS MUJERES "
        "A UNA VIDA LIBRE DE VIOLENCIA"
    ):
        texto = limpiar_ley_general(texto)

    # Normalización final
    texto = limpiar_espacios(texto)

    return texto


# ============================================================
# 5. PROCESAMIENTO
# ============================================================

archivos = sorted(
    CARPETA_ENTRADA.glob("*.json")
)

print("=" * 70)
print("DEPURACIÓN DE CHUNKS")
print("=" * 70)

print(
    f"\nDocumentos encontrados: {len(archivos)}"
)


total_chunks_entrada = 0
total_chunks_salida = 0

total_caracteres_antes = 0
total_caracteres_despues = 0

documentos_procesados = 0
documentos_excluidos = 0


for ruta_json in archivos:

    nombre_documento = ruta_json.stem

    print("\n" + "-" * 70)
    print(f"DOCUMENTO: {nombre_documento}")
    print("-" * 70)


    # ========================================================
    # EXCLUSIÓN DE DOCUMENTOS
    # ========================================================

    if nombre_documento in DOCUMENTOS_EXCLUIDOS:

        documentos_excluidos += 1

        print(
            "EXCLUIDO DEL RAG TEXTUAL "
            "(contenido principalmente gráfico)"
        )

        continue


    # ========================================================
    # LEER CHUNKS
    # ========================================================

    chunks = json.loads(
        ruta_json.read_text(
            encoding="utf-8"
        )
    )

    documentos_procesados += 1

    chunks_limpios = []

    caracteres_antes_documento = 0
    caracteres_despues_documento = 0

    chunks_modificados = 0
    chunks_vacios = 0


    # ========================================================
    # DEPURAR CADA CHUNK
    # ========================================================

    for chunk in chunks:

        texto_original = chunk["texto"]

        texto_limpio = depurar_texto(
            texto_original,
            nombre_documento
        )


        # ----------------------------------------------------
        # Estadísticas
        # ----------------------------------------------------

        caracteres_antes_documento += len(
            texto_original
        )

        caracteres_despues_documento += len(
            texto_limpio
        )


        # ----------------------------------------------------
        # Saber si realmente cambió
        # ----------------------------------------------------

        if texto_original.strip() != texto_limpio.strip():
            chunks_modificados += 1


        # ----------------------------------------------------
        # Si después de limpiar no queda contenido
        # ----------------------------------------------------

        if not texto_limpio:

            chunks_vacios += 1
            continue


        # ----------------------------------------------------
        # Conservamos exactamente los metadatos originales
        # ----------------------------------------------------

        nuevo_chunk = {
            "documento": chunk["documento"],
            "pagina": chunk["pagina"],
            "chunk_id": chunk["chunk_id"],
            "texto": texto_limpio
        }

        chunks_limpios.append(
            nuevo_chunk
        )


    # ========================================================
    # GUARDAR RESULTADO
    # ========================================================

    ruta_salida = (
        CARPETA_SALIDA
        / ruta_json.name
    )

    ruta_salida.write_text(
        json.dumps(
            chunks_limpios,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


    # ========================================================
    # ESTADÍSTICAS DEL DOCUMENTO
    # ========================================================

    total_chunks_entrada += len(chunks)

    total_chunks_salida += len(
        chunks_limpios
    )

    total_caracteres_antes += (
        caracteres_antes_documento
    )

    total_caracteres_despues += (
        caracteres_despues_documento
    )


    caracteres_eliminados = (
        caracteres_antes_documento
        - caracteres_despues_documento
    )


    print(
        f"Chunks originales: {len(chunks)}"
    )

    print(
        f"Chunks finales: {len(chunks_limpios)}"
    )

    print(
        f"Chunks modificados: {chunks_modificados}"
    )

    print(
        f"Chunks eliminados por quedar vacíos: "
        f"{chunks_vacios}"
    )

    print(
        f"Caracteres eliminados: "
        f"{caracteres_eliminados}"
    )


# ============================================================
# 6. RESUMEN GENERAL
# ============================================================

print("\n" + "=" * 70)
print("RESUMEN DE DEPURACIÓN")
print("=" * 70)

print(
    f"Documentos procesados: "
    f"{documentos_procesados}"
)

print(
    f"Documentos excluidos: "
    f"{documentos_excluidos}"
)

print(
    f"Chunks de entrada: "
    f"{total_chunks_entrada}"
)

print(
    f"Chunks de salida: "
    f"{total_chunks_salida}"
)

print(
    f"Caracteres antes: "
    f"{total_caracteres_antes}"
)

print(
    f"Caracteres después: "
    f"{total_caracteres_despues}"
)

print(
    f"Caracteres eliminados: "
    f"{total_caracteres_antes - total_caracteres_despues}"
)

print(
    "\nResultados guardados en:"
)

print(
    CARPETA_SALIDA
)