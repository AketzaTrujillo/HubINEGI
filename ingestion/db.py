import os
import sys

import mysql.connector
from getpass import getpass


_config = None


def _obtener_config():
    global _config

    if _config is None:
        password = os.environ.get("MYSQL_PASSWORD")

        if password is None:
            if sys.stdin is not None and sys.stdin.isatty():
                password = getpass("Contraseña MySQL: ")
            else:
                raise RuntimeError(
                    "Falta la variable de entorno MYSQL_PASSWORD."
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
