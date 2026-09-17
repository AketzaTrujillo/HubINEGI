from sql_generator import (
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


def generar_respuesta(
    pregunta,
    resultados,
    contexto_anterior=None
):

    if not resultados:
        return (
            "No se encontraron datos para "
            "los criterios consultados."
        )

    contexto_texto = ""

    if (
        contexto_anterior
        and contexto_anterior.get("pregunta")
    ):

        contexto_texto = f"""
CONTEXTO ANTERIOR:

Pregunta anterior:
{contexto_anterior.get("pregunta")}

Resultados anteriores:
{contexto_anterior.get("resultados")}

Respuesta anterior:
{contexto_anterior.get("respuesta")}
"""

    prompt = f"""
Eres el asistente del sistema MHub.

MHub es un hub de datos relacionado con
indicadores de violencia contra las mujeres
en México.


PREGUNTA ACTUAL:

{pregunta}


RESULTADOS DE MYSQL:

{resultados}


{contexto_texto}


REGLAS:

{REGLAS_RESPUESTA}


Genera una respuesta clara,
breve y en español.
"""

    return preguntar_ollama(prompt)


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