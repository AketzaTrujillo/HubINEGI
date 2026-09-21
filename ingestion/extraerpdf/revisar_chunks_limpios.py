from pathlib import Path
import json
import re
import random
from statistics import mean, median


# ============================================================
# 1. RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_ORIGINAL = (
    BASE_DIR
    / "data"
    / "processed"
    / "pdfs_chunks"
)

CARPETA_LIMPIA = (
    BASE_DIR
    / "data"
    / "processed"
    / "pdfs_chunks_limpios"
)


# Para que las muestras aleatorias sean reproducibles
random.seed(42)


# ============================================================
# 2. FUNCIONES DE EVALUACIÓN
# ============================================================

def tiene_caracteres_control(texto):
    """
    Detecta caracteres de control no deseados.
    """

    patron = r"[\x00-\x08\x0b\x0c\x0e-\x1f]"

    return bool(
        re.search(patron, texto)
    )


def empieza_raro(texto):
    """
    Marca como sospechoso un chunk que comienza con
    minúscula o determinados signos de puntuación.

    IMPORTANTE:
    Esto es solamente un indicador.
    No significa automáticamente que el chunk sea incorrecto.
    """

    texto = texto.strip()

    if not texto:
        return True

    primer_caracter = texto[0]

    return (
        primer_caracter.islower()
        or primer_caracter in ",.;:)"
    )


def normalizar_para_duplicado(texto):
    """
    Normaliza un texto para detectar duplicados exactos.
    """

    texto = texto.lower()

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# 3. PATRONES DE RUIDO QUE DEBERÍAN HABER DESAPARECIDO
# ============================================================

PATRONES_REVISION = {

    "Cámara de Diputados":
        r"CÁMARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNIÓN",

    "Secretaría General":
        r"Secretaría General",

    "Secretaría de Servicios Parlamentarios":
        r"Secretaría de Servicios Parlamentarios",

    "Última Reforma DOF":
        r"Última Reforma DOF\s+\d{1,2}-\d{1,2}-\d{4}",

    "Número de página de la Ley":
        r"\b\d{1,2}\s+de\s+88\b",
}


# ============================================================
# 4. PATRONES IMPORTANTES QUE QUEREMOS CONSERVAR
# ============================================================

PATRONES_LEGALES = {

    "Artículo":
        r"\bArtículo\b",

    "Capítulo":
        r"\bCapítulo\b",

    "Fracción":
        r"\bFracción\b",

    "Orden de protección":
        r"\bórdenes?\s+de\s+protección\b",
}


# ============================================================
# 5. FUNCIÓN PARA EVALUAR UN DOCUMENTO
# ============================================================

def evaluar_chunks(chunks):

    longitudes = []

    chunks_cortos = []
    chunks_largos = []
    caracteres_raros = []
    comienzos_sospechosos = []
    duplicados = []

    textos_vistos = set()


    for chunk in chunks:

        texto = chunk["texto"].strip()

        longitud = len(texto)

        longitudes.append(longitud)


        # ----------------------------------------------------
        # Chunks cortos
        # ----------------------------------------------------

        if longitud < 150:
            chunks_cortos.append(chunk)


        # ----------------------------------------------------
        # Chunks demasiado largos
        # ----------------------------------------------------

        if longitud > 1500:
            chunks_largos.append(chunk)


        # ----------------------------------------------------
        # Caracteres de control
        # ----------------------------------------------------

        if tiene_caracteres_control(texto):
            caracteres_raros.append(chunk)


        # ----------------------------------------------------
        # Comienzos sospechosos
        # ----------------------------------------------------

        if empieza_raro(texto):
            comienzos_sospechosos.append(chunk)


        # ----------------------------------------------------
        # Duplicados
        # ----------------------------------------------------

        normalizado = normalizar_para_duplicado(
            texto
        )

        if normalizado in textos_vistos:

            duplicados.append(chunk)

        else:

            textos_vistos.add(normalizado)


    return {

        "total": len(chunks),

        "minima": min(longitudes)
        if longitudes else 0,

        "maxima": max(longitudes)
        if longitudes else 0,

        "promedio": mean(longitudes)
        if longitudes else 0,

        "mediana": median(longitudes)
        if longitudes else 0,

        "cortos": len(chunks_cortos),

        "largos": len(chunks_largos),

        "control": len(caracteres_raros),

        "duplicados": len(duplicados),

        "sospechosos": len(comienzos_sospechosos),
    }


