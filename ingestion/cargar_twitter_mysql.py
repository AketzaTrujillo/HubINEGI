import json
from getpass import getpass

import pandas as pd
import mysql.connector


CSV_PATH = "../data/processed/dataset_twitter_limpio.csv"


def limpiar(valor):
    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if valor.lower() in ["nan", "none", "null", ""]:
        return None

    return valor


def obtener_id_fuente(cursor):
    cursor.execute("""
        SELECT id_fuente
        FROM fuentes
        WHERE nombre = 'X Twitter'
        LIMIT 1
    """)

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    raise Exception("No existe la fuente X Twitter")


def obtener_id_tipo_contenido(cursor, tipo):
    if tipo is None:
        return None

    cursor.execute("""
        SELECT id_tipo_contenido
        FROM tipos_contenido
        WHERE nombre = %s
        LIMIT 1
    """, (tipo,))

    resultado = cursor.fetchone()

    return resultado[0] if resultado else None


def obtener_id_ambito(cursor, ambito):
    if ambito is None:
        return None

    cursor.execute("""
        SELECT id_ambito
        FROM ambitos_violencia
        WHERE nombre = %s
        LIMIT 1
    """, (ambito,))

    resultado = cursor.fetchone()

    return resultado[0] if resultado else None


def obtener_id_ubicacion(cursor, row):
    estado = limpiar(row.get("estado"))

    if estado is None:
        return None

    municipio = limpiar(row.get("municipio_alcaldia"))
    lugar = limpiar(row.get("lugar_detectado"))
    nivel = limpiar(row.get("nivel_ubicacion"))

    cursor.execute("""
        SELECT id_ubicacion
        FROM ubicaciones
        WHERE
            estado <=> %s
            AND municipio_alcaldia <=> %s
            AND lugar_detectado <=> %s
            AND nivel_ubicacion <=> %s
        LIMIT 1
    """, (estado, municipio, lugar, nivel))

    resultado = cursor.fetchone()

    if resultado:
        return resultado[0]

    cursor.execute("""
        INSERT INTO ubicaciones (
            lugar_detectado,
            municipio_alcaldia,
            estado,
            nivel_ubicacion
        )
        VALUES (%s, %s, %s, %s)
    """, (lugar, municipio, estado, nivel))

    return cursor.lastrowid


def main():
    df = pd.read_csv(CSV_PATH)

    print("Total registros:", len(df))

    password = getpass("Contraseña MySQL: ")

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password=password,
        database="HUBDATOS"
    )

    cursor = conn.cursor()

    id_fuente = obtener_id_fuente(cursor)

    sql = """
        INSERT INTO registros (
            id_fuente,
            id_ambito,
            id_tipo_contenido,
            id_ubicacion,

            archivo_origen,
            anio_publicacion,
            anio_mencionado,
            fecha_publicacion,
            usuario,

            texto_original,
            texto_limpio,

            violencia_contra_mujer,
            es_basura,
            motivo_basura,
            nivel_confianza,

            datos_extra
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    insertados = 0

    for _, row in df.iterrows():

        id_tipo_contenido = obtener_id_tipo_contenido(
            cursor,
            limpiar(row.get("tipo_contenido"))
        )

        id_ambito = obtener_id_ambito(
            cursor,
            limpiar(row.get("tipo_violencia_archivo"))
        )

        id_ubicacion = obtener_id_ubicacion(cursor, row)

        datos_extra = {
            "estado_detectado": limpiar(row.get("estado")),
            "nivel_ubicacion": limpiar(row.get("nivel_ubicacion"))
        }

        valores = (
            id_fuente,
            id_ambito,
            id_tipo_contenido,
            id_ubicacion,

            limpiar(row.get("archivo_origen")),

            int(row["anio_publicacion"])
            if not pd.isna(row.get("anio_publicacion"))
            else None,

            int(row["anio_mencionado"])
            if not pd.isna(row.get("anio_mencionado"))
            else None,

            limpiar(row.get("fecha")),
            limpiar(row.get("usuario")),

            limpiar(row.get("texto_original")),
            limpiar(row.get("texto_limpio")),

            limpiar(row.get("violencia_mujer")) or "incierto",

            limpiar(row.get("es_basura")) or "no",

            limpiar(row.get("motivo_basura")),

            float(row["nivel_confianza"])
            if not pd.isna(row.get("nivel_confianza"))
            else None,

            json.dumps(datos_extra, ensure_ascii=False)
        )

        cursor.execute(sql, valores)

        insertados += 1

    conn.commit()

    cursor.close()
    conn.close()

    print(f"\nRegistros insertados: {insertados}")


if __name__ == "__main__":
    main()