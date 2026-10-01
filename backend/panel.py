"""Panel manual de MHub (Fase 11).

Construye los bloques de un dashboard a partir de filtros (fuente, entidad,
año, tipo de violencia, delito) usando el esquema en estrella. Todo con datos
reales; nunca se inventan cifras.
"""
from database import ejecutar_select

FUENTES = ["ENDIREH", "SIESVIM", "INMUJERES", "SESNSP", "X"]
FUENTES_INDICADOR = ("ENDIREH", "SIESVIM")
UNIDAD_POR_FUENTE = {
    "ENDIREH": "porcentaje", "SIESVIM": "porcentaje",
    "INMUJERES": "conteo", "SESNSP": "conteo", "X": "publicaciones",
}


def _f(valor):
    try:
        return round(float(valor), 2)
    except (TypeError, ValueError):
        return None


def _fid(fuente):
    filas = ejecutar_select("SELECT id_fuente FROM fuentes WHERE codigo = %s", params=(fuente,))
    return filas[0]["id_fuente"] if filas else None


# ------------------------------------------------------------
# Catálogo de filtros
# ------------------------------------------------------------
def filtros():
    salida = {"fuentes": FUENTES, "por_fuente": {}}

    for fuente in FUENTES:
        fid = _fid(fuente)
        info = {"nacional": fuente in ("INMUJERES", "SESNSP"), "unidad": UNIDAD_POR_FUENTE[fuente]}

        if fuente == "X":
            anios = [f["anio"] for f in ejecutar_select(
                "SELECT DISTINCT t.anio AS anio FROM fact_publicacion p "
                "JOIN dim_tiempo t ON t.id_tiempo = p.id_tiempo_pub "
                "WHERE t.anio IS NOT NULL ORDER BY t.anio"
            )]
            ents = [f["entidad"] for f in ejecutar_select(
                "SELECT DISTINCT e.nombre_canonico AS entidad FROM fact_publicacion p "
                "JOIN dim_entidad e ON e.id_entidad = p.id_entidad "
                "WHERE e.nivel = 'estado' ORDER BY e.nombre_canonico"
            )]
            tipos = [f["nombre"] for f in ejecutar_select(
                "SELECT DISTINCT tv.nombre FROM fact_publicacion p "
                "JOIN bridge_pub_tipo_violencia b ON b.id_publicacion = p.id_publicacion "
                "JOIN tipos_violencia tv ON tv.id_tipo_violencia = b.id_tipo_violencia"
            )]
            info.update(anios=anios, entidades=ents, tipos=tipos, delitos=[])
        else:
            anios = [f["anio"] for f in ejecutar_select(
                "SELECT DISTINCT t.anio AS anio FROM fact_indicador f "
                "JOIN dim_tiempo t ON t.id_tiempo = f.id_tiempo "
                "WHERE f.id_fuente = %s AND t.anio IS NOT NULL ORDER BY t.anio",
                params=(fid,),
            )]
            ents = [] if fuente in ("INMUJERES", "SESNSP") else [
                f["entidad"] for f in ejecutar_select(
                    "SELECT DISTINCT e.nombre_canonico AS entidad FROM fact_indicador f "
                    "JOIN dim_entidad e ON e.id_entidad = f.id_entidad "
                    "WHERE f.id_fuente = %s AND e.nivel = 'estado' ORDER BY e.nombre_canonico",
                    params=(fid,),
                )
            ]
            tipos = [f["nombre"] for f in ejecutar_select(
                "SELECT DISTINCT tv.nombre FROM fact_indicador f "
                "JOIN bridge_indicador_tipo_violencia b ON b.id_indicador = f.id_indicador "
                "JOIN tipos_violencia tv ON tv.id_tipo_violencia = b.id_tipo_violencia "
                "WHERE f.id_fuente = %s",
                params=(fid,),
            )]
            delitos = []
            if fuente == "SESNSP":
                delitos = [f["nombre"] for f in ejecutar_select(
                    "SELECT nombre FROM dim_indicador WHERE id_fuente = %s ORDER BY nombre",
                    params=(fid,),
                )]
            info.update(anios=anios, entidades=ents, tipos=tipos, delitos=delitos)

        salida["por_fuente"][fuente] = info

    return salida


