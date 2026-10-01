"""Capa semántica de MHub (Fase 2).

Carga la metadata desde `mhub_meta` y resuelve entidades, indicadores,
métricas y fuentes. Expone el contexto para el prompt de NL→SQL.

Si `mhub_meta` no existe o está vacía, las funciones degradan de forma
controlada (devuelven listas vacías / None) para no romper el backend.
"""
import re
import unicodedata

from database import ejecutar_select

_CATALOGO = None


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    return texto


# ------------------------------------------------------------
# Carga del catálogo
# ------------------------------------------------------------
def _cargar():
    catalogo = {
        "tablas": [],
        "columnas": {},
        "metricas": [],
        "sinonimos": [],
        "ejemplos": [],
        "reglas_sql": [],
        "reglas_respuesta": [],
        "reglas_explicacion": [],
        "intenciones": [],
    }

    try:
        catalogo["tablas"] = ejecutar_select(
            "SELECT tabla, descripcion, grano, es_fact FROM sem_tabla "
            "ORDER BY es_fact DESC, tabla",
            database="mhub_meta",
        )

        for fila in ejecutar_select(
            "SELECT tabla, columna, descripcion, tipo_dato, sinonimos, "
            "es_filtrable, es_agrupable, es_medida, ejemplo FROM sem_columna",
            database="mhub_meta",
        ):
            catalogo["columnas"].setdefault(fila["tabla"], []).append(fila)

        catalogo["metricas"] = ejecutar_select(
            "SELECT nombre, expresion_sql, sinonimos, requiere_columna, descripcion "
            "FROM sem_metrica",
            database="mhub_meta",
        )

        catalogo["sinonimos"] = ejecutar_select(
            "SELECT termino, tipo_destino, id_destino FROM sem_sinonimo",
            database="mhub_meta",
        )

        catalogo["ejemplos"] = ejecutar_select(
            "SELECT pregunta, consulta_sql, id_intencion FROM sem_ejemplo",
            database="mhub_meta",
        )

        for fila in ejecutar_select(
            "SELECT grupo, orden, texto FROM sem_regla ORDER BY grupo, orden",
            database="mhub_meta",
        ):
            clave = {
                "sql": "reglas_sql",
                "respuesta": "reglas_respuesta",
                "explicacion": "reglas_explicacion",
            }.get(fila["grupo"])
            if clave:
                catalogo[clave].append(fila["texto"])

        catalogo["intenciones"] = ejecutar_select(
            "SELECT id_intencion, descripcion, requiere_bd, prioridad "
            "FROM cat_intencion ORDER BY prioridad",
            database="mhub_meta",
        )
    except Exception as error:
        print(f"[semantic_loader] mhub_meta no disponible: {error}")

    return catalogo


def cargar_catalogo(forzar=False):
    global _CATALOGO
    if _CATALOGO is None or forzar:
        _CATALOGO = _cargar()
    return _CATALOGO


# ------------------------------------------------------------
# Contexto para el prompt
# ------------------------------------------------------------
def contexto_prompt():
    catalogo = cargar_catalogo()
    lineas = ["BASE DE DATOS: HUBDATOS (esquema en estrella)", ""]

    for tabla in catalogo["tablas"]:
        marca = " (TABLA DE HECHOS)" if tabla["es_fact"] else ""
        lineas.append(f"TABLA: {tabla['tabla']}{marca}")
        if tabla["descripcion"]:
            lineas.append(f"  Descripción: {tabla['descripcion']}")
        if tabla["grano"]:
            lineas.append(f"  Grano: {tabla['grano']}")
        for col in catalogo["columnas"].get(tabla["tabla"], []):
            flags = []
            if col["es_medida"]:
                flags.append("medida")
            if col["es_filtrable"]:
                flags.append("filtrable")
            if col["es_agrupable"]:
                flags.append("agrupable")
            sufijo = f" [{', '.join(flags)}]" if flags else ""
            desc = f" - {col['descripcion']}" if col["descripcion"] else ""
            lineas.append(f"  - {col['columna']}{sufijo}{desc}")
        lineas.append("")

    if catalogo["metricas"]:
        lineas.append("MÉTRICAS DISPONIBLES:")
        for m in catalogo["metricas"]:
            lineas.append(
                f"  - {m['nombre']} -> {m['expresion_sql']} "
                f"(sinónimos: {m['sinonimos']})"
            )
        lineas.append("")

    if catalogo["reglas_sql"]:
        lineas.append("REGLAS SQL:")
        lineas.extend(catalogo["reglas_sql"])
        lineas.append("")

    if catalogo["ejemplos"]:
        lineas.append("EJEMPLOS:")
        for e in catalogo["ejemplos"][:30]:
            lineas.append(f"  Pregunta: {e['pregunta']}")
            lineas.append(f"  SQL: {e['consulta_sql']}")
            lineas.append("")

    return "\n".join(lineas)


