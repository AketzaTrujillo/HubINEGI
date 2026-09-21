from pathlib import Path
import pymupdf

# Ruta raíz del proyecto HubINEGI
BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_PDFS = BASE_DIR / "data" / "raw" / "pdfs"
CARPETA_SALIDA = BASE_DIR / "data" / "processed" / "pdfs_texto"

CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

for ruta_pdf in CARPETA_PDFS.glob("*.pdf"):
    print(f"\nProcesando: {ruta_pdf.name}")

    documento = pymupdf.open(ruta_pdf)

    total_paginas = len(documento)
    paginas_con_texto = 0
    texto_documento = []

    for numero_pagina, pagina in enumerate(documento, start=1):
        texto = pagina.get_text("text").strip()

        if texto:
            paginas_con_texto += 1

        texto_documento.append(
            f"\n--- PÁGINA {numero_pagina} ---\n{texto}"
        )

    porcentaje = (
        paginas_con_texto / total_paginas * 100
        if total_paginas > 0
        else 0
    )

    ruta_salida = CARPETA_SALIDA / f"{ruta_pdf.stem}.txt"

    ruta_salida.write_text(
        "\n".join(texto_documento),
        encoding="utf-8"
    )

    print(f"Páginas totales: {total_paginas}")
    print(f"Páginas con texto: {paginas_con_texto}")
    print(f"Cobertura de texto: {porcentaje:.1f}%")

    if porcentaje >= 90:
        print("Estado: OK")
    elif porcentaje >= 50:
        print("Estado: REVISAR")
    else:
        print("Estado: POSIBLE PDF ESCANEADO")

    documento.close()