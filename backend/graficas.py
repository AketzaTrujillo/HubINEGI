"""Especificaciones de gráfica (Fase 9).

El LLM/backend no dibuja: produce una spec y el frontend la renderiza.
"""
from decimal import Decimal

PLOTABLES = {"por_anio", "por_entidad", "por_tipo_violencia", "comparar"}


def _f(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _titulo(spec):
    partes = []
    if spec.get("_nombre_indicador"):
        nombre = spec["_nombre_indicador"]
        partes.append(nombre[:70] + ("…" if len(nombre) > 70 else ""))
    elif spec.get("tipo_violencia"):
        partes.append(f"violencia {spec['tipo_violencia']}")
    elif spec.get("fuente"):
        partes.append(spec["fuente"])
    if spec.get("entidad") and spec.get("entidad_b"):
        partes.append(f"{spec['entidad']} vs {spec['entidad_b']}")
    elif spec.get("entidad"):
        partes.append(spec["entidad"])
    if spec.get("anio"):
        partes.append(str(spec["anio"]))
    if spec.get("operacion") == "por_anio":
        partes.append("por año")
    elif spec.get("operacion") in ("por_entidad", "comparar"):
        partes.append("por entidad")
    return " · ".join(partes) if partes else "Datos de MHub"


def construir_grafica(spec, resultados):
    if not resultados:
        return None

    operacion = spec.get("operacion")
    if operacion not in PLOTABLES:
        return None

    if operacion == "por_anio":
        clave, eje, tipo = "anio", "Año", "linea"
    elif operacion == "por_tipo_violencia":
        clave, eje, tipo = "tipo_violencia", "Tipo de violencia", "dona"
    elif operacion == "comparar":
        clave, eje, tipo = "entidad", "Entidad", "barra"
    else:
        clave, eje, tipo = "entidad", "Entidad", "barra_horizontal"

    valor_clave = "promedio" if "promedio" in resultados[0] else "total"

    # Para por_tipo_violencia, preferir porcentaje si existe (unidades distintas).
    filas = resultados
    if operacion == "por_tipo_violencia":
        porcentaje = [f for f in resultados if f.get("unidad") == "porcentaje"]
        if porcentaje:
            filas = porcentaje

    valores = []
    unidad = None
    for fila in filas:
        valor = _f(fila.get(valor_clave))
        etiqueta = fila.get(clave)
        if valor is None or etiqueta is None:
            continue
        valores.append({"etiqueta": str(etiqueta), "valor": round(valor, 2)})
        if fila.get("unidad"):
            unidad = fila["unidad"]

    if not valores:
        return None

    return {
        "tipo": tipo,
        "titulo": _titulo(spec),
        "eje_x": eje,
        "unidad": unidad,
        "valores": valores[:30],
    }
