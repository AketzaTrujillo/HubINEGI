# Carga el corpus documental (chunks limpios) en documentos/fragmentos (Fase 3).
# Uso: python cargar_corpus_faq.py
import glob
import json
import os

import mysql.connector

BASE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
CARPETA = os.path.join(BASE, "data", "processed", "pdfs_chunks_limpios")

MAPA_FUENTES = {
    "LEY GENERAL DE ACCESO DE LAS MUJERES A UNA VIDA LIBRE DE VIOLENCIA":
        "Ley General de Acceso de las Mujeres a una Vida Libre de Violencia",
    "ProtocoloAtencionCJM": "Protocolo de Atención de los CJM",
    "03ProtocoloEstandarizadoCJM": "Protocolo Estandarizado CJM",
    "01ModeloCJM_Secretariado_Ejecutivo": "Modelo CJM Secretariado Ejecutivo",
    "MODELO_DE_ATENCION": "Modelo de Atención",
    "MODELO_DE_SANCION": "Modelo de Sanción",
    "Modelo_Prevencion_de_Violencias_Contra_Mujeres":
        "Modelo de Prevención de Violencias contra las Mujeres",
    "Lineamientos BANAVIM 16_08_2018": "Lineamientos BANAVIM",
    "DIRECTORIO NACIONAL DE LOS CENTROS DE JUSTICIA PARA LAS MUJERES":
        "Directorio Nacional de los CJM",
    "Directorio_Nacional_CJM_2024": "Directorio Nacional CJM 2024",
    "Apoyo para Espacios de Refugio Especializados para Mujeres Víctimas de Violencia de Género":
        "Apoyo a Espacios de Refugio",
    "Violencia_de_Genero_Contra_Mujeres_en_Zonas_Ind_genas_en_M_xico":
        "Violencia de Género en Zonas Indígenas",
    "Que_te_agrada_y_que_te_agrade_en_las_relaciones":
        "Qué te agrada en las relaciones",
    "noestassola_conavim": "No Estás Sola (CONAVIM)",
    "911_SESPC": "SESNSP - Informe 911 (emergencias e incidencia delictiva)",
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
            os.environ.setdefault(
                clave.strip(), valor.strip().strip('"').strip("'")
            )


def conexion():
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD"),
        database=os.environ.get("MYSQL_DATABASE", "HUBDATOS"),
    )


def obtener_fuente(cur, nombre):
    cur.execute(
        "INSERT IGNORE INTO fuentes (nombre, tipo_fuente, descripcion) "
        "VALUES (%s, 'GOBIERNO', 'Corpus documental para FAQ')",
        (nombre,),
    )
    cur.execute("SELECT id_fuente FROM fuentes WHERE nombre = %s", (nombre,))
    return cur.fetchone()[0]


def main():
    cargar_env()
    if not os.environ.get("MYSQL_PASSWORD"):
        raise SystemExit("Falta MYSQL_PASSWORD.")

    conn = conexion()
    cur = conn.cursor()

    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    cur.execute("TRUNCATE TABLE fragmentos_documentos")
    cur.execute("TRUNCATE TABLE documentos")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    archivos = sorted(glob.glob(os.path.join(CARPETA, "*.json")))
    total_docs = 0
    total_frags = 0

    for ruta in archivos:
        with open(ruta, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        if not chunks:
            continue

        nombre_doc = chunks[0]["documento"]
        fuente = MAPA_FUENTES.get(nombre_doc, nombre_doc)
        id_fuente = obtener_fuente(cur, fuente)

        paginas = [c.get("pagina") for c in chunks if c.get("pagina")]
        total_paginas = max(paginas) if paginas else None

        cur.execute(
            """
            INSERT INTO documentos (
                id_fuente, nombre, nombre_archivo, total_paginas,
                total_chunks, incluido_faq, observaciones
            ) VALUES (%s, %s, %s, %s, %s, 1, %s)
            """,
            (
                id_fuente,
                fuente,
                os.path.basename(ruta),
                total_paginas,
                len(chunks),
                "Corpus normativo/institucional para FAQ.",
            ),
        )
        id_documento = cur.lastrowid

        cur.executemany(
            "INSERT INTO fragmentos_documentos (id_documento, chunk_id, pagina, texto) "
            "VALUES (%s, %s, %s, %s)",
            [
                (id_documento, c.get("chunk_id"), c.get("pagina"), c["texto"])
                for c in chunks
            ],
        )

        total_docs += 1
        total_frags += len(chunks)
        print(f"  {fuente}: {len(chunks)} fragmentos")

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM documentos")
    docs = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM fragmentos_documentos")
    frags = cur.fetchone()[0]

    print(f"\nDocumentos: {docs}  Fragmentos: {frags}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
