"""Genera SQL determinista desde una spec (Fase 4).

Solo SELECT, solo tablas del catálogo, filtros parametrizados.
Soporta indicadores (fact_indicador) y publicaciones de X (fact_publicacion).
"""
from query_spec import validar_spec

TABLAS_INDICADOR = """
FROM fact_indicador f
JOIN dim_indicador i ON i.id_indicador = f.id_indicador
JOIN dim_entidad   e ON e.id_entidad   = f.id_entidad
JOIN dim_tiempo    t ON t.id_tiempo    = f.id_tiempo
JOIN dim_unidad    u ON u.id_unidad    = f.id_unidad
JOIN fuentes       fu ON fu.id_fuente  = f.id_fuente
"""

TABLAS_PUBLICACION = """
FROM fact_publicacion p
JOIN dim_entidad e ON e.id_entidad = p.id_entidad
JOIN dim_tiempo  t ON t.id_tiempo  = p.id_tiempo_pub
"""


def _where_indicador(spec):
    condiciones = ["t.tipo_tiempo = 'dato'"]
    params = []
    if spec.get("fuente"):
        condiciones.append("fu.codigo = %s")
        params.append(spec["fuente"])
    if spec.get("entidad"):
        condiciones.append("e.nombre_canonico = %s")
        params.append(spec["entidad"])
    if spec.get("anio"):
        condiciones.append("t.anio = %s")
        params.append(spec["anio"])
    if spec.get("tipo_violencia"):
        condiciones.append(
            "EXISTS (SELECT 1 FROM bridge_indicador_tipo_violencia b "
            "WHERE b.id_indicador = i.id_indicador AND b.id_tipo_violencia = "
            "(SELECT id_tipo_violencia FROM tipos_violencia WHERE nombre = %s))"
        )
        params.append(spec["tipo_violencia"])
    if spec.get("_id_indicador"):
        condiciones.append("i.id_indicador = %s")
        params.append(spec["_id_indicador"])
    if spec.get("filtro_texto"):
        condiciones.append("i.nombre LIKE %s")
        params.append(f"%{spec['filtro_texto']}%")
    return " WHERE " + " AND ".join(condiciones), params


def _where_publicacion(spec):
    condiciones = ["p.es_basura = 'no'"]
    params = []
    if spec.get("entidad"):
        condiciones.append("e.nombre_canonico = %s")
        params.append(spec["entidad"])
    if spec.get("anio"):
        condiciones.append("t.anio = %s")
        params.append(spec["anio"])
    if spec.get("tipo_violencia"):
        condiciones.append(
            "EXISTS (SELECT 1 FROM bridge_pub_tipo_violencia b "
            "WHERE b.id_publicacion = p.id_publicacion AND b.id_tipo_violencia = "
            "(SELECT id_tipo_violencia FROM tipos_violencia WHERE nombre = %s))"
        )
        params.append(spec["tipo_violencia"])
    return " WHERE " + " AND ".join(condiciones), params


