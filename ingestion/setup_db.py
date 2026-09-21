import os
import shutil
import subprocess
import sys
from getpass import getpass


AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SCHEMA = os.path.join(RAIZ, "HUBDATOS.session.sql")

CARGADORES = [
    "cargar_endireh_mysql.py",
    "cargar_siesvim_mysql.py",
    "cargar_inmujeres_mysql.py",
    "cargar_twitter_mysql.py",
]

RUTAS_MYSQL = [
    r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    r"C:\xampp\mysql\bin\mysql.exe",
    r"C:\laragon\bin\mysql\mysql-8.0\bin\mysql.exe",
]


def encontrar_mysql():
    en_path = shutil.which("mysql")
    if en_path:
        return en_path
    for ruta in RUTAS_MYSQL:
        if os.path.exists(ruta):
            return ruta
    raise SystemExit(
        "No se encontró mysql.exe. Instala MySQL o agrégalo al PATH."
    )


def verificar_dependencias():
    faltantes = []

    for modulo, paquete in [
        ("mysql.connector", "mysql-connector-python"),
        ("pandas", "pandas"),
    ]:
        try:
            __import__(modulo)
        except ImportError:
            faltantes.append(paquete)

    if faltantes:
        raise SystemExit(
            "Faltan dependencias en el Python que estás usando: "
            + ", ".join(faltantes)
            + "\n\nInstálalas con:\n"
            + f'  "{sys.executable}" -m pip install -r requirements.txt'
        )


def main():
    verificar_dependencias()

    if not os.path.exists(SCHEMA):
        raise SystemExit(f"No se encontró el esquema: {SCHEMA}")

    usuario = os.environ.get("MYSQL_USER", "root")
    host = os.environ.get("MYSQL_HOST", "localhost")
    puerto = os.environ.get("MYSQL_PORT", "3306")

    print("=== Instalación de la base de datos HUBDATOS ===")
    print("Esto RECREA la base desde cero (DROP + CREATE) y carga los CSV.")
    print(f"Esquema: {SCHEMA}\n")

    password = getpass(f"Contraseña MySQL ({usuario}@{host}): ")

    env = {
        **os.environ,
        "MYSQL_PWD": password,
        "MYSQL_PASSWORD": password,
        "MYSQL_USER": usuario,
        "MYSQL_HOST": host,
        "MYSQL_PORT": puerto,
    }

    mysql = encontrar_mysql()

    print("\n[1/5] Creando base y tablas ...")
    with open(SCHEMA, "r", encoding="utf-8") as archivo:
        resultado = subprocess.run(
            [
                mysql,
                "-u", usuario,
                "-h", host,
                "-P", puerto,
                "--default-character-set=utf8mb4",
            ],
            stdin=archivo,
            env=env,
            capture_output=True,
            text=True,
        )

    if resultado.returncode != 0:
        print(resultado.stdout)
        print(resultado.stderr)
        raise SystemExit(
            "\nFalló la creación del esquema. Verifica la contraseña y que MySQL esté corriendo."
        )

    print("      OK: HUBDATOS creada.")

    for indice, script in enumerate(CARGADORES, start=2):
        print(f"\n[{indice}/5] Cargando {script} ...")
        resultado = subprocess.run(
            [sys.executable, script],
            cwd=AQUI,
            env=env,
            text=True,
        )
        if resultado.returncode != 0:
            raise SystemExit(f"\nFalló {script}. Revisa el error de arriba.")

    print("\n=== Listo: base HUBDATOS creada y cargada. ===")
    print("Ahora puedes arrancar la API con uvicorn (ver instrucciones).")


if __name__ == "__main__":
    main()
