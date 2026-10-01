# Migra la metadata semántica de los .py a mhub_meta (Fase 2).
# Uso: python migrar_metadata_semantica.py
import os
import re
import sys

import mysql.connector

BACKEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "backend")
)
sys.path.insert(0, BACKEND)

from reglas_sql import REGLAS_SQL          # noqa: E402
from reglas_respuesta import REGLAS_RESPUESTA  # noqa: E402
from examples_nl_sql import EJEMPLOS_NL_SQL    # noqa: E402


def cargar_env():
    ruta = os.path.join(BACKEND, ".env")
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


def conexion(database):
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD"),
        database=database,
    )


# ------------------------------------------------------------
# Descripción del star schema (sem_tabla + sem_columna)
# ------------------------------------------------------------
TABLAS = [
    {
        "tabla": "fact_indicador",
        "descripcion": "Hechos numéricos de indicadores de ENDIREH, SIESVIM e INMUJERES.",
        "grano": "un valor por indicador + entidad + año + fuente",
        "es_fact": 1,
        "columnas": [
            ("id_indicador", "Indicador (FK dim_indicador).", "int", "indicador,metrica", 1, 1, 0, None),
            ("id_entidad", "Entidad federativa o país (FK dim_entidad).", "int", "entidad,estado", 1, 1, 0, "Jalisco"),
            ("id_tiempo", "Año del dato (FK dim_tiempo).", "int", "anio,año", 1, 1, 0, "2021"),
            ("id_fuente", "Fuente (FK fuentes).", "int", "fuente", 1, 1, 0, "ENDIREH"),
            ("id_unidad", "Unidad de medida (FK dim_unidad).", "int", "unidad", 1, 0, 0, "porcentaje"),
            ("valor", "Valor del indicador. Es la medida a agregar.", "decimal", "valor,cifra,porcentaje", 1, 0, 1, "54.09"),
            ("fecha_referencia", "Fecha de referencia del dato.", "date", "fecha", 1, 0, 0, None),
        ],
    },
    {
        "tabla": "dim_indicador",
        "descripcion": "Catálogo de indicadores con su metadata.",
        "grano": "un indicador",
        "es_fact": 0,
        "columnas": [
            ("id_indicador", "Identificador del indicador.", "int", None, 1, 1, 0, None),
            ("codigo", "Código único del indicador.", "varchar", "codigo", 1, 0, 0, "ENDIREH_FS_PAREJA_12M"),
            ("nombre", "Nombre del indicador.", "text", "indicador,nombre", 1, 1, 0, None),
            ("tema", "Tema (SIESVIM).", "varchar", "tema", 1, 1, 0, "Situación de la violencia"),
            ("subtema", "Subtema (SIESVIM) o subcategoría (INMUJERES).", "varchar", "subtema", 1, 1, 0, "Violencia de pareja"),
            ("categoria", "Categoría del indicador.", "varchar", "categoria", 1, 1, 0, "prevalencia"),
            ("ambito", "Ámbito (ENDIREH): pareja, no pareja, general.", "varchar", "ambito", 1, 1, 0, "pareja"),
            ("agresor", "Agresor (ENDIREH).", "varchar", "agresor", 1, 1, 0, "pareja_actual_o_ultima"),
            ("periodo_medicion", "Periodo de medición (ENDIREH).", "varchar", "periodo", 1, 1, 0, "alguna_vez"),
            ("poblacion_objetivo", "Población objetivo (ENDIREH).", "text", "poblacion", 0, 0, 0, None),
            ("id_fuente", "Fuente del indicador (FK fuentes).", "int", "fuente", 1, 1, 0, "ENDIREH"),
            ("id_unidad", "Unidad base (FK dim_unidad).", "int", "unidad", 1, 0, 0, "porcentaje"),
        ],
    },
    {
        "tabla": "dim_entidad",
        "descripcion": "Entidades federativas y país.",
        "grano": "una entidad",
        "es_fact": 0,
        "columnas": [
            ("id_entidad", "Identificador de la entidad.", "int", None, 1, 1, 0, None),
            ("nombre_canonico", "Nombre canónico de la entidad.", "varchar", "entidad,estado", 1, 1, 0, "Jalisco"),
            ("nivel", "Nivel: pais, estado, municipio, alcaldia.", "enum", "nivel", 1, 1, 0, "estado"),
            ("entidad_padre", "Entidad padre (para municipios).", "int", None, 1, 0, 0, None),
        ],
    },
    {
        "tabla": "dim_tiempo",
        "descripcion": "Años separados por semántica.",
        "grano": "un año por tipo",
        "es_fact": 0,
        "columnas": [
            ("id_tiempo", "Identificador del tiempo.", "int", None, 1, 1, 0, None),
            ("anio", "Año.", "smallint", "anio,año", 1, 1, 0, "2021"),
            ("tipo_tiempo", "dato, publicacion o mencion.", "enum", "tipo", 1, 1, 0, "dato"),
        ],
    },
    {
        "tabla": "dim_unidad",
        "descripcion": "Unidades de medida.",
        "grano": "una unidad",
        "es_fact": 0,
        "columnas": [
            ("id_unidad", "Identificador de unidad.", "int", None, 1, 1, 0, None),
            ("nombre", "Nombre de la unidad.", "varchar", "unidad", 1, 1, 0, "porcentaje"),
            ("tipo", "porcentaje, conteo, tasa o indice.", "enum", "tipo", 1, 1, 0, "porcentaje"),
        ],
    },
    {
        "tabla": "fuentes",
        "descripcion": "Fuentes de información de MHub.",
        "grano": "una fuente",
        "es_fact": 0,
        "columnas": [
            ("id_fuente", "Identificador de la fuente.", "int", None, 1, 1, 0, None),
            ("nombre", "Nombre de la fuente.", "varchar", "fuente", 1, 1, 0, "ENDIREH INEGI"),
            ("codigo", "Código: X, ENDIREH, SIESVIM, INMUJERES.", "varchar", "codigo", 1, 1, 0, "ENDIREH"),
            ("tipo_fuente", "Tipo de fuente.", "enum", "tipo", 1, 1, 0, "ENDIREH"),
        ],
    },
    {
        "tabla": "fact_publicacion",
        "descripcion": "Publicaciones de X. No son casos ni estadística oficial.",
        "grano": "una publicación",
        "es_fact": 1,
        "columnas": [
            ("id_publicacion", "Identificador de la publicación.", "bigint", None, 1, 1, 0, None),
            ("id_entidad", "Entidad detectada (FK dim_entidad).", "int", "entidad,estado", 1, 1, 0, "Jalisco"),
            ("id_tiempo_pub", "Año de publicación (FK dim_tiempo).", "int", "anio", 1, 1, 0, "2021"),
            ("id_tiempo_mencion", "Año mencionado (FK dim_tiempo).", "int", "anio", 1, 1, 0, "2021"),
            ("violencia_mujer", "si, no o incierto.", "enum", "clasificacion", 1, 1, 0, "si"),
            ("es_basura", "si o no. Las publicaciones basura se excluyen por defecto.", "enum", "basura", 1, 1, 0, "no"),
            ("nivel_confianza", "Confianza de la clasificación (0 a 1).", "decimal", "confianza", 1, 0, 1, "0.91"),
        ],
    },
    {
        "tabla": "tipos_violencia",
        "descripcion": "Catálogo de tipos de violencia (para X).",
        "grano": "un tipo",
        "es_fact": 0,
        "columnas": [
            ("id_tipo_violencia", "Identificador.", "int", None, 1, 1, 0, None),
            ("nombre", "Nombre del tipo de violencia.", "varchar", "tipo,violencia", 1, 1, 0, "psicológica"),
        ],
    },
    {
        "tabla": "ambitos_violencia",
        "descripcion": "Catálogo de ámbitos de violencia (para X).",
        "grano": "un ámbito",
        "es_fact": 0,
        "columnas": [
            ("id_ambito", "Identificador.", "int", None, 1, 1, 0, None),
            ("nombre", "Nombre del ámbito.", "varchar", "ambito", 1, 1, 0, "violencia familiar"),
        ],
    },
    {
        "tabla": "tipos_contenido",
        "descripcion": "Catálogo de tipos de contenido (para X).",
        "grano": "un tipo",
        "es_fact": 0,
        "columnas": [
            ("id_tipo_contenido", "Identificador.", "int", None, 1, 1, 0, None),
            ("nombre", "Nombre del tipo de contenido.", "varchar", "contenido", 1, 1, 0, "noticia"),
        ],
    },
    {
        "tabla": "bridge_pub_tipo_violencia",
        "descripcion": "Relación M:N entre publicaciones y tipos de violencia.",
        "grano": "publicación + tipo",
        "es_fact": 0,
        "columnas": [
            ("id_publicacion", "FK fact_publicacion.", "bigint", None, 1, 1, 0, None),
            ("id_tipo_violencia", "FK tipos_violencia.", "int", None, 1, 1, 0, None),
        ],
    },
    {
        "tabla": "bridge_pub_tipo_contenido",
        "descripcion": "Relación M:N entre publicaciones y tipos de contenido.",
        "grano": "publicación + tipo",
        "es_fact": 0,
        "columnas": [
            ("id_publicacion", "FK fact_publicacion.", "bigint", None, 1, 1, 0, None),
            ("id_tipo_contenido", "FK tipos_contenido.", "int", None, 1, 1, 0, None),
        ],
    },
    {
        "tabla": "bridge_pub_ambito",
        "descripcion": "Relación M:N entre publicaciones y ámbitos.",
        "grano": "publicación + ámbito",
        "es_fact": 0,
        "columnas": [
            ("id_publicacion", "FK fact_publicacion.", "bigint", None, 1, 1, 0, None),
            ("id_ambito", "FK ambitos_violencia.", "int", None, 1, 1, 0, None),
        ],
    },
]


