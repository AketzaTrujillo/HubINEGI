"""Pruebas de humo del clasificador de criticidad (objetivo 7).

No requiere el modelo entrenado: valida las funciones de limpieza, el filtro de
seguridad y la regla de respaldo. Para métricas del modelo usa
`evaluar_clasificador.py`.

Uso:
    cd tests
    python run_clasificador.py
"""

from __future__ import annotations

import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "ingestion", "X"))

import clasificador_dl as dl  # noqa: E402

CASOS = [
    ("texto_util imagen", dl.texto_util("image"), False),
    ("texto_util vacío", dl.texto_util(""), False),
    (
        "texto_util noticia",
        dl.texto_util("detienen a un hombre por violencia familiar en Jalisco"),
        True,
    ),
    (
        "filtro crimen organizado",
        dl.es_violencia_de_genero("el cartel cjng desató una ola de violencia"),
        False,
    ),
    (
        "filtro género",
        dl.es_violencia_de_genero("una mujer fue asesinada por su pareja"),
        True,
    ),
    (
        "regla noticia",
        dl.regla_critica("detienen a un hombre por violencia familiar", "noticia"),
        1,
    ),
    (
        "regla otro",
        dl.regla_critica("campaña de prevención", "institucional"),
        0,
    ),
]


def main() -> None:
    fallas = 0
    for nombre, obtenido, esperado in CASOS:
        ok = obtenido == esperado
        print(f"[{'OK' if ok else 'FALLA'}] {nombre}: {obtenido!r} (esperado {esperado!r})")
        if not ok:
            fallas += 1

    print("\n" + "=" * 60)
    print(f"Clasificador (humo): {len(CASOS) - fallas}/{len(CASOS)}")
    if fallas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