# ------------------------------------------------------------
# Resolución
# ------------------------------------------------------------
def resolver_entidad(texto):
    if not texto:
        return None
    n = normalizar(texto)

    alias = ejecutar_select("SELECT alias, id_entidad FROM dim_entidad_alias")

    for fila in alias:
        if normalizar(fila["alias"]) == n:
            return fila["id_entidad"]

    canon = ejecutar_select(
        "SELECT id_entidad, nombre_canonico FROM dim_entidad"
    )
    for fila in canon:
        if normalizar(fila["nombre_canonico"]) == n:
            return fila["id_entidad"]

    for fila in alias:
        a = normalizar(fila["alias"])
        if a and re.search(rf"\b{re.escape(a)}\b", n):
            return fila["id_entidad"]

    for fila in canon:
        c = normalizar(fila["nombre_canonico"])
        if c and re.search(rf"\b{re.escape(c)}\b", n):
            return fila["id_entidad"]

    return None


def nombre_entidad(id_entidad):
    if id_entidad is None:
        return None
    filas = ejecutar_select(
        "SELECT nombre_canonico FROM dim_entidad WHERE id_entidad = %s"
        % int(id_entidad)
    )
    return filas[0]["nombre_canonico"] if filas else None


def resolver_fuente(texto):
    if not texto:
        return None
    n = normalizar(texto)

    filas = ejecutar_select("SELECT id_fuente, codigo, nombre FROM fuentes")

    for fila in filas:
        if normalizar(fila["codigo"]) == n or normalizar(fila["nombre"]) == n:
            return fila["codigo"]

    for fila in filas:
        if not fila["codigo"]:
            continue
        for candidato in (fila["codigo"], fila["nombre"]):
            c = normalizar(candidato)
            if c and re.search(rf"\b{re.escape(c)}\b", n):
                return fila["codigo"]

    catalogo = cargar_catalogo()
    for s in catalogo["sinonimos"]:
        if s["tipo_destino"] != "fuente":
            continue
        t = normalizar(s["termino"])
        if t and re.search(rf"\b{re.escape(t)}\b", n):
            return s["id_destino"]

    return None


def resolver_metrica(texto):
    if not texto:
        return None
    n = normalizar(texto)
    catalogo = cargar_catalogo()
    for m in catalogo["metricas"]:
        sinonimos = normalizar(m["sinonimos"] or "")
        terminos = [normalizar(t) for t in re.split(r"[,\n]", sinonimos)]
        if n == normalizar(m["nombre"]) or n in terminos:
            return m["nombre"]
    for m in catalogo["metricas"]:
        for t in re.split(r"[,\n]", normalizar(m["sinonimos"] or "")):
            if t.strip() and t.strip() in n:
                return m["nombre"]
    return None


def resolver_indicador(texto):
    if not texto:
        return None
    n = normalizar(texto)
    if len(n) < 4:
        return None

    filas = ejecutar_select(
        "SELECT id_indicador, alias FROM dim_indicador_alias"
    )
    for fila in filas:
        if normalizar(fila["alias"]) == n:
            return fila["id_indicador"]

    filas = ejecutar_select(
        "SELECT id_indicador, nombre FROM dim_indicador"
    )
    for fila in filas:
        if n in normalizar(fila["nombre"]):
            return fila["id_indicador"]

    return None


# ------------------------------------------------------------
# Accesos directos
# ------------------------------------------------------------
def metricas_disponibles():
    return cargar_catalogo()["metricas"]


def reglas_sql():
    return cargar_catalogo()["reglas_sql"]


def reglas_respuesta():
    return cargar_catalogo()["reglas_respuesta"]


def reglas_explicacion():
    return cargar_catalogo()["reglas_explicacion"]


def tipos_violencia():
    try:
        return [
            f["nombre"]
            for f in ejecutar_select(
                "SELECT nombre FROM tipos_violencia ORDER BY id_tipo_violencia"
            )
        ]
    except Exception:
        return []


def resolver_tipo_violencia(texto):
    n = normalizar(texto)
    if not n:
        return None
    for nombre in tipos_violencia():
        objetivo = normalizar(nombre)
        if objetivo and (n == objetivo or objetivo in n or n in objetivo):
            return nombre
    return None


def glosario():
    try:
        return ejecutar_select(
            "SELECT termino, definicion, categoria, sinonimos FROM glosario",
            database="mhub_meta",
        )
    except Exception:
        return []


def ayuda_datos():
    """Datos reales de la BD para generar la ayuda dinámica."""
    try:
        fuentes = ejecutar_select(
            "SELECT codigo, nombre FROM fuentes WHERE codigo IS NOT NULL "
            "ORDER BY id_fuente"
        )
        rango = ejecutar_select(
            "SELECT MIN(anio) AS minimo, MAX(anio) AS maximo FROM dim_tiempo "
            "WHERE tipo_tiempo = 'dato' AND anio IS NOT NULL"
        )[0]
        entidades = ejecutar_select(
            "SELECT COUNT(*) AS c FROM dim_entidad WHERE nivel = 'estado'"
        )[0]["c"]
        indicadores = ejecutar_select(
            "SELECT nombre FROM dim_indicador ORDER BY RAND() LIMIT 3"
        )
        return {
            "fuentes": [f["codigo"] for f in fuentes],
            "anio_min": rango["minimo"],
            "anio_max": rango["maximo"],
            "entidades": entidades,
            "indicadores": [i["nombre"] for i in indicadores],
        }
    except Exception:
        return {}


def ejemplos_nl_sql():
    return cargar_catalogo()["ejemplos"]


if __name__ == "__main__":
    cargar_catalogo(forzar=True)
    print(contexto_prompt()[:1500])
