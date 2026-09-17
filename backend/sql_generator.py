from ollama_service import preguntar_ollama
from esquema_db import ESQUEMA_DB
from diccionario_semantico import (
    DICCIONARIO_SEMANTICO
)
from examples_nl_sql import EJEMPLOS_NL_SQL
from reglas_sql import REGLAS_SQL


def limpiar_sql(respuesta):
    respuesta = respuesta.strip()

    respuesta = respuesta.replace("```sql", "")
    respuesta = respuesta.replace("```SQL", "")
    respuesta = respuesta.replace("```", "")

    if (
        "NO_SE_PUEDE_CONSULTAR"
        in respuesta.upper()
    ):
        return "NO_SE_PUEDE_CONSULTAR"

    inicio = respuesta.upper().find("SELECT")

    if inicio == -1:
        return respuesta.strip()

    respuesta = respuesta[inicio:]

    fin = respuesta.find(";")

    if fin != -1:
        respuesta = respuesta[:fin + 1]

    return respuesta.strip()


def generar_sql(
    pregunta,
    contexto=None
):

    contexto_texto = ""

    if (
        contexto
        and contexto.get("pregunta")
    ):

        contexto_texto = f"""
========================================
CONTEXTO DE LA CONSULTA ANTERIOR
========================================

Pregunta anterior:
{contexto.get("pregunta")}

SQL anterior:
{contexto.get("sql")}

Resultados anteriores:
{contexto.get("resultados")}

Respuesta anterior:
{contexto.get("respuesta")}

REGLAS DEL CONTEXTO:

1. Si la pregunta actual usa expresiones como:
   "ese año"
   "ese indicador"
   "esa entidad"
   "la misma fuente"
   conserva esos datos de la consulta anterior.

2. Si el usuario introduce una nueva entidad,
   cambia únicamente la entidad y conserva
   los demás filtros que no haya modificado.

3. Si la pregunta anterior utilizaba:
   valor más bajo
   conserva ORDER BY valor ASC LIMIT 1,
   salvo que el usuario cambie la operación.

4. Si la pregunta anterior utilizaba:
   valor más alto
   conserva ORDER BY valor DESC LIMIT 1,
   salvo que el usuario cambie la operación.

5. No inventes información.
"""

    prompt = f"""
Eres el módulo NL-to-SQL del sistema MHub.

Tu única función es convertir preguntas
en español en consultas SQL válidas para MySQL.


========================================
ESQUEMA
========================================

{ESQUEMA_DB}


========================================
DICCIONARIO SEMÁNTICO
========================================

{DICCIONARIO_SEMANTICO}


========================================
REGLAS SQL
========================================

{REGLAS_SQL}


========================================
EJEMPLOS CORRECTOS
========================================

{EJEMPLOS_NL_SQL}


{contexto_texto}


========================================
PREGUNTA ACTUAL
========================================

{pregunta}


Devuelve exclusivamente UNA consulta SQL.

No escribas explicaciones.
No escribas alternativas.
No utilices Markdown.

La respuesta debe comenzar con SELECT
y terminar con punto y coma.

Si no puede responderse con la base de datos:

NO_SE_PUEDE_CONSULTAR
"""

    respuesta = preguntar_ollama(prompt)

    return limpiar_sql(respuesta)


def validar_sql(sql):

    sql_limpio = sql.strip().lower()

    if sql_limpio == "no_se_puede_consultar":
        return False

    if not sql_limpio.startswith("select"):
        return False

    palabras_prohibidas = [
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "truncate",
        "create",
        "replace"
    ]

    for palabra in palabras_prohibidas:
        if palabra in sql_limpio:
            return False

    contenido = sql_limpio.rstrip(";")

    if ";" in contenido:
        return False

    return True