def migrar_tablas(cur):
    for t in TABLAS:
        cur.execute(
            """
            INSERT INTO sem_tabla (tabla, descripcion, grano, es_fact)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE descripcion=VALUES(descripcion),
                grano=VALUES(grano), es_fact=VALUES(es_fact)
            """,
            (t["tabla"], t["descripcion"], t["grano"], t["es_fact"]),
        )
        for (col, desc, tipo, sin, filt, agr, med, ej) in t["columnas"]:
            cur.execute(
                """
                INSERT INTO sem_columna (
                    tabla, columna, descripcion, tipo_dato, sinonimos,
                    es_filtrable, es_agrupable, es_medida, ejemplo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE descripcion=VALUES(descripcion),
                    sinonimos=VALUES(sinonimos), es_filtrable=VALUES(es_filtrable),
                    es_agrupable=VALUES(es_agrupable), es_medida=VALUES(es_medida)
                """,
                (t["tabla"], col, desc, tipo, sin, filt, agr, med, ej),
            )
    print(f"sem_tabla: {len(TABLAS)} tablas")


def migrar_reglas(cur):
    cur.execute("DELETE FROM sem_regla")
    orden = 0

    cur.execute(
        "INSERT INTO sem_regla (grupo, orden, texto) VALUES (%s, %s, %s)",
        ("sql", orden, REGLAS_SQL.strip()),
    )

    for i, linea in enumerate(
        [l.strip() for l in REGLAS_RESPUESTA.splitlines() if l.strip().startswith("-")],
        start=1,
    ):
        cur.execute(
            "INSERT INTO sem_regla (grupo, orden, texto) VALUES (%s, %s, %s)",
            ("respuesta", i, linea.lstrip("- ").strip()),
        )

    cur.execute("SELECT COUNT(*) FROM sem_regla")
    print(f"sem_regla: {cur.fetchone()[0]} filas")