# ------------------------------------------------------------
# Helpers de bloques
# ------------------------------------------------------------
def _bloque(tipo, titulo, filas, unidad=None, limite=None):
    filas = [f for f in filas if f["v"] is not None]
    if limite:
        filas = filas[:limite]
    if not filas:
        return None
    return {
        "tipo": tipo,
        "titulo": titulo,
        "unidad": unidad,
        "valores": [{"etiqueta": str(f["e"]), "valor": _f(f["v"])} for f in filas],
    }


def _panel_indicadores(fuente, entidad, anio, tipo):
    fid = _fid(fuente)

    def base(con_entidad=True, con_tipo=True, anio_fijo=False):
        cond = ["f.id_fuente = %s", "t.tipo_tiempo = 'dato'"]
        params = [fid]
        if con_entidad and entidad:
            cond.append("e.nombre_canonico = %s")
            params.append(entidad)
        if con_tipo and tipo:
            cond.append(
                "EXISTS (SELECT 1 FROM bridge_indicador_tipo_violencia b "
                "JOIN tipos_violencia tv ON tv.id_tipo_violencia = b.id_tipo_violencia "
                "WHERE b.id_indicador = i.id_indicador AND tv.nombre = %s)"
            )
            params.append(tipo)
        if anio_fijo and anio:
            cond.append("t.anio = %s")
            params.append(anio)
        return (
            "FROM fact_indicador f JOIN dim_indicador i ON i.id_indicador = f.id_indicador "
            "JOIN dim_entidad e ON e.id_entidad = f.id_entidad "
            "JOIN dim_tiempo t ON t.id_tiempo = f.id_tiempo "
            "WHERE " + " AND ".join(cond),
            params,
        )

    s_sql, s_p = base()
    serie = ejecutar_select(
        f"SELECT t.anio AS e, AVG(f.valor) AS v {s_sql} GROUP BY t.anio ORDER BY t.anio",
        params=s_p,
    )

    r_sql, r_p = base(con_entidad=False, anio_fijo=True)
    ranking = ejecutar_select(
        f"SELECT e.nombre_canonico AS e, AVG(f.valor) AS v {r_sql} "
        "AND e.nivel = 'estado' GROUP BY e.nombre_canonico ORDER BY v DESC LIMIT 12",
        params=r_p,
    )

    tc = ["f.id_fuente = %s", "t.tipo_tiempo = 'dato'"]
    tp = [fid]
    if entidad:
        tc.append("e.nombre_canonico = %s")
        tp.append(entidad)
    if anio:
        tc.append("t.anio = %s")
        tp.append(anio)
    tipos = ejecutar_select(
        "SELECT tv.nombre AS e, AVG(f.valor) AS v "
        "FROM fact_indicador f JOIN dim_indicador i ON i.id_indicador = f.id_indicador "
        "JOIN dim_entidad e ON e.id_entidad = f.id_entidad "
        "JOIN dim_tiempo t ON t.id_tiempo = f.id_tiempo "
        "JOIN bridge_indicador_tipo_violencia b ON b.id_indicador = i.id_indicador "
        "JOIN tipos_violencia tv ON tv.id_tipo_violencia = b.id_tipo_violencia "
        "WHERE " + " AND ".join(tc) + " GROUP BY tv.nombre ORDER BY v DESC",
        params=tp,
    )

    return serie, ranking, tipos


