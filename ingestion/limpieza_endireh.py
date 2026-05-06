import os
import re
import unicodedata
import pandas as pd


CARPETA_ENDIREH = "data/raw/endireh"
SALIDA = "data/processed/endireh_limpio.csv"


METADATOS = {
    "data1.csv": {
        "codigo_indicador": "ENDIREH_AYUDA_INSTITUCION_PAREJA_FS",
        "nombre_indicador": "Proporción de mujeres de 15 años y más que han sufrido violencia física y/o sexual por parte de su actual o última pareja y que han acudido al menos a una institución",
        "categoria_indicador": "busqueda_de_ayuda",
        "ambito": "pareja",
        "agresor": "pareja_actual_o_ultima",
        "periodo_medicion": "alguna_vez",
        "poblacion_objetivo": "mujeres de 15 años y más",
    },
    "data2.csv": {
        "codigo_indicador": "ENDIREH_AYUDA_AUTORIDAD_PAREJA_FS",
        "nombre_indicador": "Mujeres que han acudido al menos a una institución o autoridad en busca de ayuda, entre las mujeres que han sido alguna vez víctimas de violencia física y/o sexual infligida por su pareja",
        "categoria_indicador": "busqueda_de_ayuda",
        "ambito": "pareja",
        "agresor": "pareja",
        "periodo_medicion": "alguna_vez",
        "poblacion_objetivo": "mujeres víctimas de violencia física y/o sexual por pareja",
    },
    "data3.csv": {
        "codigo_indicador": "ENDIREH_FS_NO_PAREJA",
        "nombre_indicador": "Proporción de mujeres de 15 años y más que declararon haber experimentado al menos un incidente de violencia física y/o sexual infligida por cualquier agresor distinto a la pareja",
        "categoria_indicador": "prevalencia",
        "ambito": "no_pareja",
        "agresor": "distinto_a_pareja",
        "periodo_medicion": "alguna_vez",
        "poblacion_objetivo": "mujeres de 15 años y más",
    },
    "data4.csv": {
        "codigo_indicador": "ENDIREH_DANO_PAREJA",
        "nombre_indicador": "Proporción de mujeres de 15 años y más que declararon haber experimentado al menos un incidente de violencia por parte de su actual o última pareja a lo largo de la relación por tipo de daño ocasionado a consecuencia de la violencia sufrida",
        "categoria_indicador": "consecuencias",
        "ambito": "pareja",
        "agresor": "pareja_actual_o_ultima",
        "periodo_medicion": "a_lo_largo_de_la_relacion",
        "poblacion_objetivo": "mujeres de 15 años y más",
    },
    "data5.csv": {
        "codigo_indicador": "ENDIREH_FS_PAREJA_12M",
        "nombre_indicador": "Proporción de las mujeres de 15 años o más actualmente casadas o unidas que declararon haber experimentado al menos un incidente de violencia física y/o sexual por parte de su esposo o pareja en los últimos 12 meses",
        "categoria_indicador": "prevalencia",
        "ambito": "pareja",
        "agresor": "esposo_o_pareja",
        "periodo_medicion": "ultimos_12_meses",
        "poblacion_objetivo": "mujeres de 15 años o más actualmente casadas o unidas",
    },
    "data6.csv": {
        "codigo_indicador": "ENDIREH_CUALQUIER_TIPO_CUALQUIER_AGRESOR",
        "nombre_indicador": "Proporción de mujeres de 15 años y más que han sufrido al menos un incidente de violencia de cualquier tipo física, sexual, emocional, económica o patrimonial, por cualquier agresor",
        "categoria_indicador": "prevalencia_general",
        "ambito": "general",
        "agresor": "cualquier_agresor",
        "periodo_medicion": "alguna_vez",
        "poblacion_objetivo": "mujeres de 15 años y más",
    },
    "data7.csv": {
        "codigo_indicador": "ENDIREH_FS_PAREJA_EXPAREJA",
        "nombre_indicador": "Proporción de las mujeres de 15 años y más que declararon haber experimentado al menos un incidente de violencia física y/o sexual por parte de su pareja o expareja",
        "categoria_indicador": "prevalencia",
        "ambito": "pareja_expareja",
        "agresor": "pareja_o_expareja",
        "periodo_medicion": "alguna_vez",
        "poblacion_objetivo": "mujeres de 15 años y más",
    },
}


def limpiar_texto(texto):
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFC", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def normalizar_columna(columna):
    columna = limpiar_texto(columna).lower()
    columna = unicodedata.normalize("NFD", columna)
    columna = "".join(c for c in columna if unicodedata.category(c) != "Mn")
    columna = columna.replace(" ", "_")
    return columna


