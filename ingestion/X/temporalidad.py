import re

def detectar_anio_mencionado(texto):
    anios = re.findall(r"\b(2021|2022|2023|2024|2025|2026)\b", texto)

    if anios:
        return anios[0]

    return None
