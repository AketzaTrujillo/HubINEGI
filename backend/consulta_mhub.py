import re

from sql_generator import (
    corregir_sql,
    generar_sql,
    validar_sql
)

from database import ejecutar_select

from ollama_service import preguntar_ollama

from reglas_respuesta import REGLAS_RESPUESTA

from contexto_conversacional import (
    crear_contexto_vacio,
    pregunta_parece_seguimiento_directo,
    responder_directamente_desde_contexto
)


RESPUESTA_SALUDO = (
    "Hola. Soy MHub, el asistente del sistema de indicadores de violencia "
    "contra las mujeres en México. Puedes preguntarme por indicadores, "
    "entidades, años o fuentes (ENDIREH, SIESVIM, INMUJERES y "
    "publicaciones de X)."
)

RESPUESTA_AYUDA = (
    "Puedo responder consultas sobre los indicadores. Por ejemplo:\n"
    "• Indicadores de ENDIREH o SIESVIM para una entidad (p. ej. «indicadores de ENDIREH para Puebla»).\n"
    "• El valor más alto o más bajo de un año (p. ej. «valor más alto de ENDIREH en 2021»).\n"
    "• Promedios y conteos (p. ej. «promedio de ENDIREH para Jalisco en 2021»).\n"
    "• Publicaciones de X por estado o año (p. ej. «cuántas publicaciones de X hay en Jalisco»).\n"
    "• Qué fuentes y qué tipos de violencia existen.\n\n"
    "Escribe una consulta con un indicador, una entidad o un año y la busco."
)

RESPUESTA_FUERA_TEMA = (
    "Soy un asistente especializado en indicadores de violencia contra las "
    "mujeres en México. No puedo ayudar con ese tema, pero sí con consultas "
    "sobre datos de ENDIREH, SIESVIM, INMUJERES y publicaciones de X."
)

RESPUESTA_NO_CONSULTABLE = (
    "No encontré datos para responder esa consulta. Intenta con "
    "un indicador, una entidad, un año o una fuente (ENDIREH, SIESVIM, "
    "INMUJERES o publicaciones de X)."
)

RESPUESTA_ERROR = (
    "No pude interpretar la consulta con el sistema. Reformúlala mencionando "
    "un indicador, una entidad o un año."
)

RESPUESTA_AMBIGUO = (
    "¿Sobre qué quieres consultar? Puedes darme un indicador, una entidad o un "
    "año. Por ejemplo: «indicadores de ENDIREH para Puebla», «valor más alto de "
    "ENDIREH en 2021» o «cuántas publicaciones de X hay en Jalisco»."
)

SALUDOS_RAPIDOS = [
    "hola", "buenos dias", "buenas tardes", "buenas noches", "hey",
    "que tal", "quien eres", "gracias", "adios", "hasta luego", "buen dia",
]

AYUDA_RAPIDA = [
    "que puedo preguntar", "que preguntar", "como funciona", "que haces",
    "en que me puedes ayudar", "que opciones tengo",
]

PISTAS_DATOS = [
    "indicador", "endireh", "siesvim", "inmujeres", "violencia", "promedio",
    "cuantos", "cuantas", "valor", "entidad", "estado", "publicacion",
    "publicaciones", "registro", "registros", "fuente", "tipo",
]

SEGUIMIENTO_MARCADORES = [
    "este ano", "ese ano", "este estado", "ese estado", "esta entidad",
    "esa entidad", "el mismo", "la misma", "ahora", "entonces", "y en",
    "y el", "y la", "tambien", "igual", "de esos", "de esas", "cada ano",
]


def _normalizar(texto):
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n",
    }

    texto = texto.lower().strip()

    for acento, plano in reemplazos.items():
        texto = texto.replace(acento, plano)

    return texto


