import os
import re
import json
import pandas as pd

from extraccion import separar_tweets, extraer_campos
from preprocesamiento import limpiar_texto
from clasificacion import clasificar_tipo
from ubicacion import detectar_ubicacion
from enriquecimiento import es_mujer
from filtro_ruido import detectar_basura
from temporalidad import detectar_anio_mencionado
from confianza import calcular_confianza


CARPETA_TXT = "data/raw/txt_x"
SALIDA_CSV = "data/processed/dataset_twitter_limpio.csv"
SALIDA_RESUMEN = "data/processed/resumen_limpieza.json"


def obtener_anio_y_tipo(nombre_archivo):
    nombre = nombre_archivo.replace(".txt", "").lower()

    anio_match = re.search(r"(2021|2022|2023|2024|2025|2026)", nombre)
    anio = anio_match.group(1) if anio_match else None

    tipo = nombre
    if anio:
        tipo = tipo.replace(anio, "")

    tipo = tipo.replace("violencia", "").strip()

    mapa_tipos = {
        "familiar": "violencia familiar",
        "economica": "violencia económica",
        "escolar": "violencia escolar",
        "fisica": "violencia física",
        "laboral": "violencia laboral",
        "pareja": "violencia de pareja",
        "psicologica": "violencia psicológica",
        "sexual": "violencia sexual"
    }

    tipo_violencia = mapa_tipos.get(tipo, tipo)

    return anio, tipo_violencia


data = []

for archivo in os.listdir(CARPETA_TXT):
    if not archivo.endswith(".txt"):
        continue

    ruta = os.path.join(CARPETA_TXT, archivo)

    anio, tipo_violencia_archivo = obtener_anio_y_tipo(archivo)

    with open(ruta, "r", encoding="utf-8") as f:
        texto = f.read()

    tweets = separar_tweets(texto)

    for t in tweets:
        usuario, fecha, texto_original = extraer_campos(t)

        limpio = limpiar_texto(texto_original)

        es_basura, motivo_basura = detectar_basura(limpio)
        
        ubicacion = detectar_ubicacion(limpio, usuario)
        
        tipo = clasificar_tipo(limpio)

        confianza = calcular_confianza(tipo, limpio)

        data.append({
            "archivo_origen": archivo,
            "anio": anio,
            "tipo_violencia_archivo": tipo_violencia_archivo,
            "usuario": usuario,
            "fecha": fecha,
            "anio_publicacion": anio,
            "anio_mencionado": detectar_anio_mencionado(limpio),
            "texto_original": texto_original,
            "texto_limpio": limpio,
            "tipo_contenido": tipo,
            "nivel_confianza": confianza,
            "lugar_detectado": ubicacion["lugar_detectado"],
            "municipio_alcaldia": ubicacion["municipio_alcaldia"],
            "estado": ubicacion["estado"],
            "nivel_ubicacion": ubicacion["nivel_ubicacion"],
            "violencia_mujer": es_mujer(limpio),
            "es_basura": es_basura,
            "motivo_basura": motivo_basura
        })


df = pd.DataFrame(data)

os.makedirs("data/processed", exist_ok=True)

df.to_csv(SALIDA_CSV, index=False, encoding="utf-8-sig")


resumen = {
    "total_registros": int(len(df)),
    "por_anio": df["anio"].value_counts().sort_index().to_dict(),
    "por_anio_publicacion": df["anio_publicacion"].value_counts().sort_index().to_dict(),
    "por_anio_mencionado": df["anio_mencionado"].value_counts().sort_index().to_dict(),
    "por_tipo_violencia": df["tipo_violencia_archivo"].value_counts().to_dict(),
    "por_tipo_contenido": df["tipo_contenido"].value_counts().to_dict(),
    "por_estado": df["estado"].value_counts().to_dict(),
    "basura_vs_utiles": df["es_basura"].value_counts().to_dict(),
    "confianza_promedio": float(df["nivel_confianza"].mean()),
    "confianza_por_tipo": df.groupby("tipo_contenido")["nivel_confianza"].mean().round(2).to_dict()
}

with open(SALIDA_RESUMEN, "w", encoding="utf-8") as f:
    json.dump(resumen, f, ensure_ascii=False, indent=4)


print("\nRESUMEN GENERAL")
print("Total registros:", len(df))

print("\nPor año:")
print(df["anio"].value_counts().sort_index())

print("\nPor tipo de violencia:")
print(df["tipo_violencia_archivo"].value_counts())

print("\nPor tipo de contenido:")
print(df["tipo_contenido"].value_counts())

print("\nConfianza promedio:")
print(df["nivel_confianza"].mean())

print("\nConfianza por tipo:")
print(df.groupby("tipo_contenido")["nivel_confianza"].mean().round(2))

print("\nPor estado:")
print(df["estado"].value_counts())

print("\nBasura vs útiles:")
print(df["es_basura"].value_counts())

print("\nPipeline terminado")
print(f"Dataset guardado en: {SALIDA_CSV}")
print(f"Resumen guardado en: {SALIDA_RESUMEN}")