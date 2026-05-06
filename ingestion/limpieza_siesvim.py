import json
import os
import re
import pandas as pd


ENTRADA = "data/raw/datosSIESVIM.json"
SALIDA = "data/processed/siesvim_limpio.csv"


def es_numero(x):
    try:
        float(str(x).replace(",", "").strip())
        return True
    except:
        return False


def limpiar_texto(x):
    if x is None:
        return None
    x = str(x).strip()
    x = re.sub(r"\s+", " ", x)
    if x.lower() in ["nan", "none", "null", ""]:
        return None
    return x


def unir_texto(partes):
    partes = [limpiar_texto(p) for p in partes]
    partes = [p for p in partes if p is not None]
    return " ".join(partes)


def separar_nombre_y_valores(fila):
    valores = []
    nombre_partes = []

    for item in fila:
        item_limpio = limpiar_texto(item)

        if item_limpio is None:
            continue

        if es_numero(item_limpio):
            valores.append(float(str(item_limpio).replace(",", "")))
        else:
            nombre_partes.append(item_limpio)

    nombre = unir_texto(nombre_partes)

    return nombre, valores


def extraer_anios(filas):
    anios = []

    for fila in filas:
        if len(fila) == 1:
            valor = limpiar_texto(fila[0])
            if valor and valor.isdigit() and 1900 <= int(valor) <= 2100:
                anios.append(int(valor))

    return anios


def procesar_item(item):
    tema = item.get("tema")
    subtema = item.get("subtema")
    indicador = item.get("indicador")

    tabla = item.get("tabla", {})
    filas = tabla.get("filas", [])

    anios = extraer_anios(filas)

    registros = []

    for fila in filas:
        nombre, valores = separar_nombre_y_valores(fila)

        if not nombre or not valores:
            continue

        # omitir filas que son encabezados
        if nombre.lower() in [
            "total",
            "psicologica",
            "fisica",
            "sexual",
            "economica y/o patrimonial"
        ] and len(valores) == 0:
            continue

        # caso normal: una entidad con valores por año
        if anios and len(valores) == len(anios):
            for anio, valor in zip(anios, valores):
                registros.append({
                    "tema": tema,
                    "subtema": subtema,
                    "nombre_indicador": indicador,
                    "entidad": nombre,
                    "anio": anio,
                    "categoria": None,
                    "valor": valor,
                    "unidad": "porcentaje"
                })

        # caso con categorías repetidas por año:
        # ejemplo 2016 Total Psicologica Fisica...
        elif anios and len(valores) % len(anios) == 0:
            categorias_por_anio = len(valores) // len(anios)

            for i, valor in enumerate(valores):
                anio = anios[i // categorias_por_anio]
                categoria = f"categoria_{(i % categorias_por_anio) + 1}"

                registros.append({
                    "tema": tema,
                    "subtema": subtema,
                    "nombre_indicador": indicador,
                    "entidad": nombre,
                    "anio": anio,
                    "categoria": categoria,
                    "valor": valor,
                    "unidad": "porcentaje"
                })

        # caso sin años claros: guardarlo como categoría nacional si se puede
        else:
            for i, valor in enumerate(valores):
                registros.append({
                    "tema": tema,
                    "subtema": subtema,
                    "nombre_indicador": indicador,
                    "entidad": nombre,
                    "anio": None,
                    "categoria": f"valor_{i+1}",
                    "valor": valor,
                    "unidad": "porcentaje"
                })

    return registros


def main():
    os.makedirs("data/processed", exist_ok=True)

    with open(ENTRADA, "r", encoding="utf-8") as f:
        data = json.load(f)

    registros = []

    for item in data:
        registros.extend(procesar_item(item))

    df = pd.DataFrame(registros)

    df = df.drop_duplicates()

    df.to_csv(SALIDA, index=False, encoding="utf-8-sig")

    print("\nSIESVIM limpio generado")
    print("Total registros:", len(df))
    print("Archivo:", SALIDA)
    print("\nColumnas:")
    print(df.columns.tolist())
    print("\nPrimeras filas:")
    print(df.head())


if __name__ == "__main__":
    main()