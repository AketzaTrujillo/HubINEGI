import re
import unicodedata


def normalizar(texto):
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def coincide_regex(texto, patrones):
    return any(re.search(p, texto) for p in patrones)


def contiene(texto, palabras):
    return any(p in texto for p in palabras)


def clasificar_tipo(texto):
    texto = normalizar(texto)

    # 1. Estadística / informes / datos
    patrones_estadistica = [
        r"\d+\s*%",
        r"\d+\s+de\s+cada\s+\d+",
        r"\d+\s*(mujeres|ninas|casos|denuncias|llamadas|victimas|carpetas|reportes)",
        r"(afecta al|afecta a)\s+\d+",
        r"(segun|de acuerdo con|con base en)\s+(inegi|endireh|onu|cidh|sesnsp|conavim)",
        r"(inegi|endireh|sesnsp|conavim|onu|cidh|feminismo de datos)",
        r"(cifras|datos|estadisticas|indicadores|reporte|informe|encuesta|indice|diagnostico)",
        r"(aumento|disminuyo|incremento|redujo|crecio|subio|bajo)",
        r"(la primera|la segunda|la tercera)\s+violencia",
        r"(mayor|menor)\s+violencia\s+contra\s+las\s+mujeres",
        r"(llamadas de emergencia|carpetas de investigacion)",
        r"(la violencia psicologica|la violencia sexual|la violencia economica)",
        r"(80 de las mujeres|70 de las mujeres|60 de las mujeres)",
        r"(en mexico el)",
        r"(violencia contra las mujeres)",
        r"(erradicacion de la violencia)"
    ]

    if coincide_regex(texto, patrones_estadistica):
        return "estadistica"

    # 2. Noticia / hecho reportado
    palabras_noticia = [
        "detienen", "detuvo", "capturan", "capturaron",
        "vinculan a proceso", "sentencian", "fiscalia", "fgj",
        "policia", "investigan", "denuncian ante", "reportan",
        "informo", "presunto", "presunta", "acusado", "agresor",
        "fue detenido", "fue detenida", "caso de violencia"
    ]

    if contiene(texto, palabras_noticia):
        return "noticia"

    # 3. Institucional / programas / talleres / campañas públicas
    palabras_institucional = [
        "secretaria", "gobierno", "ayuntamiento", "municipio", "dif",
        "congreso", "instituto", "comision", "derechos humanos",
        "campana", "programa", "capacitacion", "taller", "foro",
        "jornada", "iniciativa", "servicios de asistencia",
        "atencion a mujeres", "linea de ayuda", "prevencion",
        "sensibilizacion", "ordenes de proteccion", "dimos inicio",
        "unam", "icj", "teleton", "revista", "nexos", "prodecon",
        "onu", "ejecentral",
    ]

    if contiene(texto, palabras_institucional):
        return "institucional"

    # 4. Denuncia / testimonio personal
    patrones_denuncia = [
        r"\byo\b.*(sufri|vivi|denuncie|padeci)",
        r"(mi esposo|mi pareja|mi novio|mi ex|mi agresor)",
        r"(me golpeo|me pego|me acoso|me violento|me amenazo)",
        r"(nadie me ayudo|no me creyeron|nadie hizo nada)"
    ]

    if coincide_regex(texto, patrones_denuncia):
        return "denuncia"

    # 5. Propaganda / promoción política o gubernamental
    palabras_propaganda = [
        "seguimos trabajando", "nuestro compromiso", "transformando",
        "acciones del gobierno", "inauguramos", "entregamos",
        "vive tu comunidad", "logros", "avances de gobierno",
        "gracias al trabajo", "por instrucciones de"
    ]

    if contiene(texto, palabras_propaganda):
        return "propaganda"

    # 6. Opinión / activismo / divulgación
    palabras_opinion = [

        # Opinión
        "no hacen nada",
        "que verguenza",
        "es indignante",
        "basta de violencia",
        "exigimos justicia",
        "lamentable",

        # Divulgación / concientización
        "este cuerpo es mio",
        "violencia politica contra las mujeres",
        "por razones de genero",
        "sus consecuencias",
        "violencia contra las mujeres",
        "erradicacion de la violencia",
        "la violencia psicologica",
        "la violencia sexual",
        "la violencia economica",
        "en mexico la violencia",
    ]

    if contiene(texto, palabras_opinion):
        return "opinion"

    return "otro"