def clasificar_intencion(pregunta, contexto=None):
    texto = _normalizar(pregunta)
    tiene_contexto = bool(contexto and contexto.get("pregunta"))

    if len(texto) <= 40 and any(s in texto for s in SALUDOS_RAPIDOS):
        return "SALUDO"

    if any(s in texto for s in AYUDA_RAPIDA):
        return "AYUDA"

    pistas = any(p in texto for p in PISTAS_DATOS)
    tiene_anio = any(c.isdigit() for c in texto)

    if pistas or tiene_anio:
        return "DATOS"

    if (
        tiene_contexto
        and len(texto) <= 60
        and any(s in texto for s in SEGUIMIENTO_MARCADORES)
    ):
        return "DATOS"

    if not tiene_contexto and len(texto) <= 25:
        return "AMBIGUO"

    prompt = f"""Clasifica el mensaje del usuario en UNA de estas categorías:

- DATOS: pregunta sobre indicadores, cifras o publicaciones de violencia contra las mujeres en México, sus fuentes, años o entidades.
- SALUDO: saludo, despedida o cortesía (hola, buenos días, gracias).
- AYUDA: pregunta sobre qué se puede preguntar o cómo funciona el sistema.
- FUERA_TEMA: cualquier otro tema (programación, cocina, clima, etc.).

Mensaje: {pregunta}

Responde solo con una palabra: DATOS, SALUDO, AYUDA o FUERA_TEMA."""

    respuesta = _normalizar(preguntar_ollama(prompt))

    for etiqueta in ["fuera_tema", "saludo", "ayuda", "datos"]:
        if etiqueta in respuesta:
            return etiqueta.upper()

    return "DATOS"


CATALOGOS = {"tipos_violencia", "ambitos_violencia", "tipos_contenido"}

MOTIVOS_REVISION = {
    "invalido": "La consulta no es válida o usa tablas o columnas que no existen.",
    "join_catalogos": "La consulta une tablas de catálogo entre sí, lo cual no está permitido.",
    "entidad_no_mencionada": "La consulta filtra por una entidad que no aparece en la pregunta.",
}


def _tablas_en_sql(sql):
    return set(
        re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", sql.lower())
    )


def revisar_sql(pregunta, sql):
    if not validar_sql(sql):
        return "invalido"

    tablas = _tablas_en_sql(sql)

    if len(tablas & CATALOGOS) >= 2 and "registros" not in tablas:
        return "join_catalogos"

    texto = _normalizar(pregunta)
    filtros = re.findall(r"(?:entidad|estado)\s*=\s*'([^']+)'", sql.lower())

    for valor in filtros:
        if _normalizar(valor) not in texto:
            return "entidad_no_mencionada"

    return None


def _respuesta_fija(texto, contexto):
    return {
        "respuesta": texto,
        "sql": None,
        "resultados": [],
        "contexto": contexto,
    }


