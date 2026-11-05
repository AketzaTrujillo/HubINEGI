"""Validación funcional de las tareas de usabilidad (objetivo 9).

Comprueba que las 5 tareas del protocolo producen una respuesta que contiene
los elementos esperados. **No sustituye** las pruebas con personas: solo
verifica que los flujos del sistema funcionan de extremo a extremo.

Uso:
    cd tests/usabilidad
    python validar_tareas_funcional.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

from consulta_mhub import responder  # noqa: E402

TAREAS = [
    {
        "id": "T1",
        "pregunta": "promedio de ENDIREH para Jalisco en 2021",
        "grupos": [["37.58", "endireh"], ["jalisco"]],
    },
    {
        "id": "T2",
        "pregunta": "compara la violencia de pareja entre Jalisco y Puebla en 2021",
        "grupos": [["jalisco"], ["puebla"]],
    },
    {
        "id": "T3",
        "pregunta": "publicaciones críticas de Jalisco",
        "grupos": [["critica", "criticas"], ["jalisco"], ["x", "publicacion", "publicaciones"]],
    },
    {
        "id": "T4",
        "pregunta": "estoy sufriendo violencia, ¿dónde puedo pedir ayuda?",
        "grupos": [["911", "cjm", "089", "refugio"]],
    },
    {
        "id": "T5",
        "pregunta": "muéstrame los indicadores de Puebla",
        "grupos": [["puebla"], ["indicador", "indicadores"]],
    },
]


def normalizar(texto: str) -> str:
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def evaluar(tarea: dict) -> dict:
    inicio = time.time()
    resultado = responder(tarea["pregunta"])
    duracion = round(time.time() - inicio, 2)
    respuesta = normalizar(resultado.get("respuesta", ""))
    grupos_ok = [any(alt in respuesta for alt in grupo) for grupo in tarea["grupos"]]
    return {
        "id": tarea["id"],
        "pregunta": tarea["pregunta"],
        "exito": all(grupos_ok),
        "grupos_ok": grupos_ok,
        "tiempo_segundos": duracion,
        "respuesta": resultado.get("respuesta", ""),
        "sql": resultado.get("sql"),
        "n_resultados": len(resultado.get("resultados") or []),
    }


def main() -> None:
    resultados = [evaluar(tarea) for tarea in TAREAS]
    exitos = sum(1 for r in resultados if r["exito"])

    reporte_dir = os.path.join(BASE, "reports")
    os.makedirs(reporte_dir, exist_ok=True)
    ruta_json = os.path.join(reporte_dir, "validacion_funcional_tareas.json")
    ruta_md = os.path.join(reporte_dir, "validacion_funcional_tareas.md")

    with open(ruta_json, "w", encoding="utf-8") as archivo:
        json.dump(resultados, archivo, ensure_ascii=False, indent=2)

    lineas = [
        "# Validación funcional de tareas — MHub",
        "",
        "> Esto verifica que los flujos respondan; **no sustituye** las pruebas de",
        "> usabilidad con personas. Las sesiones reales siguen pendientes.",
        "",
        f"Resultado: **{exitos}/{len(resultados)}** tareas con respuesta esperada.",
        "",
        "| Tarea | Pregunta | Éxito | Tiempo (s) | Resultados |",
        "|---|---|---:|---:|---:|",
    ]
    for r in resultados:
        lineas.append(
            f"| {r['id']} | {r['pregunta']} | {'Sí' if r['exito'] else 'No'} | "
            f"{r['tiempo_segundos']} | {r['n_resultados']} |"
        )
    lineas += ["", "## Respuestas", ""]
    for r in resultados:
        lineas += [
            f"### {r['id']}",
            "",
            r["respuesta"][:1200],
            "",
        ]
    with open(ruta_md, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas) + "\n")

    for r in resultados:
        print(f"{r['id']}: {'OK' if r['exito'] else 'FALLA'} ({r['tiempo_segundos']} s)")
    print(f"\nValidación funcional: {exitos}/{len(resultados)}")
    print(f"Reporte: {ruta_md}")


if __name__ == "__main__":
    main()