def migrar_ejemplos(cur):
    cur.execute("DELETE FROM sem_ejemplo")
    bloques = re.split(r"\n\s*\n\s*\n", EJEMPLOS_NL_SQL)
    n = 0
    for bloque in bloques:
        if "SQL" not in bloque:
            continue
        idx = bloque.find("SQL")
        pregunta = bloque[:idx].strip()
        sql = bloque[idx:].strip()
        sql = re.sub(r"^SQL(?:\s+anterior)?\s*:\s*", "", sql).strip()
        pregunta = re.sub(r"^Pregunta(?:\s+anterior|\s+actual)?\s*:\s*", "", pregunta).strip()
        if not pregunta or not sql:
            continue
        intencion = (
            "CONVERSACION"
            if "NO_SE_PUEDE_CONSULTAR" in sql
            else "CONSULTA_DETALLE"
        )
        cur.execute(
            """
            INSERT INTO sem_ejemplo (pregunta, consulta_sql, id_intencion)
            VALUES (%s, %s, %s)
            """,
            (pregunta, sql, intencion),
        )
        n += 1
    print(f"sem_ejemplo: {n} ejemplos")


def main():
    cargar_env()
    if not os.environ.get("MYSQL_PASSWORD"):
        raise SystemExit("Falta MYSQL_PASSWORD.")

    conn = conexion("mhub_meta")
    cur = conn.cursor()

    migrar_tablas(cur)
    migrar_reglas(cur)
    migrar_ejemplos(cur)

    conn.commit()
    cur.close()
    conn.close()
    print("Metadata semántica migrada.")


if __name__ == "__main__":
    main()