# ============================================================
# 6. CARGAR DOCUMENTOS LIMPIOS
# ============================================================

archivos_limpios = sorted(
    CARPETA_LIMPIA.glob("*.json")
)


print("=" * 75)
print("SEGUNDA EVALUACIÓN DE CALIDAD DE CHUNKS")
print("=" * 75)

print(
    f"\nDocumentos encontrados en corpus limpio: "
    f"{len(archivos_limpios)}"
)


# ============================================================
# 7. VERIFICAR 911_SESPC
# ============================================================

ruta_911 = (
    CARPETA_LIMPIA
    / "911_SESPC.json"
)


print("\n" + "=" * 75)
print("VERIFICACIÓN DE DOCUMENTOS EXCLUIDOS")
print("=" * 75)


if ruta_911.exists():

    print(
        "⚠ 911_SESPC todavía existe "
        "en pdfs_chunks_limpios."
    )

else:

    print(
        "✓ 911_SESPC no está presente "
        "en el corpus limpio."
    )


# ============================================================
# 8. EVALUACIÓN GENERAL
# ============================================================

total_chunks = 0

total_cortos = 0
total_largos = 0
total_control = 0
total_duplicados = 0
total_sospechosos = 0


for ruta_json in archivos_limpios:

    chunks = json.loads(
        ruta_json.read_text(
            encoding="utf-8"
        )
    )

    resultado = evaluar_chunks(chunks)

    total_chunks += resultado["total"]

    total_cortos += resultado["cortos"]

    total_largos += resultado["largos"]

    total_control += resultado["control"]

    total_duplicados += resultado["duplicados"]

    total_sospechosos += resultado["sospechosos"]


    print("\n" + "-" * 75)

    print(
        f"DOCUMENTO: {ruta_json.stem}"
    )

    print("-" * 75)

    print(
        f"Chunks: {resultado['total']}"
    )

    print("\nLONGITUD")

    print(
        f"  Mínima:   {resultado['minima']}"
    )

    print(
        f"  Máxima:   {resultado['maxima']}"
    )

    print(
        f"  Promedio: "
        f"{resultado['promedio']:.1f}"
    )

    print(
        f"  Mediana:  "
        f"{resultado['mediana']:.1f}"
    )


    print("\nPOSIBLES PROBLEMAS")

    print(
        f"  Menores de 150 caracteres: "
        f"{resultado['cortos']}"
    )

    print(
        f"  Mayores de 1500 caracteres: "
        f"{resultado['largos']}"
    )

    print(
        f"  Caracteres de control: "
        f"{resultado['control']}"
    )

    print(
        f"  Duplicados exactos: "
        f"{resultado['duplicados']}"
    )

    print(
        f"  Comienzos sospechosos: "
        f"{resultado['sospechosos']}"
    )


# ============================================================
# 9. COMPROBAR RUIDO RESTANTE
# ============================================================

print("\n" + "=" * 75)
print("COMPROBACIÓN DE RUIDO EDITORIAL")
print("=" * 75)


conteo_ruido = {
    nombre: 0
    for nombre in PATRONES_REVISION
}


for ruta_json in archivos_limpios:

    chunks = json.loads(
        ruta_json.read_text(
            encoding="utf-8"
        )
    )

    for chunk in chunks:

        texto = chunk["texto"]

        for nombre, patron in PATRONES_REVISION.items():

            if re.search(
                patron,
                texto,
                flags=re.IGNORECASE
            ):

                conteo_ruido[nombre] += 1


for nombre, cantidad in conteo_ruido.items():

    print(
    f"{nombre}: "
    f"{cantidad} coincidencias para revisión"
)


# ============================================================
# 10. COMPROBAR CONTENIDO JURÍDICO CONSERVADO
# ============================================================

print("\n" + "=" * 75)
print("VERIFICACIÓN DE CONTENIDO JURÍDICO")
print("=" * 75)


ruta_ley = (
    CARPETA_LIMPIA
    / (
        "LEY GENERAL DE ACCESO DE LAS MUJERES "
        "A UNA VIDA LIBRE DE VIOLENCIA.json"
    )
)


