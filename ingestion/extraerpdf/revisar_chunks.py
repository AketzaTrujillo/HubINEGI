from pathlib import Path
import json
import re
import random
from statistics import mean, median

BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_CHUNKS = (
    BASE_DIR
    / "data"
    / "processed"
    / "pdfs_chunks"
)

# Para que la muestra aleatoria sea reproducible
random.seed(42)


def tiene_caracteres_control(texto):
    patron = r"[\x00-\x08\x0b\x0c\x0e-\x1f]"
    return bool(re.search(patron, texto))


def empieza_raro(texto):
    """
    Detecta algunos casos sospechosos:
    - empieza con minúscula
    - empieza con signo de puntuación extraño

    OJO: empezar con minúscula no siempre es un error
    debido al solapamiento entre chunks.
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
    Normalización sencilla para detectar chunks
    exactamente duplicados ignorando espacios.
    """
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


archivos = list(CARPETA_CHUNKS.glob("*.json"))

print("=" * 70)
print("EVALUACIÓN DE CALIDAD DE CHUNKS")
print("=" * 70)

print(f"\nDocumentos encontrados: {len(archivos)}")

total_chunks_global = 0
total_problematicos_global = 0


for ruta_json in archivos:

    datos = json.loads(
        ruta_json.read_text(encoding="utf-8")
    )

    if not datos:
        print(f"\n⚠ {ruta_json.name}: archivo vacío")
        continue

    longitudes = [
        len(chunk["texto"])
        for chunk in datos
    ]

    chunks_cortos = []
    chunks_largos = []
    caracteres_raros = []
    comienzos_sospechosos = []

    textos_vistos = set()
    duplicados = []

    for chunk in datos:

        texto = chunk["texto"].strip()
        longitud = len(texto)

        # ------------------------------------
        # Longitud
        # ------------------------------------

        if longitud < 150:
            chunks_cortos.append(chunk)

        if longitud > 1500:
            chunks_largos.append(chunk)

        # ------------------------------------
        # Caracteres de control
        # ------------------------------------

        if tiene_caracteres_control(texto):
            caracteres_raros.append(chunk)

        # ------------------------------------
        # Comienzo sospechoso
        # ------------------------------------

        if empieza_raro(texto):
            comienzos_sospechosos.append(chunk)

        # ------------------------------------
        # Duplicados exactos
        # ------------------------------------

        normalizado = normalizar_para_duplicado(texto)

        if normalizado in textos_vistos:
            duplicados.append(chunk)
        else:
            textos_vistos.add(normalizado)

    # No sumamos las categorías porque un chunk
    # podría presentar más de un problema.
    ids_problematicos = set()

    for lista in [
        chunks_cortos,
        chunks_largos,
        caracteres_raros,
        duplicados
    ]:
        for chunk in lista:
            ids_problematicos.add(
                (
                    chunk["documento"],
                    chunk["chunk_id"]
                )
            )

    total = len(datos)
    problematicos = len(ids_problematicos)

    total_chunks_global += total
    total_problematicos_global += problematicos

    paginas = {
        chunk["pagina"]
        for chunk in datos
    }

    print("\n" + "-" * 70)
    print(f"DOCUMENTO: {ruta_json.stem}")
    print("-" * 70)

    print(f"Chunks: {total}")
    print(f"Páginas representadas: {len(paginas)}")

    print("\nLONGITUD")
    print(f"  Mínima:   {min(longitudes)}")
    print(f"  Máxima:   {max(longitudes)}")
    print(f"  Promedio: {mean(longitudes):.1f}")
    print(f"  Mediana:  {median(longitudes):.1f}")

    print("\nPOSIBLES PROBLEMAS")
    print(f"  Menores de 150 caracteres: {len(chunks_cortos)}")
    print(f"  Mayores de 1500 caracteres: {len(chunks_largos)}")
    print(f"  Caracteres de control: {len(caracteres_raros)}")
    print(f"  Duplicados exactos: {len(duplicados)}")

    print(
        "  Comienzos sospechosos: "
        f"{len(comienzos_sospechosos)}"
        " (solo indicador)"
    )

    porcentaje = problematicos / total * 100

    print(
        f"\nChunks con algún problema fuerte: "
        f"{problematicos}/{total} "
        f"({porcentaje:.1f}%)"
    )

    # ----------------------------------------
    # Muestra aleatoria
    # ----------------------------------------

    muestra = random.sample(
        datos,
        min(3, len(datos))
    )

    print("\nMUESTRA ALEATORIA:")

    for chunk in muestra:

        texto = chunk["texto"].replace("\n", " ")

        print(
            f"\n  Chunk {chunk['chunk_id']} "
            f"| página {chunk['pagina']}"
        )

        print(f"  {texto[:250]}...")


print("\n" + "=" * 70)
print("RESUMEN GLOBAL")
print("=" * 70)

print(f"Chunks analizados: {total_chunks_global}")

if total_chunks_global:

    porcentaje_global = (
        total_problematicos_global
        / total_chunks_global
        * 100
    )

    print(
        f"Chunks con algún problema fuerte: "
        f"{total_problematicos_global} "
        f"({porcentaje_global:.1f}%)"
    )