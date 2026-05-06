def calcular_confianza(tipo_contenido, texto):

    texto = str(texto).lower()

    confianza_base = {
        "estadistica": 0.90,
        "noticia": 0.85,
        "institucional": 0.80,
        "denuncia": 0.75,
        "opinion": 0.65,
        "propaganda": 0.60,
        "otro": 0.20
    }

    confianza = confianza_base.get(tipo_contenido, 0.20)

    # aumentar confianza si encuentra patrones fuertes
    patrones_fuertes = {
        "estadistica": [
            "inegi", "endireh", "%", "estadistica",
            "encuesta", "reporte", "informe"
        ],

        "noticia": [
            "detuvieron", "fiscalia", "investigan",
            "capturaron", "presunto"
        ],

        "institucional": [
            "secretaria", "gobierno", "campana",
            "programa", "taller"
        ],

        "denuncia": [
            "yo sufri", "me golpeo", "me acoso",
            "mi pareja"
        ]
    }

    if tipo_contenido in patrones_fuertes:
        for p in patrones_fuertes[tipo_contenido]:
            if p in texto:
                confianza += 0.05

    # límite máximo
    confianza = min(confianza, 0.99)

    return round(confianza, 2)