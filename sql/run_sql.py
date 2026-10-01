# Runner de archivos .sql para MHub
# Uso: python run_sql.py <archivo.sql> [--database DB] [--create-database DB]
import os
import sys
import argparse

import mysql.connector


def cargar_env():
    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "backend",
        ".env",
    )
    ruta = os.path.abspath(ruta)

    if not os.path.exists(ruta):
        return

    with open(ruta, "r", encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(
                clave.strip(),
                valor.strip().strip('"').strip("'"),
            )


def config(database=None):
    return {
        "host": os.environ.get("MYSQL_HOST", "localhost"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD"),
        "database": database,
    }


def partir_sentencias(texto):
    lineas = []
    for linea in texto.splitlines():
        if linea.strip().startswith("--"):
            continue
        lineas.append(linea)
    limpio = "\n".join(lineas)

    sentencias = []
    for parte in limpio.split(";"):
        parte = parte.strip()
        if parte:
            sentencias.append(parte)
    return sentencias


ERRORES_IDEMPOTENTES = {1060, 1050, 1061, 1826, 1007, 1008, 1062}


def ejecutar(archivo, database, create_database):
    cargar_env()

    if not os.environ.get("MYSQL_PASSWORD"):
        raise SystemExit("Falta MYSQL_PASSWORD (revisa backend/.env).")

    if create_database:
        conn = mysql.connector.connect(**config())
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS {create_database} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cur.close()
        conn.close()
        print(f"[db] {create_database} lista")

    with open(archivo, "r", encoding="utf-8") as f:
        sentencias = partir_sentencias(f.read())

    conn = mysql.connector.connect(**config(database))
    cur = conn.cursor()

    ok = 0
    for sentencia in sentencias:
        try:
            cur.execute(sentencia)
            if cur.with_rows:
                cur.fetchall()
            ok += 1
        except mysql.connector.Error as error:
            if error.errno in ERRORES_IDEMPOTENTES:
                print(f"[skip {error.errno}] {sentencia[:60]}...")
            else:
                print(f"[error {error.errno}] {sentencia[:80]}...")
                print(f"    {error.msg}")
                raise

    conn.commit()
    cur.close()
    conn.close()
    print(f"[ok] {archivo}: {ok}/{len(sentencias)} sentencias")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archivo")
    parser.add_argument("--database", default=None)
    parser.add_argument("--create-database", default=None)
    args = parser.parse_args()

    ejecutar(args.archivo, args.database, args.create_database)


if __name__ == "__main__":
    main()
