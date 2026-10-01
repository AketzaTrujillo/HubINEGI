"""Catálogos consultables de MHub (Fase 9).

Responden preguntas del tipo "¿cuántos tipos de violencia existen?" desde el
catálogo, no desde los hechos.
"""
from database import ejecutar_select
import semantic_loader


def _fuentes():
    return [
        f["codigo"]
        for f in ejecutar_select(
            "SELECT codigo FROM fuentes WHERE codigo IS NOT NULL ORDER BY id_fuente"
        )
    ]


def _entidades():
    return [
        f["nombre_canonico"]
        for f in ejecutar_select(
            "SELECT nombre_canonico FROM dim_entidad WHERE nivel = 'estado' "
            "ORDER BY nombre_canonico"
        )
    ]


def _indicadores():
    return [
        f["nombre"]
        for f in ejecutar_select(
            "SELECT nombre FROM dim_indicador ORDER BY id_indicador LIMIT 25"
        )
    ]


def _unidades():
    return [
        f["nombre"]
        for f in ejecutar_select("SELECT nombre FROM dim_unidad ORDER BY id_unidad")
    ]


def listar(recurso):
    if recurso == "tipos_violencia":
        return semantic_loader.tipos_violencia()
    if recurso == "fuentes":
        return _fuentes()
    if recurso == "entidades":
        return _entidades()
    if recurso == "indicadores":
        return _indicadores()
    if recurso == "unidades":
        return _unidades()
    return []


def _lista(items, limite=12):
    if len(items) <= limite:
        return ", ".join(items)
    return ", ".join(items[:limite]) + f", … (y {len(items) - limite} más)"


def responder(recurso):
    items = listar(recurso)

    if not items:
        return "No tengo ese catálogo disponible."

    if recurso == "tipos_violencia":
        return (
            f"En MHub se manejan {len(items)} tipos de violencia: "
            f"{_lista(items)}."
        )

    if recurso == "fuentes":
        return (
            f"MHub usa {len(items)} fuentes: {_lista(items)}. "
            "ENDIREH y SIESVIM son del INEGI, INMUJERES es oficial, y X son "
            "publicaciones (no estadística oficial)."
        )

    if recurso == "entidades":
        return (
            f"Tengo datos de {len(items)} entidades federativas: {_lista(items, limite=100)}."
        )

    if recurso == "indicadores":
        return (
            f"Estos son algunos de los indicadores disponibles ({len(items)} en "
            f"total en esta muestra): {_lista(items, limite=6)}."
        )

    if recurso == "unidades":
        return f"Las unidades de medida disponibles son: {_lista(items)}."

    return "No tengo ese catálogo disponible."
