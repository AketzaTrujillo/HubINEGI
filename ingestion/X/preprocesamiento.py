import re
import unicodedata


def limpiar_texto(texto):

    texto = str(texto).lower()

    # quitar acentos
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    # quitar urls
    texto = re.sub(r"http\S+", " ", texto)

    # quitar menciones
    texto = re.sub(r"@\w+", " ", texto)

    # quitar hashtags pero dejar palabra
    texto = re.sub(r"#", "", texto)

    # quitar "image", "show more", etc
    basura = [
        "image",
        "show more",
        "replying to",
        "square profile picture",
        "quote",
        "translate post"
    ]

    for b in basura:
        texto = texto.replace(b, " ")

    # quitar caracteres raros
    texto = re.sub(r"[^a-zA-Z0-9áéíóúñ\s]", " ", texto)

    # quitar espacios repetidos
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()