if ruta_ley.exists():

    chunks_ley = json.loads(
        ruta_ley.read_text(
            encoding="utf-8"
        )
    )

    texto_ley = "\n".join(
        chunk["texto"]
        for chunk in chunks_ley
    )


    for nombre, patron in PATRONES_LEGALES.items():

        coincidencias = re.findall(
            patron,
            texto_ley,
            flags=re.IGNORECASE
        )

        cantidad = len(coincidencias)

        simbolo = "✓" if cantidad > 0 else "⚠"

        print(
            f"{simbolo} {nombre}: "
            f"{cantidad} coincidencias"
        )

else:

    print(
        "⚠ No se encontró el archivo de la Ley."
    )


# ============================================================
# 11. COMPARACIÓN ANTES VS DESPUÉS PARA LA LEY
# ============================================================

print("\n" + "=" * 75)
print("MUESTRAS ANTES VS DESPUÉS - LEY GENERAL")
print("=" * 75)


nombre_ley = (
    "LEY GENERAL DE ACCESO DE LAS MUJERES "
    "A UNA VIDA LIBRE DE VIOLENCIA.json"
)

ruta_ley_original = (
    CARPETA_ORIGINAL
    / nombre_ley
)

ruta_ley_limpia = (
    CARPETA_LIMPIA
    / nombre_ley
)


if (
    ruta_ley_original.exists()
    and ruta_ley_limpia.exists()
):

    originales = json.loads(
        ruta_ley_original.read_text(
            encoding="utf-8"
        )
    )

    limpios = json.loads(
        ruta_ley_limpia.read_text(
            encoding="utf-8"
        )
    )


    originales_por_id = {
        chunk["chunk_id"]: chunk
        for chunk in originales
    }

    limpios_por_id = {
        chunk["chunk_id"]: chunk
        for chunk in limpios
    }


    ids_modificados = []


    for chunk_id, original in originales_por_id.items():

        limpio = limpios_por_id.get(
            chunk_id
        )

        if limpio is None:
            continue

        if (
            original["texto"].strip()
            != limpio["texto"].strip()
        ):

            ids_modificados.append(
                chunk_id
            )


    print(
        f"\nChunks modificados encontrados: "
        f"{len(ids_modificados)}"
    )


    if ids_modificados:

        muestra_ids = random.sample(
            ids_modificados,
            min(3, len(ids_modificados))
        )


        for chunk_id in muestra_ids:

            original = originales_por_id[
                chunk_id
            ]

            limpio = limpios_por_id[
                chunk_id
            ]


            print("\n" + "-" * 75)

            print(
                f"CHUNK {chunk_id} "
                f"| página {original['pagina']}"
            )


            print("\nANTES:")

            print(
                original["texto"][:700]
            )


            print("\nDESPUÉS:")

            print(
                limpio["texto"][:700]
            )

else:

    print(
        "⚠ No fue posible realizar "
        "la comparación de la Ley."
    )


print("\n" + "=" * 75)
print("UBICACIÓN DEL RUIDO EDITORIAL RESTANTE")
print("=" * 75)

for ruta_json in archivos_limpios:

    chunks = json.loads(
        ruta_json.read_text(encoding="utf-8")
    )

    for chunk in chunks:

        texto = chunk["texto"]

        for nombre, patron in PATRONES_REVISION.items():

            if re.search(
                patron,
                texto,
                flags=re.IGNORECASE
            ):

                print(
                    f"\nPatrón: {nombre}"
                )

                print(
                    f"Documento: {chunk['documento']}"
                )

                print(
                    f"Página: {chunk['pagina']}"
                )

                print(
                    f"Chunk: {chunk['chunk_id']}"
                )

                print(
                    f"Texto: {texto[:500]}"
                )

# ============================================================
# 12. RESUMEN GLOBAL
# ============================================================

print("\n" + "=" * 75)
print("RESUMEN GLOBAL - PRUEBA 2")
print("=" * 75)


print(
    f"Documentos evaluados: "
    f"{len(archivos_limpios)}"
)

print(
    f"Chunks evaluados: "
    f"{total_chunks}"
)

print(
    f"Chunks menores de 150 caracteres: "
    f"{total_cortos}"
)

print(
    f"Chunks mayores de 1500 caracteres: "
    f"{total_largos}"
)

print(
    f"Chunks con caracteres de control: "
    f"{total_control}"
)

print(
    f"Duplicados exactos: "
    f"{total_duplicados}"
)

print(
    f"Comienzos sospechosos: "
    f"{total_sospechosos}"
)


print("\nEvaluación terminada.")