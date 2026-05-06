import unicodedata


def normalizar(texto):
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


LUGARES = {
    # =====================
    # CDMX - Alcaldías
    # =====================
    "cdmx": ("CDMX", None, "estado"),
    "ciudad de mexico": ("CDMX", None, "estado"),
    "azcapotzalco": ("CDMX", "Azcapotzalco", "alcaldia"),
    "coyoacan": ("CDMX", "Coyoacán", "alcaldia"),
    "cuajimalpa": ("CDMX", "Cuajimalpa de Morelos", "alcaldia"),
    "gustavo a madero": ("CDMX", "Gustavo A. Madero", "alcaldia"),
    "gam": ("CDMX", "Gustavo A. Madero", "alcaldia"),
    "iztacalco": ("CDMX", "Iztacalco", "alcaldia"),
    "iztapalapa": ("CDMX", "Iztapalapa", "alcaldia"),
    "magdalena contreras": ("CDMX", "La Magdalena Contreras", "alcaldia"),
    "milpa alta": ("CDMX", "Milpa Alta", "alcaldia"),
    "alvaro obregon": ("CDMX", "Álvaro Obregón", "alcaldia"),
    "tlahuac": ("CDMX", "Tláhuac", "alcaldia"),
    "tlalpan": ("CDMX", "Tlalpan", "alcaldia"),
    "xochimilco": ("CDMX", "Xochimilco", "alcaldia"),
    "benito juarez": ("CDMX", "Benito Juárez", "alcaldia"),
    "cuauhtemoc": ("CDMX", "Cuauhtémoc", "alcaldia"),
    "miguel hidalgo": ("CDMX", "Miguel Hidalgo", "alcaldia"),
    "venustiano carranza": ("CDMX", "Venustiano Carranza", "alcaldia"),

    # =====================
    # Estado de México
    # =====================
    "edomex": ("Estado de México", None, "estado"),
    "estado de mexico": ("Estado de México", None, "estado"),
    "ecatepec": ("Estado de México", "Ecatepec de Morelos", "municipio"),
    "nezahualcoyotl": ("Estado de México", "Nezahualcóyotl", "municipio"),
    "neza": ("Estado de México", "Nezahualcóyotl", "municipio"),
    "tlalnepantla": ("Estado de México", "Tlalnepantla de Baz", "municipio"),
    "naucalpan": ("Estado de México", "Naucalpan de Juárez", "municipio"),
    "toluca": ("Estado de México", "Toluca", "capital"),
    "atenco": ("Estado de México", "San Salvador Atenco", "municipio"),
    "chalco": ("Estado de México", "Chalco", "municipio"),
    "chimalhuacan": ("Estado de México", "Chimalhuacán", "municipio"),
    "texcoco": ("Estado de México", "Texcoco", "municipio"),
    "atizapan": ("Estado de México", "Atizapán de Zaragoza", "municipio"),
    "coacalco": ("Estado de México", "Coacalco de Berriozábal", "municipio"),

    # =====================
    # Jalisco
    # =====================
    "jalisco": ("Jalisco", None, "estado"),
    "guadalajara": ("Jalisco", "Guadalajara", "capital"),
    "zapopan": ("Jalisco", "Zapopan", "municipio"),
    "tonala": ("Jalisco", "Tonalá", "municipio"),
    "tlaquepaque": ("Jalisco", "San Pedro Tlaquepaque", "municipio"),
    "puerto vallarta": ("Jalisco", "Puerto Vallarta", "municipio"),

    # =====================
    # Puebla / Tlaxcala
    # =====================
    "puebla": ("Puebla", "Puebla", "capital"),
    "tehuacan": ("Puebla", "Tehuacán", "municipio"),
    "cholula": ("Puebla", "San Pedro Cholula", "municipio"),
    "tlaxcala": ("Tlaxcala", "Tlaxcala", "capital"),

    # =====================
    # Nuevo León
    # =====================
    "nuevo leon": ("Nuevo León", None, "estado"),
    "monterrey": ("Nuevo León", "Monterrey", "capital"),
    "guadalupe nuevo leon": ("Nuevo León", "Guadalupe", "municipio"),
    "san nicolas": ("Nuevo León", "San Nicolás de los Garza", "municipio"),
    "san pedro garza garcia": ("Nuevo León", "San Pedro Garza García", "municipio"),
    "apodaca": ("Nuevo León", "Apodaca", "municipio"),
    "escobedo": ("Nuevo León", "General Escobedo", "municipio"),

    # =====================
    # Veracruz
    # =====================
    "veracruz": ("Veracruz", None, "estado"),
    "xalapa": ("Veracruz", "Xalapa", "capital"),
    "coatzacoalcos": ("Veracruz", "Coatzacoalcos", "municipio"),
    "cordoba": ("Veracruz", "Córdoba", "municipio"),
    "orizaba": ("Veracruz", "Orizaba", "municipio"),

    # =====================

    "colima": ("Colima", "Colima", "capital"),
    "guanajuato": ("Guanajuato", "Guanajuato", "capital"),
    "leon": ("Guanajuato", "León", "municipio"),
    "queretaro": ("Querétaro", "Querétaro", "capital"),
    "merida": ("Yucatán", "Mérida", "capital"),
    "yucatan": ("Yucatán", None, "estado"),
    "oaxaca": ("Oaxaca", "Oaxaca de Juárez", "capital"),
    "chiapas": ("Chiapas", None, "estado"),
    "tuxtla": ("Chiapas", "Tuxtla Gutiérrez", "capital"),
    "guerrero": ("Guerrero", None, "estado"),
    "chilpancingo": ("Guerrero", "Chilpancingo de los Bravo", "capital"),
    "acapulco": ("Guerrero", "Acapulco de Juárez", "municipio"),
    "sonora": ("Sonora", None, "estado"),
    "hermosillo": ("Sonora", "Hermosillo", "capital"),
    "baja california": ("Baja California", None, "estado"),
    "mexicali": ("Baja California", "Mexicali", "capital"),
    "tijuana": ("Baja California", "Tijuana", "municipio"),
    "tamaulipas": ("Tamaulipas", None, "estado"),
    "ciudad victoria": ("Tamaulipas", "Ciudad Victoria", "capital"),
    "reynosa": ("Tamaulipas", "Reynosa", "municipio"),
    "matamoros": ("Tamaulipas", "Matamoros", "municipio"),
}


def detectar_ubicacion(texto, usuario=None):
    texto_total = normalizar(f"{texto} {usuario}")

    # Buscar primero lugares más específicos
    lugares_ordenados = sorted(LUGARES.keys(), key=len, reverse=True)

    for lugar in lugares_ordenados:
        if lugar in texto_total:
            estado, municipio, nivel = LUGARES[lugar]

            return {
                "lugar_detectado": lugar,
                "municipio_alcaldia": municipio,
                "estado": estado,
                "nivel_ubicacion": nivel
            }

    return {
        "lugar_detectado": None,
        "municipio_alcaldia": None,
        "estado": "Nacional",
        "nivel_ubicacion": "no_detectado"
    }
    