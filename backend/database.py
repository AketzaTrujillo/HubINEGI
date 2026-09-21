import os
import sys
import mysql.connector
from getpass import getpass


_config = None


def _cargar_env():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if not os.path.exists(ruta):
        return

    with open(ruta, "r", encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()

            if not linea or linea.startswith("#") or "=" not in linea:
                continue

            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env()


def _obtener_config():
    global _config

    if _config is None:
        password = os.environ.get("MYSQL_PASSWORD")

        if password is None:
            if sys.stdin is not None and sys.stdin.isatty():
                password = getpass("Contraseña MySQL: ")
            else:
                raise RuntimeError(
                    "Falta la variable de entorno MYSQL_PASSWORD. "
                    "Defínela antes de arrancar la API."
                )

        _config = {
            "host": os.environ.get("MYSQL_HOST", "localhost"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": password,
            "database": os.environ.get("MYSQL_DATABASE", "HUBDATOS"),
        }

    return _config


def obtener_conexion():
    return mysql.connector.connect(**_obtener_config())


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