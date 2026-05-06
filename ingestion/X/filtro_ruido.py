def detectar_basura(texto):
    texto = texto.lower().strip()

    # muy corto
    if len(texto) < 25:
        return "si", "texto_vacio_o_muy_corto"

    # spam
    palabras_basura = [
        "venta", "promo", "promoción", "descuento",
        "sígueme", "follow", "bitcoin", "casino",
        "apuesta", "onlyfans", "meme", "jajaja"
    ]

    if any(p in texto for p in palabras_basura):
        return "si", "spam_o_irrelevante"

    # multimedia sin contenido
    if texto.strip() in ["image", "quote", "video"]:
        return "si", "solo_multimedia"

    return "no", None