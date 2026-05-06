import pandas as pd
import mysql.connector
from getpass import getpass
import math


CSV_PATH = "data/processed/endireh_limpio.csv"


def limpiar_valor(valor):
    if pd.isna(valor):
        return None
    return valor


def main():
    df = pd.read_csv(CSV_PATH)

    print("Columnas del CSV:")
    print(df.columns.tolist())
    print("Total filas:", len(df))

    password = getpass("Contraseña MySQL: ")

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password=password,
        database="HUBDATOS"
    )

    cursor = conn.cursor()

    # 1. Asegurar fuente ENDIREH
    cursor.execute("""
        INSERT INTO fuentes (nombre, tipo_fuente, url, descripcion, fecha_consulta)
        VALUES (
            'ENDIREH INEGI',
            'ENDIREH',
            'https://www.inegi.org.mx/programas/endireh/',
            'Indicadores oficiales de ENDIREH procesados desde CSV',
            CURDATE()
        )
        ON DUPLICATE KEY UPDATE nombre = nombre;
    """)

    cursor.execute("""
        SELECT id_fuente
        FROM fuentes
        WHERE nombre = 'ENDIREH INEGI'
        LIMIT 1;
    """)

    id_fuente = cursor.fetchone()[0]

    sql = """
        INSERT INTO indicadores_endireh (
            id_fuente,
            codigo_indicador,
            nombre_indicador,
            categoria_indicador,
            ambito,
            agresor,
            periodo_medicion,
            poblacion_objetivo,
            entidad,
            anio,
            valor,
            unidad,
            fecha_referencia,
            datos_extra
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
    """

    insertados = 0

    for _, row in df.iterrows():
        valores = (
            id_fuente,
            limpiar_valor(row.get("codigo_indicador")),
            limpiar_valor(row.get("nombre_indicador")),
            limpiar_valor(row.get("categoria_indicador")),
            limpiar_valor(row.get("ambito")),
            limpiar_valor(row.get("agresor")),
            limpiar_valor(row.get("periodo_medicion")),
            limpiar_valor(row.get("poblacion_objetivo")),
            limpiar_valor(row.get("entidad")),
            int(row["anio"]) if not pd.isna(row.get("anio")) else None,
            float(row["valor"]) if not pd.isna(row.get("valor")) else None,
            limpiar_valor(row.get("unidad")),
            limpiar_valor(row.get("fecha_referencia")),
        )

        cursor.execute(sql, valores)
        insertados += 1

    conn.commit()

    cursor.close()
    conn.close()

    print(f"Registros insertados en indicadores_endireh: {insertados}")


if __name__ == "__main__":
    main()