def _sql_indicador(spec):
    where, params = _where_indicador(spec)
    operacion = spec["operacion"]
    metrica = spec.get("metrica")
    limite = spec["limite"]

    cols = (
        "i.nombre AS indicador, e.nombre_canonico AS entidad, "
        "t.anio AS anio, f.valor AS valor, u.nombre AS unidad, "
        "fu.codigo AS fuente"
    )

    if operacion == "conteo":
        return f"SELECT COUNT(*) AS total {TABLAS_INDICADOR}{where}", params

    if operacion == "promedio":
        sql = (
            f"SELECT AVG(f.valor) AS promedio, u.nombre AS unidad, "
            f"COUNT(*) AS registros {TABLAS_INDICADOR}{where} "
            f"GROUP BY u.nombre ORDER BY promedio DESC"
        )
        return sql, params

    if operacion == "suma":
        sql = (
            f"SELECT SUM(f.valor) AS total, u.nombre AS unidad "
            f"{TABLAS_INDICADOR}{where} GROUP BY u.nombre"
        )
        return sql, params

    if operacion == "maximo":
        return (
            f"SELECT {cols} {TABLAS_INDICADOR}{where} "
            f"ORDER BY f.valor DESC LIMIT 1"
        ), params

    if operacion == "minimo":
        return (
            f"SELECT {cols} {TABLAS_INDICADOR}{where} "
            f"ORDER BY f.valor ASC LIMIT 1"
        ), params

    if operacion == "top_n":
        direccion = "DESC" if spec.get("orden", "desc") == "desc" else "ASC"
        return (
            f"SELECT {cols} {TABLAS_INDICADOR}{where} "
            f"ORDER BY f.valor {direccion} LIMIT {int(limite)}"
        ), params

    if operacion == "por_anio":
        agregado = "COUNT(*)" if metrica == "conteo" else "AVG(f.valor)"
        alias = "total" if metrica == "conteo" else "promedio"
        return (
            f"SELECT t.anio AS anio, {agregado} AS {alias}, "
            "GROUP_CONCAT(DISTINCT fu.codigo ORDER BY fu.codigo) AS fuentes "
            f"{TABLAS_INDICADOR}{where} "
            f"GROUP BY t.anio ORDER BY t.anio"
        ), params

    if operacion == "por_entidad":
        agregado = "COUNT(*)" if metrica == "conteo" else "AVG(f.valor)"
        alias = "total" if metrica == "conteo" else "promedio"
        return (
            f"SELECT e.nombre_canonico AS entidad, {agregado} AS {alias}, "
            "MAX(i.nombre) AS indicador, MAX(t.anio) AS anio, "
            "MAX(u.nombre) AS unidad, "
            "GROUP_CONCAT(DISTINCT fu.codigo ORDER BY fu.codigo) AS fuentes "
            f"{TABLAS_INDICADOR}{where} AND e.nivel = 'estado' "
            f"GROUP BY e.nombre_canonico ORDER BY {alias} DESC LIMIT {int(limite)}"
        ), params

    if operacion == "anios_disponibles":
        return (
            f"SELECT DISTINCT t.anio AS anio {TABLAS_INDICADOR}{where} "
            "AND t.anio IS NOT NULL ORDER BY t.anio"
        ), params

    if operacion == "por_tipo_violencia":
        agregado = "COUNT(*)" if metrica == "conteo" else "AVG(f.valor)"
        alias = "total" if metrica == "conteo" else "promedio"
        return (
            f"SELECT tv.nombre AS tipo_violencia, u.nombre AS unidad, "
            f"{agregado} AS {alias}, COUNT(*) AS registros, "
            "GROUP_CONCAT(DISTINCT fu.codigo ORDER BY fu.codigo) AS fuentes "
            f"{TABLAS_INDICADOR} "
            "JOIN bridge_indicador_tipo_violencia b ON b.id_indicador = i.id_indicador "
            "JOIN tipos_violencia tv ON tv.id_tipo_violencia = b.id_tipo_violencia "
            f"{where} GROUP BY tv.nombre, u.nombre ORDER BY {alias} DESC"
        ), params

    if operacion == "comparar":
        entidades = [
            e for e in (spec.get("entidad"), spec.get("entidad_b")) if e
        ]
        condiciones = ["t.tipo_tiempo = 'dato'"]
        params = []
        if spec.get("fuente"):
            condiciones.append("fu.codigo = %s")
            params.append(spec["fuente"])
        if spec.get("anio"):
            condiciones.append("t.anio = %s")
            params.append(spec["anio"])
        if entidades:
            marcadores = ", ".join(["%s"] * len(entidades))
            condiciones.append(f"e.nombre_canonico IN ({marcadores})")
            params.extend(entidades)
        agregado = "COUNT(*)" if metrica == "conteo" else "AVG(f.valor)"
        alias = "total" if metrica == "conteo" else "promedio"
        return (
            f"SELECT e.nombre_canonico AS entidad, {agregado} AS {alias}, "
            "u.nombre AS unidad, GROUP_CONCAT(DISTINCT fu.codigo ORDER BY fu.codigo) AS fuentes "
            f"{TABLAS_INDICADOR} WHERE {' AND '.join(condiciones)} "
            "GROUP BY e.nombre_canonico, u.nombre ORDER BY e.nombre_canonico"
        ), params

    # detalle por defecto
    return (
        f"SELECT {cols} {TABLAS_INDICADOR}{where} "
        f"ORDER BY t.anio DESC, e.nombre_canonico LIMIT {int(limite)}"
    ), params


