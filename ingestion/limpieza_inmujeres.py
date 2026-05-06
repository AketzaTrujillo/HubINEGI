import os
import re
import unicodedata
import pandas as pd

CARPETA_INMUJERES = "data/raw/inmujeres"
SALIDA = "data/processed/inmujeres_limpio.csv"

METADATOS = {
    "indicador1.xls": "MUJERES DE 15 AÑOS Y MÁS CASADAS O UNIDAS CON AL MENOS UN INCIDENTE DE VIOLENCIA POR PARTE DE SU PAREJA EN LOS ÚLTIMOS 12 MESES POR TIPO DE VIOLENCIA Y TAMAÑO DE LOCALIDAD",
    "indicador2.xls": "MUJERES DE 15 AÑOS Y MÁS CASADAS O UNIDAS QUE HAN SUFRIDO VIOLENCIA ECONÓMICA POR PARTE DE SU PAREJA EN LOS ÚLTIMOS 12 MESES POR GRUPOS DE EDAD",
    "indicador3.xls": "MUJERES DE 15 AÑOS Y MÁS CASADAS O UNIDAS QUE HAN SUFRIDO VIOLENCIA EMOCIONAL POR PARTE DE SU PAREJA EN LOS ÚLTIMOS 12 MESES POR GRUPOS DE EDAD",
    "indicador4.xls": "MUJERES DE 15 AÑOS Y MÁS CASADAS O UNIDAS QUE HAN SUFRIDO VIOLENCIA FÍSICA POR PARTE DE SU PAREJA EN LOS ÚLTIMOS 12 MESES POR GRUPOS DE EDAD",
    "indicador5.xls": "MUJERES DE 15 AÑOS Y MÁS CASADAS O UNIDAS QUE HAN SUFRIDO VIOLENCIA SEXUAL POR PARTE DE SU PAREJA EN LOS ÚLTIMOS 12 MESES POR GRUPOS DE EDAD",
    "indicador6.xls": "MUJERES DE 15 AÑOS Y MÁS QUE HAN SUFRIDO ALGÚN INCIDENTE DE VIOLENCIA POR TIPO SEGÚN ÁMBITO",
    "indicador7.xls": "MUJERES DE 15 AÑOS Y MÁS QUE HAN SUFRIDO ALGÚN INCIDENTE DE VIOLENCIA EN CUALQUIER ÁMBITO A LO LARGO DE LA VIDA POR SITUACIÓN CONYUGAL",
    "indicador8.xls": "MUJERES VÍCTIMAS DE VIOLENCIA ATENDIDAS EN REFUGIOS Y CENTROS DE JUSTICIA",
    "indicador9.xls": "DENUNCIAS PRESENTADAS ANTE AGENCIAS DEL MINISTERIO PÚBLICO POR DELITOS DE GÉNERO",
    "indicador10.xls": "PRESUNTOS DELITOS DE VIOLACIÓN",
}


def limpiar_texto(texto):
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFC", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def normalizar_columna(col):
    col = limpiar_texto(col).lower()
    col = unicodedata.normalize("NFD", col)
    col = "".join(c for c in col if unicodedata.category(c) != "Mn")
    col = re.sub(r"[^a-z0-9]+", "_", col)
    return col.strip("_")


def leer_xls_html(ruta):
    tablas = pd.read_html(ruta)
    return tablas


def procesar_archivo(ruta, archivo):
    tablas = leer_xls_html(ruta)
    registros = []

    nombre_indicador = METADATOS.get(archivo, archivo)

    for i, tabla in enumerate(tablas):
        tabla = tabla.dropna(how="all")
        tabla = tabla.dropna(axis=1, how="all")

        if tabla.empty:
            continue

        tabla.columns = [normalizar_columna(c) for c in tabla.columns]


        for _, fila in tabla.iterrows():
            datos = fila.to_dict()

            registro = {
                "archivo_origen": archivo,
                "numero_tabla": i + 1,
                "nombre_indicador": nombre_indicador,
                "fuente": "INMUJERES",
            }

            for k, v in datos.items():
                registro[k] = limpiar_texto(v)

            registros.append(registro)

    return registros


def main():
    os.makedirs("data/processed", exist_ok=True)

    todos = []

    for archivo in sorted(os.listdir(CARPETA_INMUJERES)):
        if not archivo.endswith(".xls"):
            continue

        print(f"Procesando: {archivo}")
        ruta = os.path.join(CARPETA_INMUJERES, archivo)

        registros = procesar_archivo(ruta, archivo)
        todos.extend(registros)

    df = pd.DataFrame(todos)
    
    df = df.drop_duplicates()

    columnas_id = [
        "archivo_origen",
        "numero_tabla",
        "nombre_indicador",
        "fuente",
        "unnamed_0",
        "unnamed_1"
    ]

    columnas_id = [c for c in columnas_id if c in df.columns]

    columnas_anio = [
        c for c in df.columns
        if str(c).isdigit() and 1900 <= int(c) <= 2100
    ]

    df_largo = df.melt(
        id_vars=columnas_id,
        value_vars=columnas_anio,
        var_name="anio",
        value_name="valor"
    )

    df_largo = df_largo.rename(columns={
        "unnamed_0": "categoria",
        "unnamed_1": "subcategoria"
    })

    df_largo["valor"] = (
        df_largo["valor"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    df_largo["anio"] = pd.to_numeric(df_largo["anio"], errors="coerce")
    df_largo["valor"] = pd.to_numeric(df_largo["valor"], errors="coerce")

    df_largo = df_largo.dropna(subset=["anio", "valor"])

    df_largo["anio"] = df_largo["anio"].astype(int)

    df_largo.to_csv(SALIDA, index=False, encoding="utf-8-sig")

    print("\nLimpieza INMUJERES terminada")
    print("Total registros:", len(df_largo))
    print("Archivo guardado en:", SALIDA)



    df_largo.to_csv(SALIDA, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()