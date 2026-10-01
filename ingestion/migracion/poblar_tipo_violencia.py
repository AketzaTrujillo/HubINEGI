# Puebla bridge_indicador_tipo_violencia por palabras clave (Fase 7).
# Uso: python poblar_tipo_violencia.py
import os
import re
import sys
import unicodedata

import mysql.connector

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))


def cargar_env():
    ruta = os.path.join(BASE, "backend", ".env")
    if not os.path.exists(ruta):
        return
    with open(ruta, "r", encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def conexion():
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD"),
        database=os.environ.get("MYSQL_DATABASE", "HUBDATOS"),
    )


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


# Palabras clave por tipo de violencia (claves normalizadas sin acento)
CLAVES = {
    "fisica": ["fisica"],
    "psicologica": ["psicologica", "emocional"],
    "sexual": ["sexual"],
    "economica": ["economica"],
    "patrimonial": ["patrimonial"],
    "discriminacion": ["discriminacion"],
}


def main():
    cargar_env()
    if not os.environ.get("MYSQL_PASSWORD"):
        raise SystemExit("Falta MYSQL_PASSWORD.")

    conn = conexion()
    cur = conn.cursor()

    cur.execute("SELECT id_tipo_violencia, nombre FROM tipos_violencia")
    tipos = {}
    for id_tv, nombre in cur.fetchall():
        tipos[normalizar(nombre)] = id_tv

    cur.execute("SELECT id_indicador, nombre FROM dim_indicador")
    indicadores = cur.fetchall()

    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    cur.execute("TRUNCATE TABLE bridge_indicador_tipo_violencia")
    cur.execute("TRUNCATE TABLE bridge_pub_tipo_violencia")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    filas = []
    sin_tipo = 0
    for id_indicador, nombre in indicadores:
        n = normalizar(nombre)
        encontrados = set()
        for tipo_norm, palabras in CLAVES.items():
            if any(p in n for p in palabras) and tipo_norm in tipos:
                encontrados.add(tipos[tipo_norm])
        if not encontrados:
            sin_tipo += 1
            continue
        for id_tv in encontrados:
            filas.append((id_indicador, id_tv))

    cur.executemany(
        "INSERT IGNORE INTO bridge_indicador_tipo_violencia VALUES (%s, %s)",
        filas,
    )

    # Publicaciones de X: el tipo va en el nombre del archivo de origen.
    cur.execute("SELECT id_publicacion, archivo_origen FROM fact_publicacion")
    filas_x = []
    for id_pub, archivo in cur.fetchall():
        n = normalizar(archivo)
        for tipo_norm, palabras in CLAVES.items():
            if any(p in n for p in palabras) and tipo_norm in tipos:
                filas_x.append((id_pub, tipos[tipo_norm]))

    cur.executemany(
        "INSERT IGNORE INTO bridge_pub_tipo_violencia VALUES (%s, %s)",
        filas_x,
    )

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM bridge_indicador_tipo_violencia")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bridge_pub_tipo_violencia")
    total_x = cur.fetchone()[0]
    print(f"Indicadores: {len(indicadores)}  con tipo: {len(indicadores) - sin_tipo}  sin tipo: {sin_tipo}")
    print(f"Relaciones indicador-tipo: {total}")
    print(f"Relaciones publicacion-tipo: {total_x}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