def _panel_x(entidad, anio, tipo):
    cond = ["p.es_basura = 'no'"]
    params = []
    if entidad:
        cond.append("e.nombre_canonico = %s")
        params.append(entidad)
    if tipo:
        cond.append(
            "EXISTS (SELECT 1 FROM bridge_pub_tipo_violencia b "
            "JOIN tipos_violencia tv ON tv.id_tipo_violencia = b.id_tipo_violencia "
            "WHERE b.id_publicacion = p.id_publicacion AND tv.nombre = %s)"
        )
        params.append(tipo)
    base = (
        "FROM fact_publicacion p JOIN dim_entidad e ON e.id_entidad = p.id_entidad "
        "JOIN dim_tiempo t ON t.id_tiempo = p.id_tiempo_pub WHERE " + " AND ".join(cond)
    )
    serie = ejecutar_select(
        f"SELECT t.anio AS e, COUNT(*) AS v {base} GROUP BY t.anio ORDER BY t.anio",
        params=params,
    )
    ranking = ejecutar_select(
        f"SELECT e.nombre_canonico AS e, COUNT(*) AS v {base} "
        "AND e.nivel = 'estado' GROUP BY e.nombre_canonico ORDER BY v DESC LIMIT 12",
        params=params,
    )
    return serie, ranking


def _panel_nacional(fuente, anio, delito):
    fid = _fid(fuente)
    cond = ["f.id_fuente = %s", "t.tipo_tiempo = 'dato'"]
    params = [fid]
    if delito:
        cond.append("i.nombre = %s")
        params.append(delito)
    base = (
        "FROM fact_indicador f JOIN dim_indicador i ON i.id_indicador = f.id_indicador "
        "JOIN dim_tiempo t ON t.id_tiempo = f.id_tiempo WHERE " + " AND ".join(cond)
    )
    serie = ejecutar_select(
        f"SELECT t.anio AS e, SUM(f.valor) AS v {base} GROUP BY t.anio ORDER BY t.anio",
        params=params,
    )

    cond_r = ["f.id_fuente = %s"]
    params_r = [fid]
    if anio:
        cond_r.append("t.anio = %s")
        params_r.append(anio)
    base_r = (
        "FROM fact_indicador f JOIN dim_indicador i ON i.id_indicador = f.id_indicador "
        "JOIN dim_tiempo t ON t.id_tiempo = f.id_tiempo WHERE " + " AND ".join(cond_r)
    )
    ranking = ejecutar_select(
        f"SELECT i.nombre AS e, MAX(f.valor) AS v {base_r} "
        "GROUP BY i.nombre ORDER BY v DESC LIMIT 12",
        params=params_r,
    )
    return serie, ranking


