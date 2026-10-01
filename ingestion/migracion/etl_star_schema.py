# ETL de las tablas actuales al esquema en estrella (Fase 1).
# Uso: python etl_star_schema.py
import hashlib
import os
import re
import sys
import unicodedata
import difflib

import mysql.connector


# ------------------------------------------------------------
# Conexión (lee backend/.env)
# ------------------------------------------------------------
def cargar_env():
    ruta = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "backend", ".env"
        )
    )
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


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------
def normalizar(texto):
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def md5_corto(*partes):
    base = "|".join("" if p is None else str(p) for p in partes)
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:20]


# ------------------------------------------------------------
# Cachés de dimensiones
# ------------------------------------------------------------
class Dimensiones:
    def __init__(self, cur):
        self.cur = cur
        self.entidades_canon = {}
        self.entidades_alias = {}
        self.unidades = {}
        self.tiempos = {}
        self.fuentes = {}
        self.indicadores = {}
        self._cargar()

    def _cargar(self):
        self.cur.execute("SELECT id_entidad, nombre_canonico FROM dim_entidad")
        for id_, nombre in self.cur.fetchall():
            self.entidades_canon[normalizar(nombre)] = id_

        self.cur.execute("SELECT alias, id_entidad FROM dim_entidad_alias")
        for alias, id_ in self.cur.fetchall():
            self.entidades_alias[normalizar(alias)] = id_

        self.cur.execute("SELECT id_unidad, nombre FROM dim_unidad")
        for id_, nombre in self.cur.fetchall():
            self.unidades[normalizar(nombre)] = id_

        self.cur.execute("SELECT id_fuente, codigo FROM fuentes")
        for id_, codigo in self.cur.fetchall():
            if codigo:
                self.fuentes[codigo] = id_

    def entidad(self, valor):
        if valor is None or str(valor).strip() == "":
            return None
        n = normalizar(valor)
        if n in self.entidades_alias:
            return self.entidades_alias[n]
        if n in self.entidades_canon:
            return self.entidades_canon[n]

        base = re.split(r"\bde\b", n)[0].strip()
        if base in self.entidades_canon:
            return self.entidades_canon[base]

        cercanos = difflib.get_close_matches(
            n, list(self.entidades_canon.keys()), n=1, cutoff=0.85
        )
        if cercanos:
            return self.entidades_canon[cercanos[0]]
        return None

    def unidad(self, nombre):
        if nombre is None:
            return None
        n = normalizar(nombre)
        if n in self.unidades:
            return self.unidades[n]
        tipo = "conteo" if "conteo" in n else "porcentaje"
        self.cur.execute(
            "INSERT IGNORE INTO dim_unidad (nombre, tipo) VALUES (%s, %s)",
            (nombre, tipo),
        )
        self.cur.execute(
            "SELECT id_unidad FROM dim_unidad WHERE nombre = %s", (nombre,)
        )
        id_ = self.cur.fetchone()[0]
        self.unidades[n] = id_
        return id_

    def tiempo(self, anio, tipo):
        clave = (anio, tipo)
        if clave in self.tiempos:
            return self.tiempos[clave]
        self.cur.execute(
            "SELECT id_tiempo FROM dim_tiempo WHERE anio <=> %s AND tipo_tiempo = %s",
            (anio, tipo),
        )
        fila = self.cur.fetchone()
        if fila:
            id_ = fila[0]
        else:
            self.cur.execute(
                "INSERT INTO dim_tiempo (anio, tipo_tiempo) VALUES (%s, %s)",
                (anio, tipo),
            )
            id_ = self.cur.lastrowid
        self.tiempos[clave] = id_
        return id_

    def indicador(self, codigo, datos):
        if codigo in self.indicadores:
            return self.indicadores[codigo]
        self.cur.execute(
            """
            INSERT INTO dim_indicador (
                codigo, nombre, descripcion, id_fuente,
                tema, subtema, categoria, ambito, agresor,
                periodo_medicion, poblacion_objetivo, id_unidad
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                codigo,
                datos.get("nombre"),
                datos.get("descripcion"),
                datos.get("id_fuente"),
                datos.get("tema"),
                datos.get("subtema"),
                datos.get("categoria"),
                datos.get("ambito"),
                datos.get("agresor"),
                datos.get("periodo_medicion"),
                datos.get("poblacion_objetivo"),
                datos.get("id_unidad"),
            ),
        )
        id_ = self.cur.lastrowid
        self.indicadores[codigo] = id_
        return id_


# ------------------------------------------------------------
# Limpieza de tablas del star schema (no toca las originales)
# ------------------------------------------------------------
def limpiar(cur):
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for tabla in [
        "bridge_pub_tipo_violencia",
        "bridge_pub_tipo_contenido",
        "bridge_pub_ambito",
        "fact_publicacion",
        "fact_indicador",
        "dim_indicador_alias",
        "dim_indicador",
        "dim_tiempo",
    ]:
        cur.execute(f"TRUNCATE TABLE {tabla}")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")


# ------------------------------------------------------------
# Fuente 1: ENDIREH
# ------------------------------------------------------------
def etl_endireh(cur, dim):
    cur.execute(
        """
        SELECT codigo_indicador, nombre_indicador, categoria_indicador,
               ambito, agresor, periodo_medicion, poblacion_objetivo,
               entidad, anio, valor, unidad, fecha_referencia
        FROM indicadores_endireh
        """
    )
    filas = cur.fetchall()
    id_fuente = dim.fuentes["ENDIREH"]
    id_unidad = dim.unidad("porcentaje")

    hechos = []
    for (
        codigo, nombre, categoria, ambito, agresor, periodo, poblacion,
        entidad, anio, valor, unidad, fecha,
    ) in filas:
        id_indicador = dim.indicador(
            codigo,
            {
                "nombre": nombre,
                "categoria": categoria,
                "ambito": ambito,
                "agresor": agresor,
                "periodo_medicion": periodo,
                "poblacion_objetivo": poblacion,
                "id_fuente": id_fuente,
                "id_unidad": id_unidad,
            },
        )
        hechos.append(
            (
                id_indicador,
                dim.entidad(entidad),
                dim.tiempo(int(anio) if anio is not None else None, "dato"),
                id_fuente,
                id_unidad,
                valor,
                fecha,
            )
        )

    _insertar_hechos(cur, hechos)
    return len(filas)


# ------------------------------------------------------------
# Fuente 2: SIESVIM
# ------------------------------------------------------------
def etl_siesvim(cur, dim):
    cur.execute(
        """
        SELECT tema, subtema, nombre_indicador, entidad, anio,
               categoria, valor, unidad
        FROM indicadores_siesvim
        """
    )
    filas = cur.fetchall()
    id_fuente = dim.fuentes["SIESVIM"]
    id_unidad = dim.unidad("porcentaje")

    hechos = []
    for tema, subtema, nombre, entidad, anio, categoria, valor, unidad in filas:
        codigo = "SIESVIM_" + md5_corto(nombre, tema, subtema, categoria)
        id_indicador = dim.indicador(
            codigo,
            {
                "nombre": nombre,
                "tema": tema,
                "subtema": subtema,
                "categoria": categoria,
                "id_fuente": id_fuente,
                "id_unidad": id_unidad,
            },
        )
        hechos.append(
            (
                id_indicador,
                dim.entidad(entidad),
                dim.tiempo(int(anio) if anio is not None else None, "dato"),
                id_fuente,
                id_unidad,
                valor,
                None,
            )
        )

    _insertar_hechos(cur, hechos)
    return len(filas)


# ------------------------------------------------------------
# Fuente 3: INMUJERES
# ------------------------------------------------------------
def etl_inmujeres(cur, dim):
    cur.execute(
        """
        SELECT archivo_origen, numero_tabla, nombre_indicador,
               categoria, subcategoria, anio, valor, unidad
        FROM indicadores_inmujeres
        """
    )
    filas = cur.fetchall()
    id_fuente = dim.fuentes["INMUJERES"]
    id_unidad = dim.unidad("conteo")
    id_pais = dim.entidades_canon[normalizar("Estados Unidos Mexicanos")]

    hechos = []
    for archivo, numero, nombre, categoria, subcategoria, anio, valor, unidad in filas:
        codigo = "INMUJERES_" + md5_corto(nombre, categoria, subcategoria)
        id_indicador = dim.indicador(
            codigo,
            {
                "nombre": nombre,
                "subtema": subcategoria,
                "categoria": categoria,
                "id_fuente": id_fuente,
                "id_unidad": id_unidad,
            },
        )
        hechos.append(
            (
                id_indicador,
                id_pais,
                dim.tiempo(int(anio) if anio is not None else None, "dato"),
                id_fuente,
                id_unidad,
                valor,
                None,
            )
        )

    _insertar_hechos(cur, hechos)
    return len(filas)


def _insertar_hechos(cur, hechos):
    cur.executemany(
        """
        INSERT INTO fact_indicador (
            id_indicador, id_entidad, id_tiempo, id_fuente,
            id_unidad, valor, fecha_referencia
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        hechos,
    )


# ------------------------------------------------------------
# Fuente 4: X / registros
# ------------------------------------------------------------
def etl_publicaciones(cur, dim):
    cur.execute(
        """
        SELECT r.id_registro, r.id_tipo_violencia, r.id_tipo_contenido,
               r.id_ambito, r.archivo_origen, r.anio_publicacion,
               r.anio_mencionado, r.usuario, r.texto_original,
               r.texto_limpio, r.violencia_contra_mujer, r.es_basura,
               r.motivo_basura, r.nivel_confianza, u.estado
        FROM registros r
        LEFT JOIN ubicaciones u ON u.id_ubicacion = r.id_ubicacion
        """
    )
    filas = cur.fetchall()
    id_fuente = dim.fuentes["X"]

    vistas = set()
    publicaciones = []
    bridges_violencia = []
    bridges_contenido = []
    bridges_ambito = []

    for (
        _id, id_tv, id_tc, id_amb, archivo, anio_pub, anio_menc, usuario,
        texto_original, texto_limpio, violencia, basura, motivo, confianza,
        estado,
    ) in filas:
        clave_dedup = normalizar(texto_limpio or texto_original or "")
        if clave_dedup and clave_dedup in vistas:
            continue
        vistas.add(clave_dedup)

        publicaciones.append(
            (
                id_fuente,
                dim.entidad(estado),
                dim.tiempo(int(anio_pub) if anio_pub else None, "publicacion"),
                dim.tiempo(int(anio_menc) if anio_menc else None, "mencion"),
                archivo,
                usuario,
                texto_original,
                texto_limpio,
                violencia or "incierto",
                basura or "no",
                motivo,
                float(confianza) if confianza is not None else None,
            )
        )

        indice = len(publicaciones) - 1
        if id_tv:
            bridges_violencia.append((indice, id_tv))
        if id_tc:
            bridges_contenido.append((indice, id_tc))
        if id_amb:
            bridges_ambito.append((indice, id_amb))

    cur.executemany(
        """
        INSERT INTO fact_publicacion (
            id_fuente, id_entidad, id_tiempo_pub, id_tiempo_mencion,
            archivo_origen, usuario, texto_original, texto_limpio,
            violencia_mujer, es_basura, motivo_basura, nivel_confianza
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        publicaciones,
    )

    # Los ids reales se asignan en orden de inserción (AUTO_INCREMENT desde 1).
    def id_real(indice):
        return indice + 1

    cur.executemany(
        "INSERT IGNORE INTO bridge_pub_tipo_violencia VALUES (%s, %s)",
        [(id_real(i), tv) for i, tv in bridges_violencia],
    )
    cur.executemany(
        "INSERT IGNORE INTO bridge_pub_tipo_contenido VALUES (%s, %s)",
        [(id_real(i), tc) for i, tc in bridges_contenido],
    )
    cur.executemany(
        "INSERT IGNORE INTO bridge_pub_ambito VALUES (%s, %s)",
        [(id_real(i), a) for i, a in bridges_ambito],
    )

    return len(publicaciones)


# ------------------------------------------------------------
def main():
    cargar_env()
    if not os.environ.get("MYSQL_PASSWORD"):
        raise SystemExit("Falta MYSQL_PASSWORD (revisa backend/.env).")

    conn = conexion()
    cur = conn.cursor()

    print("Limpiando star schema...")
    limpiar(cur)

    dim = Dimensiones(cur)

    print("ETL ENDIREH...")
    n_end = etl_endireh(cur, dim)
    print("ETL SIESVIM...")
    n_sie = etl_siesvim(cur, dim)
    print("ETL INMUJERES...")
    n_inm = etl_inmujeres(cur, dim)
    print("ETL X / publicaciones...")
    n_pub = etl_publicaciones(cur, dim)

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM fact_indicador")
    total_fi = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM fact_publicacion")
    total_fp = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dim_indicador")
    total_di = cur.fetchone()[0]

    print("\nResumen ETL")
    print(f"  ENDIREH leidos:     {n_end}")
    print(f"  SIESVIM leidos:     {n_sie}")
    print(f"  INMUJERES leidos:   {n_inm}")
    print(f"  X leidos:           {n_pub}")
    print(f"  fact_indicador:     {total_fi}")
    print(f"  fact_publicacion:   {total_fp}")
    print(f"  dim_indicador:      {total_di}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
