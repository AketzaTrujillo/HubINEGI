import re

def separar_tweets(texto):
    bloques = re.split(r"\n\s*\n", texto)
    return [b.strip() for b in bloques if len(b.strip()) > 50]


def extraer_campos(tweet):
    lineas = tweet.split("\n")
    
    usuario = None
    fecha = None
    
    for l in lineas:
        if l.startswith("@"):
            usuario = l.strip()
        elif "202" in l:
            fecha = l.strip()
    
    return usuario, fecha, tweet