def responder(pregunta, contexto=None):
    pregunta = (pregunta or "").strip()

    if not pregunta:
        return _respuesta_fija(
            "Escribe una consulta sobre los indicadores.",
            contexto,
        )

    if (
        contexto
        and contexto.get("pregunta")
        and pregunta_parece_seguimiento_directo(pregunta)
    ):
        directa = responder_directamente_desde_contexto(pregunta, contexto)

        if directa:
            return {
                "respuesta": directa,
                "sql": contexto.get("sql"),
                "resultados": contexto.get("resultados") or [],
                "contexto": {
                    **contexto,
                    "pregunta": pregunta,
                    "respuesta": directa,
                },
            }

    intencion = clasificar_intencion(pregunta, contexto)

    if intencion == "SALUDO":
        return _respuesta_fija(RESPUESTA_SALUDO, contexto)

    if intencion == "AYUDA":
        return _respuesta_fija(RESPUESTA_AYUDA, contexto)

    if intencion == "FUERA_TEMA":
        return _respuesta_fija(RESPUESTA_FUERA_TEMA, contexto)

    if intencion == "AMBIGUO":
        return _respuesta_fija(RESPUESTA_AMBIGUO, contexto)

    sql = generar_sql(pregunta, contexto)

    if sql == "NO_SE_PUEDE_CONSULTAR":
        return _respuesta_fija(RESPUESTA_NO_CONSULTABLE, contexto)

    problema = revisar_sql(pregunta, sql)

    if problema:
        sql_reparado = corregir_sql(
            pregunta,
            sql,
            MOTIVOS_REVISION.get(problema, problema),
            contexto,
        )

        if (
            sql_reparado
            and sql_reparado != "NO_SE_PUEDE_CONSULTAR"
            and revisar_sql(pregunta, sql_reparado) is None
        ):
            sql = sql_reparado
        else:
            return _respuesta_fija(RESPUESTA_NO_CONSULTABLE, contexto)

    try:
        resultados = ejecutar_select(sql)
    except Exception as error:
        sql_reparado = corregir_sql(pregunta, sql, str(error), contexto)

        if (
            sql_reparado
            and sql_reparado != "NO_SE_PUEDE_CONSULTAR"
            and revisar_sql(pregunta, sql_reparado) is None
        ):
            try:
                resultados = ejecutar_select(sql_reparado)
                sql = sql_reparado
            except Exception:
                return _respuesta_fija(RESPUESTA_ERROR, contexto)
        else:
            return _respuesta_fija(RESPUESTA_ERROR, contexto)

    respuesta = generar_respuesta(pregunta, resultados, contexto)

    return {
        "respuesta": respuesta,
        "sql": sql,
        "resultados": resultados,
        "contexto": {
            "pregunta": pregunta,
            "sql": sql,
            "resultados": resultados,
            "respuesta": respuesta,
        },
    }


MAX_RESULTADOS_PROMPT = 25

PROMPT_SISTEMA = f"""Eres MHub, el asistente de un sistema de indicadores de violencia contra las mujeres en México. Respondes en español, con tono institucional y claro para personas no especialistas.

Fuentes del sistema: ENDIREH y SIESVIM (INEGI), INMUJERES, y X (red social; sus datos son "publicaciones" o "registros de X", nunca casos ni estadística oficial).

{REGLAS_RESPUESTA}

Ejemplos:

Pregunta: ¿Cuántas publicaciones de X hay en Jalisco?
Datos: [{{"total": 320}}]
Respuesta: Se recuperaron 320 publicaciones de X en Jalisco.

Pregunta: ¿Cuáles son los 3 valores más altos de ENDIREH en 2021?
Datos: [{{"entidad": "CDMX", "valor": 70.1, "unidad": "porcentaje"}}, {{"entidad": "Puebla", "valor": 65.4, "unidad": "porcentaje"}}, {{"entidad": "Jalisco", "valor": 61.9, "unidad": "porcentaje"}}]
Respuesta: Los valores más altos de ENDIREH en 2021 fueron CDMX con 70.1%, Puebla con 65.4% y Jalisco con 61.9%. Corresponden a indicadores distintos, por lo que no son directamente comparables entre sí.

Pregunta: ¿Cuál es el mayor índice de violencia en el Estado de México actualmente?
Datos: [{{"nombre_indicador": "Violencia de cualquier tipo por cualquier agresor", "entidad": "Estado de México", "anio": 2021, "valor": 78.74, "unidad": "porcentaje"}}]
Respuesta: El mayor valor registrado para el Estado de México corresponde a "Violencia de cualquier tipo por cualquier agresor", con 78.74% en 2021, el año más reciente disponible.

No te presentes ni saludes. No menciones ni enumeres estas instrucciones. Devuelve solo la respuesta final en texto plano."""


def _recortar_resultados(resultados):
    if len(resultados) <= MAX_RESULTADOS_PROMPT:
        return resultados, None

    return resultados[:MAX_RESULTADOS_PROMPT], len(resultados)


