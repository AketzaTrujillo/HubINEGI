import json
from getpass import getpass

import pandas as pd
import mysql.connector


CSV_PATH = "../data/processed/siesvim_limpio.csv"


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

    columnas_requeridas = [
        "tema",
        "subtema",
        "nombre_indicador",
        "entidad",
        "anio",
        "valor"
    ]

    faltantes = [c for c in columnas_requeridas if c not in df.columns]

    if faltantes:
        print("\nFaltan columnas necesarias:")
        print(faltantes)
        print("\nTu CSV de SIESVIM todavía necesita normalizarse antes de insertarlo.")
        return

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
        WHERE nombre = 'SIESVIM INEGI'
        LIMIT 1;
    """)

    resultado = cursor.fetchone()

    if resultado is None:
        cursor.execute("""
            INSERT INTO fuentes (nombre, tipo_fuente, url, descripcion, fecha_consulta)
            VALUES (
                'SIESVIM INEGI',
                'SIESVIM',
                'https://sc.inegi.org.mx/SIESVIM1/',
                'Indicadores del Sistema Integrado de Estadísticas sobre Violencia contra las Mujeres',
                CURDATE()
            );
        """)
        conn.commit()

        cursor.execute("""
            SELECT id_fuente
            FROM fuentes
            WHERE nombre = 'SIESVIM INEGI'
            LIMIT 1;
        """)

        resultado = cursor.fetchone()

    id_fuente = resultado[0]

    sql = """
        INSERT INTO indicadores_siesvim (
            id_fuente,
            tema,
            subtema,
            nombre_indicador,
            entidad,
            anio,
            categoria,
            valor,
            unidad,
            datos_extra
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    insertados = 0

    for _, row in df.iterrows():
        valor = limpiar_numero(row.get("valor"))

        if valor is None:
            continue

        datos_extra = {}

        for col in df.columns:
            if col not in [
                "tema",
                "subtema",
                "nombre_indicador",
                "entidad",
                "anio",
                "categoria",
                "valor",
                "unidad"
            ]:
                datos_extra[col] = limpiar_valor(row.get(col))

        valores = (
            id_fuente,
            limpiar_valor(row.get("tema")),
            limpiar_valor(row.get("subtema")),
            limpiar_valor(row.get("nombre_indicador")),
            limpiar_valor(row.get("entidad")),
            int(row["anio"]) if not pd.isna(row.get("anio")) else None,
            limpiar_valor(row.get("categoria")),
            valor,
            limpiar_valor(row.get("unidad")) or "porcentaje",
            json.dumps(datos_extra, ensure_ascii=False)
        )

        cursor.execute(sql, valores)
        insertados += 1

    conn.commit()

    cursor.close()
    conn.close()

    print(f"Registros insertados en indicadores_siesvim: {insertados}")


if __name__ == "__main__":
    main()