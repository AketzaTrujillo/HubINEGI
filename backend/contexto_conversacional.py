from ollama_service import preguntar_ollama
from reglas_respuesta import REGLAS_RESPUESTA


ENTIDADES_MEXICO = [
    "aguascalientes",
    "baja california",
    "baja california sur",
    "campeche",
    "chiapas",
    "chihuahua",
    "ciudad de méxico",
    "ciudad de mexico",
    "coahuila",
    "colima",
    "durango",
    "estado de méxico",
    "estado de mexico",
    "guanajuato",
    "guerrero",
    "hidalgo",
    "jalisco",
    "michoacán",
    "michoacan",
    "morelos",
    "nayarit",
    "nuevo león",
    "nuevo leon",
    "oaxaca",
    "puebla",
    "querétaro",
    "queretaro",
    "quintana roo",
    "san luis potosí",
    "san luis potosi",
    "sinaloa",
    "sonora",
    "tabasco",
    "tamaulipas",
    "tlaxcala",
    "veracruz",
    "yucatán",
    "yucatan",
    "zacatecas"
]


def crear_contexto_vacio():
    return {
        "pregunta": None,
        "sql": None,
        "resultados": None,
        "respuesta": None
    }


def pregunta_requiere_nueva_consulta(pregunta):
    """
    Detecta si una pregunta de seguimiento necesita
    volver a consultar MySQL.
    """

    texto = pregunta.lower().strip()

    operaciones_nuevas = [
        "más alto",
        "mas alto",
        "más bajo",
        "mas bajo",
        "máximo",
        "maximo",
        "mínimo",
        "minimo",
        "promedio",
        "media",
        "cuántos",
        "cuantos",
        "cantidad",
        "total",
        "compara",
        "comparar",
        "comparado con",
        "diferencia",
        "qué cambia",
        "que cambia",
        "cambia con",
        "segundo más",
        "segundo mas",
        "top ",
        "los 5",
        "las 5",
        "existe",
        "hay ",
        "está ",
        "esta "
    ]

    for expresion in operaciones_nuevas:
        if expresion in texto:
            return True

    # Si menciona una entidad específica,
    # normalmente modifica el filtro.
    for entidad in ENTIDADES_MEXICO:
        if entidad in texto:
            return True

    return False


def pregunta_parece_seguimiento_directo(pregunta):
    """
    Detecta preguntas que pueden resolverse
    directamente con los resultados anteriores.
    """

    texto = pregunta.lower().strip()

    if pregunta_requiere_nueva_consulta(pregunta):
        return False

    expresiones = [
        "ese indicador",
        "esa entidad",
        "ese estado",
        "ese valor",
        "ese año",
        "esa fuente",

        "respecto a qué indicador",
        "respecto a que indicador",
        "con respecto a qué indicador",
        "con respecto a que indicador",

        "qué indicador fue",
        "que indicador fue",
        "cuál indicador",
        "cual indicador",

        "qué entidad fue",
        "que entidad fue",
        "qué estado fue",
        "que estado fue",

        "qué valor tenía",
        "que valor tenia",
        "cuál era el valor",
        "cual era el valor",

        "qué unidad",
        "que unidad",
        "cuál era la unidad",
        "cual era la unidad",

        "de qué fuente",
        "de que fuente",

        "en qué año",
        "en que año"
    ]

    for expresion in expresiones:
        if expresion in texto:
            return True

    return False


def responder_directamente_desde_contexto(
    pregunta,
    contexto
):
    """
    Responde primero con Python usando los campos
    disponibles en la consulta anterior.

    Si no puede, usa Ollama como respaldo.
    """

    if not contexto:
        return None

    resultados = contexto.get("resultados")

    if not resultados:
        return None

    texto = pregunta.lower().strip()

    primer_resultado = resultados[0]

    # -----------------------------------------
    # INDICADOR
    # -----------------------------------------

    if (
        "qué indicador" in texto
        or "que indicador" in texto
        or "cuál indicador" in texto
        or "cual indicador" in texto
        or "respecto a qué indicador" in texto
        or "respecto a que indicador" in texto
    ):
        indicador = primer_resultado.get(
            "nombre_indicador"
        )

        if indicador:
            return (
                "El valor mencionado corresponde al "
                f'indicador: "{indicador}".'
            )

    # -----------------------------------------
    # ENTIDAD
    # -----------------------------------------

    if (
        "qué entidad" in texto
        or "que entidad" in texto
        or "qué estado" in texto
        or "que estado" in texto
        or "dónde fue" in texto
        or "donde fue" in texto
    ):
        entidad = (
            primer_resultado.get("entidad")
            or primer_resultado.get("estado")
        )

        if entidad:
            return (
                f"La entidad correspondiente fue "
                f"{entidad}."
            )

    # -----------------------------------------
    # VALOR
    # -----------------------------------------

    if (
        "qué valor" in texto
        or "que valor" in texto
        or "cuánto fue" in texto
        or "cuanto fue" in texto
        or "cuál era el valor" in texto
        or "cual era el valor" in texto
    ):
        valor = primer_resultado.get("valor")

        if valor is not None:
            unidad = primer_resultado.get("unidad")

            if unidad:
                return (
                    f"El valor fue {valor} "
                    f"{unidad}."
                )

            return f"El valor fue {valor}."

    # -----------------------------------------
    # AÑO
    # -----------------------------------------

    if (
        "qué año" in texto
        or "que año" in texto
        or "en qué año" in texto
        or "en que año" in texto
    ):
        anio = primer_resultado.get("anio")

        if anio is not None:
            return (
                f"El año correspondiente fue {anio}."
            )

    # -----------------------------------------
    # UNIDAD
    # -----------------------------------------

    if (
        "qué unidad" in texto
        or "que unidad" in texto
        or "cuál era la unidad" in texto
        or "cual era la unidad" in texto
    ):
        unidad = primer_resultado.get("unidad")

        if unidad:
            return (
                f"La unidad correspondiente es "
                f"{unidad}."
            )

    # -----------------------------------------
    # OLLAMA COMO RESPALDO
    # -----------------------------------------

    prompt = f"""
Eres el asistente del sistema MHub.

PREGUNTA ANTERIOR:
{contexto.get("pregunta")}

SQL ANTERIOR:
{contexto.get("sql")}

RESULTADOS ANTERIORES:
{resultados}

RESPUESTA ANTERIOR:
{contexto.get("respuesta")}

PREGUNTA ACTUAL:
{pregunta}

REGLAS:
{REGLAS_RESPUESTA}

Debes decidir si la pregunta actual puede
responderse exclusivamente usando los resultados
anteriores.

Si la información está presente:
responde directamente.

Si realmente hace falta consultar nuevamente
la base de datos, responde exactamente:

NECESITA_NUEVA_CONSULTA
"""

    respuesta = preguntar_ollama(prompt).strip()

    respuesta_upper = respuesta.upper()

    frases_control = [
        "NECESITA_NUEVA_CONSULTA",
        "NECESITO REALIZAR UNA NUEVA CONSULTA",
        "NO NECESITO UNA NUEVA CONSULTA",
        "NUEVA CONSULTA A LA BASE"
    ]

    for frase in frases_control:
        if frase in respuesta_upper:
            return None

    return respuesta