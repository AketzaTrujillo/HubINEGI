import mysql.connector
from getpass import getpass


_password = None


def obtener_conexion():
    global _password

    if _password is None:
        _password = getpass("Contraseña MySQL: ")

    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password=_password,
        database="HUBDATOS"
    )

    return conexion


def ejecutar_select(sql):
    conexion = obtener_conexion()

    cursor = conexion.cursor(dictionary=True)

    cursor.execute(sql)

    resultados = cursor.fetchall()

    cursor.close()
    conexion.close()

    return resultados


def probar_conexion():
    conexion = obtener_conexion()

    cursor = conexion.cursor()

    cursor.execute("SHOW TABLES;")

    tablas = cursor.fetchall()

    print("\nConexión correcta con HUBDATOS")
    print("\nTablas encontradas:")

    for tabla in tablas:
        print("-", tabla[0])

    cursor.close()
    conexion.close()


if __name__ == "__main__":
    probar_conexion()