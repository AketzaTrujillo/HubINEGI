def es_mujer(texto):
    palabras = ["mujer", "mujeres", "niña", "niñas"]
    return "si" if any(p in texto for p in palabras) else "incierto"
