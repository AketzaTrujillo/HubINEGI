import json
from getpass import getpass

import pandas as pd
import mysql.connector


CSV_PATH = "data/processed/inmujeres_limpio.csv"


def limpiar_valor(valor):
    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if valor.lower() in ["nan", "none", "null", ""]:
        return None

    return valor


def limpiar_numero(valor):
    if pd.isna(valor):
        return None

    valor = str(valor).replace(",", "").strip()

    if valor.lower() in ["nan", "none", "null", ""]:
        return None

    try:
        return float(valor)
    except ValueError:
        return None


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

    cursor.execute("""
        SELECT id_fuente
        FROM fuentes
        WHERE nombre = 'INMUJERES SIE'
        LIMIT 1;
    """)

    resultado = cursor.fetchone()

    if resultado is None:
        cursor.execute("""
            INSERT INTO fuentes (nombre, tipo_fuente, url, descripcion, fecha_consulta)
            VALUES (
                'INMUJERES SIE',
                'SEMUJERES',
                NULL,
                'Indicadores del Sistema de Información Estadística de INMUJERES',
                CURDATE()
            );
        """)
        conn.commit()

        cursor.execute("""
            SELECT id_fuente
            FROM fuentes
            WHERE nombre = 'INMUJERES SIE'
            LIMIT 1;
        """)

        resultado = cursor.fetchone()

    id_fuente = resultado[0]

    sql = """
        INSERT INTO indicadores_inmujeres (
            id_fuente,
            archivo_origen,
            numero_tabla,
            nombre_indicador,
            categoria,
            subcategoria,
            anio,
            valor,
            unidad,
            datos_extra
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    insertados = 0

    for _, row in df.iterrows():
        datos_extra = {
            "fuente_csv": limpiar_valor(row.get("fuente"))
        }

        valores = (
            id_fuente,
            limpiar_valor(row.get("archivo_origen")),
            int(row["numero_tabla"]) if not pd.isna(row.get("numero_tabla")) else None,
            limpiar_valor(row.get("nombre_indicador")),
            limpiar_valor(row.get("categoria")),
            limpiar_valor(row.get("subcategoria")),
            int(row["anio"]) if not pd.isna(row.get("anio")) else None,
            limpiar_numero(row.get("valor")),
            limpiar_valor(row.get("unidad")) or "conteo",
            json.dumps(datos_extra, ensure_ascii=False)
        )

        cursor.execute(sql, valores)
        insertados += 1

    conn.commit()

    cursor.close()
    conn.close()

    print(f"Registros insertados en indicadores_inmujeres: {insertados}")


if __name__ == "__main__":
    main()