def _sql_publicacion(spec):
    where, params = _where_publicacion(spec)
    operacion = spec["operacion"]
    limite = spec["limite"]

    if operacion in ("conteo", "promedio", "suma", "maximo", "minimo", "top_n"):
        return f"SELECT COUNT(*) AS total {TABLAS_PUBLICACION}{where}", params

    if operacion == "por_anio":
        return (
            f"SELECT t.anio AS anio, COUNT(*) AS total "
            f"{TABLAS_PUBLICACION}{where} GROUP BY t.anio ORDER BY t.anio"
        ), params

    if operacion == "por_entidad":
        return (
            f"SELECT e.nombre_canonico AS entidad, COUNT(*) AS total "
            f"{TABLAS_PUBLICACION}{where} AND e.nivel = 'estado' "
            f"GROUP BY e.nombre_canonico ORDER BY total DESC LIMIT {int(limite)}"
        ), params

    if operacion == "anios_disponibles":
        return (
            f"SELECT DISTINCT t.anio AS anio {TABLAS_PUBLICACION}{where} "
            "AND t.anio IS NOT NULL ORDER BY t.anio"
        ), params

    if operacion == "por_tipo_violencia":
        return (
            "SELECT tv.nombre AS tipo_violencia, COUNT(*) AS total "
            "FROM fact_publicacion p "
            "JOIN dim_entidad e ON e.id_entidad = p.id_entidad "
            "JOIN dim_tiempo  t ON t.id_tiempo  = p.id_tiempo_pub "
            "JOIN bridge_pub_tipo_violencia b ON b.id_publicacion = p.id_publicacion "
            "JOIN tipos_violencia tv ON tv.id_tipo_violencia = b.id_tipo_violencia "
            f"{where} GROUP BY tv.nombre ORDER BY total DESC"
        ), params

    return (
        "SELECT p.texto_limpio AS publicacion, e.nombre_canonico AS entidad, "
        "t.anio AS anio, p.nivel_confianza AS confianza "
        f"{TABLAS_PUBLICACION}{where} "
        f"ORDER BY p.nivel_confianza DESC LIMIT {int(limite)}"
    ), params


def construir_sql(spec):
    valido, error = validar_spec(spec)
    if not valido:
        raise ValueError(error)

    if spec.get("fuente") == "X":
        return _sql_publicacion(spec)
    return _sql_indicador(spec)


if __name__ == "__main__":
    ejemplos = [
        {"operacion": "promedio", "fuente": "ENDIREH", "entidad": "Jalisco", "anio": 2021, "grupo": [], "limite": 100},
        {"operacion": "maximo", "fuente": "SIESVIM", "entidad": None, "anio": 2021, "grupo": [], "limite": 1},
        {"operacion": "conteo", "fuente": "X", "entidad": "Jalisco", "anio": None, "grupo": [], "limite": 100},
        {"operacion": "por_anio", "fuente": "X", "entidad": "Jalisco", "anio": None, "grupo": ["anio"], "limite": 100},
        {"operacion": "detalle", "fuente": None, "entidad": "Puebla", "anio": None, "grupo": [], "limite": 100},
    ]
    for e in ejemplos:
        sql, params = construir_sql(e)
        print(sql.strip())
        print("  params:", params, "\n")