# ------------------------------------------------------------
# Constructor principal
# ------------------------------------------------------------
def construir(fuente, entidad=None, anio=None, tipo=None, delito=None):
    if fuente not in FUENTES:
        return None

    fuente = fuente.upper()
    entidad = entidad or None
    tipo = tipo or None
    delito = delito or None
    try:
        anio = int(anio) if anio not in (None, "", "todos") else None
    except (TypeError, ValueError):
        anio = None

    unidad = UNIDAD_POR_FUENTE[fuente]
    bloques = []
    kpis = []
    texto = ""

    if fuente in FUENTES_INDICADOR:
        serie, ranking, tipos = _panel_indicadores(fuente, entidad, anio, tipo)
        etiqueta = tipo and f"violencia {tipo}" or "indicadores"
        bloques.append(_bloque("linea", f"Evolución por año · {etiqueta}", serie, unidad))
        bloques.append(_bloque("barra_horizontal", f"Entidades con mayor {etiqueta}" + (f" ({anio})" if anio else ""), ranking, unidad))
        bloques.append(_bloque("dona", f"Por tipo de violencia" + (f" ({anio})" if anio else ""), tipos, unidad))

        valores_serie = [f for f in serie if f["v"] is not None]
        if valores_serie:
            pico = max(valores_serie, key=lambda x: x["v"])
            kpis.append({"label": "Año con el valor más alto", "valor": str(pico["e"]), "detalle": f"{_f(pico['v'])} {unidad}"})
            if anio:
                actual = [f for f in valores_serie if f["e"] == anio]
                if actual:
                    kpis.append({"label": f"Promedio {anio}", "valor": f"{_f(actual[0]['v'])}", "detalle": unidad})
        if ranking:
            kpis.append({"label": "Entidad más alta" + (f" ({anio})" if anio else ""), "valor": str(ranking[0]["e"]), "detalle": f"{_f(ranking[0]['v'])} {unidad}"})
            kpis.append({"label": "Entidad más baja" + (f" ({anio})" if anio else ""), "valor": str(ranking[-1]["e"]), "detalle": f"{_f(ranking[-1]['v'])} {unidad}"})

        alcance = f"en {entidad}" if entidad else "a nivel nacional (todas las entidades)"
        texto = (
            f"Serie de {etiqueta} para {fuente} {alcance}. "
            + (f"En {anio}, la entidad con el valor más alto fue {ranking[0]['e']} ({_f(ranking[0]['v'])} {unidad}). " if ranking and anio else "")
            + "Cada valor es un porcentaje (proporción). Los indicadores distintos no son comparables entre sí."
        )

    elif fuente == "X":
        serie, ranking = _panel_x(entidad, anio, tipo)
        etiqueta = tipo and f"publicaciones de {tipo}" or "publicaciones de X"
        bloques.append(_bloque("linea", "Publicaciones por año", serie, "publicaciones"))
        bloques.append(_bloque("barra_horizontal", "Publicaciones por entidad", ranking, "publicaciones"))
        valores = [f for f in serie if f["v"] is not None]
        total = sum(f["v"] for f in valores)
        kpis.append({"label": "Total de publicaciones", "valor": f"{int(total):,}", "detalle": "sin contar basura"})
        if valores:
            pico = max(valores, key=lambda x: x["v"])
            kpis.append({"label": "Año con más publicaciones", "valor": str(pico["e"]), "detalle": f"{int(pico['v']):,}"})
        if ranking:
            kpis.append({"label": "Entidad con más publicaciones", "valor": str(ranking[0]["e"]), "detalle": f"{int(ranking[0]['v']):,}"})
        texto = (
            "Publicaciones de X (no son casos ni estadística oficial). "
            "Reflejan lo que se publica en la red social, con subregistro y sesgos."
        )

    else:  # INMUJERES / SESNSP
        serie, ranking = _panel_nacional(fuente, anio, delito)
        etiqueta = delito or ("delitos e incidentes" if fuente == "SESNSP" else "indicadores")
        bloques.append(_bloque("linea", f"Evolución por año · {etiqueta}", serie, unidad))
        bloques.append(_bloque("barra_horizontal", f"Mayores valores" + (f" ({anio})" if anio else ""), ranking, unidad))
        valores = [f for f in serie if f["v"] is not None]
        if valores:
            pico = max(valores, key=lambda x: x["v"])
            kpis.append({"label": "Año con el valor más alto", "valor": str(pico["e"]), "detalle": f"{_f(pico['v'])} {unidad}"})
            if anio:
                actual = [f for f in valores if f["e"] == anio]
                if actual:
                    kpis.append({"label": f"Total {anio}", "valor": f"{_f(actual[0]['v'])}", "detalle": unidad})
        if fuente == "SESNSP":
            texto = (
                "Datos de incidencia delictiva y llamadas de emergencia del SESNSP. "
                "Son conteos nacionales: las llamadas 911 no equivalen a denuncias."
            )
        else:
            texto = "Conteos nacionales de INMUJERES (no son porcentajes)."

    bloques = [b for b in bloques if b]
    return {
        "fuente": fuente,
        "filtros": {"entidad": entidad, "anio": anio, "tipo": tipo, "delito": delito},
        "unidad": unidad,
        "kpis": kpis,
        "bloques": bloques,
        "texto": texto,
    }
