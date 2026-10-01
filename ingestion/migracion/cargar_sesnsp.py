# Carga las series anuales del informe 911 (SESNSP) al esquema en estrella.
# Uso: python cargar_sesnsp.py
import json
import os
import re

import mysql.connector

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUTA = os.path.join(
    BASE, "data", "processed", "pdfs_chunks_limpios", "911_SESPC_chunks.json"
)

PATRON = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s+en\s+((?:19|20)\d{2})")

# tema -> (nombre legible, categoria, unidad)
SERIES = {
    "victimas_mujeres_feminicidio": ("Víctimas mujeres de feminicidio", "incidencia_delictiva"),
    "victimas_mujeres_homicidio_doloso": ("Víctimas mujeres de homicidio doloso", "incidencia_delictiva"),
    "victimas_mujeres_homicidio_culposo": ("Víctimas mujeres de homicidio culposo", "incidencia_delictiva"),
    "victimas_mujeres_lesiones_dolosas": ("Víctimas mujeres de lesiones dolosas", "incidencia_delictiva"),
    "victimas_mujeres_lesiones_culposas": ("Víctimas mujeres de lesiones culposas", "incidencia_delictiva"),
    "victimas_mujeres_secuestro": ("Víctimas mujeres de secuestro", "incidencia_delictiva"),
    "victimas_mujeres_trafico_menores": ("Víctimas mujeres de tráfico de menores", "incidencia_delictiva"),
    "victimas_mujeres_extorsion": ("Víctimas mujeres de extorsión", "incidencia_delictiva"),
    "victimas_mujeres_corrupcion_menores": ("Víctimas mujeres de corrupción de menores", "incidencia_delictiva"),
    "victimas_mujeres_trata_personas": ("Víctimas mujeres de trata de personas", "incidencia_delictiva"),
    "delitos_violencia_familiar": ("Presuntos delitos de violencia familiar", "incidencia_delictiva"),
    "delitos_violencia_genero": ("Presuntos delitos de violencia de género", "incidencia_delictiva"),
    "delitos_violacion_simple_equiparada": ("Presuntos delitos de violación simple y equiparada", "incidencia_delictiva"),
    "llamadas_911_violencia_contra_mujer": ("Llamadas 911 por violencia contra la mujer", "llamadas_911"),
    "llamadas_911_abuso_sexual": ("Llamadas 911 por abuso sexual", "llamadas_911"),
    "llamadas_911_acoso_hostigamiento_sexual": ("Llamadas 911 por acoso u hostigamiento sexual", "llamadas_911"),
    "llamadas_911_violacion": ("Llamadas 911 por violación", "llamadas_911"),
    "llamadas_911_violencia_pareja": ("Llamadas 911 por violencia de pareja", "llamadas_911"),
    "llamadas_911_violencia_familiar": ("Llamadas 911 por violencia familiar", "llamadas_911"),
}


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


def extraer_serie(texto):
    pares = {}
    for valor, anio in PATRON.findall(texto):
        anio = int(anio)
        if anio not in pares:
            pares[anio] = float(valor.replace(",", ""))
    return sorted(pares.items())


def main():
    cargar_env()
    if not os.environ.get("MYSQL_PASSWORD"):
        raise SystemExit("Falta MYSQL_PASSWORD.")

    with open(RUTA, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    conn = conexion()
    cur = conn.cursor()

    cur.execute(
        "INSERT IGNORE INTO fuentes (nombre, codigo, tipo_fuente, descripcion) "
        "VALUES ('SESNSP', 'SESNSP', 'GOBIERNO', "
        "'Incidencia delictiva y llamadas de emergencia 911')"
    )
    cur.execute("UPDATE fuentes SET codigo = 'SESNSP' WHERE nombre = 'SESNSP'")
    cur.execute("SELECT id_fuente FROM fuentes WHERE nombre = 'SESNSP'")
    id_fuente = cur.fetchone()[0]

    cur.execute("SELECT id_unidad FROM dim_unidad WHERE nombre = 'conteo'")
    id_unidad = cur.fetchone()[0]

    cur.execute("SELECT id_entidad FROM dim_entidad WHERE nivel = 'pais' LIMIT 1")
    id_pais = cur.fetchone()[0]

    # Limpieza idempotente de lo SESNSP
    cur.execute(
        "DELETE f FROM fact_indicador f JOIN dim_indicador i "
        "ON i.id_indicador = f.id_indicador WHERE i.id_fuente = %s",
        (id_fuente,),
    )
    cur.execute("DELETE FROM dim_indicador WHERE id_fuente = %s", (id_fuente,))

    # Años (dim_tiempo tipo 'dato')
    def tiempo(anio):
        cur.execute(
            "SELECT id_tiempo FROM dim_tiempo WHERE anio = %s AND tipo_tiempo = 'dato'",
            (anio,),
        )
        fila = cur.fetchone()
        if fila:
            return fila[0]
        cur.execute(
            "INSERT INTO dim_tiempo (anio, tipo_tiempo) VALUES (%s, 'dato')", (anio,)
        )
        return cur.lastrowid

    total = 0
    for chunk in chunks:
        tema = chunk.get("tema")
        if tema not in SERIES:
            continue
        nombre, categoria = SERIES[tema]
        serie = extraer_serie(chunk.get("texto") or "")
        if len(serie) < 3:
            continue

        codigo = "SESNSP_" + tema
        cur.execute(
            """
            INSERT INTO dim_indicador
              (codigo, nombre, id_fuente, categoria, tema, id_unidad)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (codigo, nombre, id_fuente, categoria, categoria, id_unidad),
        )
        id_indicador = cur.lastrowid

        for anio, valor in serie:
            cur.execute(
                """
                INSERT INTO fact_indicador
                  (id_indicador, id_entidad, id_tiempo, id_fuente, id_unidad, valor)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (id_indicador, id_pais, tiempo(anio), id_fuente, id_unidad, valor),
            )
            total += 1

    conn.commit()

    cur.execute(
        "SELECT COUNT(DISTINCT id_indicador) FROM dim_indicador WHERE id_fuente = %s",
        (id_fuente,),
    )
    n_ind = cur.fetchone()[0]
    print(f"Indicadores SESNSP: {n_ind}  Hechos: {total}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()