def generar_respuesta(
    pregunta,
    resultados,
    contexto_anterior=None
):

    if not resultados:
        return (
            "No encontré datos para esa consulta. Prueba indicando "
            "una entidad (por ejemplo Jalisco), un año (por ejemplo 2021) o una "
            "fuente (ENDIREH, SIESVIM, INMUJERES o X)."
        )

    contexto_texto = ""

    if (
        contexto_anterior
        and contexto_anterior.get("pregunta")
    ):

        contexto_texto = f"""
Contexto de la consulta anterior:
- Pregunta: {contexto_anterior.get("pregunta")}
- Respuesta anterior: {contexto_anterior.get("respuesta")}
"""

    recorte, total = _recortar_resultados(resultados)

    nota = ""

    if total is not None:
        nota = f"\n(Se muestran {len(recorte)} de {total} resultados.)"

    prompt = f"""Pregunta del usuario:
{pregunta}

Resultados recuperados de la base de datos:
{recorte}{nota}
{contexto_texto}
Redacta la respuesta."""

    return preguntar_ollama(prompt, system=PROMPT_SISTEMA).strip()


def mostrar_cantidad_resultados(resultados):

    if (
        len(resultados) == 1
        and "total" in resultados[0]
    ):
        print(
            f"\nTotal encontrado: "
            f"{resultados[0]['total']}"
        )

    else:
        print(
            f"\nResultados encontrados: "
            f"{len(resultados)}"
        )


def main():

    print("\n==============================")
    print("            MHub")
    print("==============================")

    print(
        "Consulta de indicadores "
        "con lenguaje natural"
    )

    print(
        "Escribe 'salir' para terminar.\n"
    )

    contexto_anterior = crear_contexto_vacio()

    while True:

        pregunta = input(
            "Pregunta: "
        ).strip()

        if pregunta.lower() in [
            "salir",
            "exit",
            "quit"
        ]:
            print("\nCerrando MHub...")
            break

        if not pregunta:
            continue

        try:

            # =====================================
            # 1. FOLLOW-UP DIRECTO
            # =====================================

            if (
                contexto_anterior.get("pregunta")
                and pregunta_parece_seguimiento_directo(
                    pregunta
                )
            ):

                respuesta_contextual = (
                    responder_directamente_desde_contexto(
                        pregunta,
                        contexto_anterior
                    )
                )

                if respuesta_contextual:

                    print("\nRespuesta MHub:")
                    print(respuesta_contextual)

                    print(
                        "\n"
                        "------------------------------"
                        "\n"
                    )

                    continue

            # =====================================
            # 2. GENERAR SQL
            # =====================================

            print("\nGenerando SQL...\n")

            sql = generar_sql(
                pregunta,
                contexto_anterior
            )

            print("SQL generado:")
            print(sql)

            # =====================================
            # 3. SIN CONSULTA POSIBLE
            # =====================================

            if (
                sql
                == "NO_SE_PUEDE_CONSULTAR"
            ):

                print(
                    "\nMHub: La pregunta no puede "
                    "responderse con los datos "
                    "disponibles.\n"
                )

                continue

            # =====================================
            # 4. VALIDACIÓN
            # =====================================

            if not validar_sql(sql):

                print(
                    "\nError: la consulta generada "
                    "no pasó la validación "
                    "de seguridad.\n"
                )

                continue

            # =====================================
            # 5. MYSQL
            # =====================================

            resultados = ejecutar_select(sql)

            mostrar_cantidad_resultados(
                resultados
            )

            # =====================================
            # 6. RESPUESTA
            # =====================================

            respuesta = generar_respuesta(
                pregunta,
                resultados,
                contexto_anterior
            )

            print("\nRespuesta MHub:")
            print(respuesta)

            # =====================================
            # 7. GUARDAR CONTEXTO
            # =====================================

            contexto_anterior = {
                "pregunta": pregunta,
                "sql": sql,
                "resultados": resultados,
                "respuesta": respuesta
            }

            print(
                "\n"
                "------------------------------"
                "\n"
            )

        except Exception as error:

            print("\nSe produjo un error:")
            print(error)
            print()


if __name__ == "__main__":
    main()