def normalizar_estado(estado):
    estado = limpiar_texto(estado)

    reemplazos = {
        "MÃ©xico": "México",
        "MÃ©xico ": "México",
        "MichoacÃ¡n": "Michoacán",
        "Nuevo LeÃ³n": "Nuevo León",
        "QuerÃ©taro": "Querétaro",
        "San Luis PotosÃ­": "San Luis Potosí",
        "YucatÃ¡n": "Yucatán",
        "Aguascalientes": "Aguascalientes",
        "Baja California": "Baja California",
        "Baja California Sur": "Baja California Sur",
        "Campeche": "Campeche",
        "Coahuila de Zaragoza": "Coahuila",
        "Colima": "Colima",
        "Chiapas": "Chiapas",
        "Chihuahua": "Chihuahua",
        "Ciudad de MÃ©xico": "Ciudad de México",
        "Ciudad de México": "Ciudad de México",
        "Durango": "Durango",
        "Guanajuato": "Guanajuato",
        "Guerrero": "Guerrero",
        "Hidalgo": "Hidalgo",
        "Jalisco": "Jalisco",
        "México": "Estado de México",
        "Morelos": "Morelos",
        "Nayarit": "Nayarit",
        "Nuevo León": "Nuevo León",
        "Oaxaca": "Oaxaca",
        "Puebla": "Puebla",
        "Querétaro": "Querétaro",
        "Quintana Roo": "Quintana Roo",
        "San Luis Potosí": "San Luis Potosí",
        "Sinaloa": "Sinaloa",
        "Sonora": "Sonora",
        "Tabasco": "Tabasco",
        "Tamaulipas": "Tamaulipas",
        "Tlaxcala": "Tlaxcala",
        "Veracruz de Ignacio de la Llave": "Veracruz",
        "Yucatán": "Yucatán",
        "Zacatecas": "Zacatecas",
    }

    return reemplazos.get(estado, estado)


def leer_csv_robusto(ruta):
    try:
        return pd.read_csv(ruta, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(ruta, encoding="latin1")


def procesar_archivo(ruta, archivo):
    df = leer_csv_robusto(ruta)

    df.columns = [normalizar_columna(c) for c in df.columns]

    metadatos = METADATOS.get(archivo)

    if metadatos is None:
        print(f"Archivo sin metadatos, se omite: {archivo}")
        return pd.DataFrame()

    # Detectar columnas esperadas
    col_entidad = "entidad"
    col_anio = "anio"
    col_valor = "porcentaje_mujeres"
    col_fecha = "fecha"

    columnas_necesarias = [col_entidad, col_anio, col_valor]

    for col in columnas_necesarias:
        if col not in df.columns:
            raise ValueError(f"Falta la columna '{col}' en {archivo}. Columnas encontradas: {df.columns.tolist()}")

    df["entidad"] = df[col_entidad].apply(normalizar_estado)
    df["anio"] = pd.to_numeric(df[col_anio], errors="coerce")
    df["valor"] = pd.to_numeric(df[col_valor], errors="coerce")

    if col_fecha in df.columns:
        df["fecha_referencia"] = pd.to_datetime(df[col_fecha], errors="coerce").dt.date
    else:
        df["fecha_referencia"] = None

    df = df.dropna(subset=["entidad", "anio", "valor"])
    df = df.drop_duplicates(subset=["entidad", "anio", "valor"])

    for k, v in metadatos.items():
        df[k] = v

    df["archivo_origen"] = archivo
    df["unidad"] = "porcentaje"

    columnas_finales = [
        "archivo_origen",
        "codigo_indicador",
        "nombre_indicador",
        "categoria_indicador",
        "ambito",
        "agresor",
        "periodo_medicion",
        "poblacion_objetivo",
        "entidad",
        "anio",
        "valor",
        "unidad",
        "fecha_referencia",
    ]

    return df[columnas_finales]


def main():
    os.makedirs("data/processed", exist_ok=True)

    dataframes = []

    for archivo in sorted(os.listdir(CARPETA_ENDIREH)):
        if not archivo.endswith(".csv"):
            continue

        ruta = os.path.join(CARPETA_ENDIREH, archivo)
        print(f"Procesando: {archivo}")

        df_archivo = procesar_archivo(ruta, archivo)

        if not df_archivo.empty:
            dataframes.append(df_archivo)

    if not dataframes:
        print("No se procesó ningún archivo.")
        return

    df_final = pd.concat(dataframes, ignore_index=True)

    df_final.to_csv(SALIDA, index=False, encoding="utf-8-sig")

    print("\nResumen ENDIREH")
    print("Total registros:", len(df_final))
    print("\nPor indicador:")
    print(df_final["codigo_indicador"].value_counts())
    print("\nPor año:")
    print(df_final["anio"].value_counts().sort_index())
    print("\nPor entidad:")
    print(df_final["entidad"].value_counts().head(10))

    print(f"\nArchivo guardado en: {SALIDA}")


if __name__ == "__main__":
    main()