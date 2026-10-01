"""Carga variables desde backend/.env una sola vez, al importar."""
import os

_CARGADO = False


def cargar_env():
    global _CARGADO
    if _CARGADO:
        return
    _CARGADO = True

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(ruta):
        return

    with open(ruta, "r", encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(
                clave.strip(), valor.strip().strip('"').strip("'")
            )


cargar_env()
