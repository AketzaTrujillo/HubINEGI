from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CARPETA = BASE_DIR / "data" / "processed" / "pdfs_texto"

archivos = sorted(CARPETA.glob("*.txt"))

print(f"\nArchivos encontrados: {len(archivos)}")

for archivo in archivos:

    print("\n" + "=" * 100)
    print(f"DOCUMENTO: {archivo.name}")
    print("=" * 100)

    with open(archivo, "r", encoding="utf-8") as f:
        texto = f.read()


    print(texto[:4000])

    print("\n")