"""Analiza los resultados de usabilidad de MHub (objetivo 9).

Entradas:
- CSV de tareas: usuario, tarea, exito (1/0), tiempo_segundos, errores, comentarios.
- CSV SUS: usuario, sus_1 ... sus_10 (escala 1-5).

Salidas:
- reports/usabilidad_reporte.md
- reports/usabilidad_metricas.json

Uso:
    python analizar_usabilidad.py \
      --tareas resultados_tareas.csv \
      --sus resultados_sus.csv
"""

from __future__ import annotations

import argparse
import json
import os

import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def calcular_sus(fila) -> float:
    """SUS: impares = respuesta - 1; pares = 5 - respuesta; suma * 2.5."""
    total = 0
    for i in range(1, 11):
        valor = int(fila[f"sus_{i}"])
        total += (valor - 1) if i % 2 == 1 else (5 - valor)
    return round(total * 2.5, 2)


def analizar(tareas: pd.DataFrame, sus: pd.DataFrame) -> dict:
    requeridas = {"usuario", "tarea", "exito", "tiempo_segundos", "errores"}
    faltantes = requeridas - set(tareas.columns)
    if faltantes:
        raise SystemExit(f"Faltan columnas en tareas: {', '.join(sorted(faltantes))}")

    tareas = tareas.copy()
    tareas["exito"] = pd.to_numeric(tareas["exito"], errors="coerce").fillna(0).astype(int)
    tareas["tiempo_segundos"] = pd.to_numeric(tareas["tiempo_segundos"], errors="coerce")
    tareas["errores"] = pd.to_numeric(tareas["errores"], errors="coerce").fillna(0).astype(int)

    por_tarea = []
    for tarea, grupo in tareas.groupby("tarea", sort=True):
        por_tarea.append(
            {
                "tarea": str(tarea),
                "n": int(len(grupo)),
                "exito": int(grupo["exito"].sum()),
                "tasa_exito": round(float(grupo["exito"].mean()), 4),
                "tiempo_promedio": round(float(grupo["tiempo_segundos"].mean()), 2),
                "errores_promedio": round(float(grupo["errores"].mean()), 2),
            }
        )

    resumen_tareas = {
        "participantes": int(tareas["usuario"].nunique()),
        "tareas": int(tareas["tarea"].nunique()),
        "registros": int(len(tareas)),
        "tasa_exito_global": round(float(tareas["exito"].mean()), 4),
        "tiempo_promedio_global": round(float(tareas["tiempo_segundos"].mean()), 2),
        "errores_promedio_global": round(float(tareas["errores"].mean()), 2),
        "por_tarea": por_tarea,
    }

    sus_resultado = None
    if not sus.empty:
        faltantes_sus = {f"sus_{i}" for i in range(1, 11)} - set(sus.columns)
        if faltantes_sus:
            raise SystemExit(
                f"Faltan columnas SUS: {', '.join(sorted(faltantes_sus))}"
            )
        sus = sus.copy()
        sus["sus_score"] = sus.apply(calcular_sus, axis=1)
        sus_resultado = {
            "participantes": int(len(sus)),
            "promedio": round(float(sus["sus_score"].mean()), 2),
            "minimo": round(float(sus["sus_score"].min()), 2),
            "maximo": round(float(sus["sus_score"].max()), 2),
            "por_participante": [
                {"usuario": str(fila["usuario"]), "sus": float(fila["sus_score"])}
                for _, fila in sus.iterrows()
            ],
        }

    return {"tareas": resumen_tareas, "sus": sus_resultado}


def escribir_reporte(resultado: dict, ruta_md: str, ruta_json: str, ejemplo: bool) -> None:
    os.makedirs(os.path.dirname(ruta_md), exist_ok=True)
    resultado["ejemplo"] = ejemplo
    with open(ruta_json, "w", encoding="utf-8") as archivo:
        json.dump(resultado, archivo, ensure_ascii=False, indent=2)

    t = resultado["tareas"]
    lineas = [
        "# Reporte de usabilidad — MHub",
        "",
        "> **Datos de ejemplo:** este reporte se generó con archivos ficticios."
        if ejemplo
        else "> Reporte generado a partir de sesiones reales.",
        "",
        "## Resumen",
        "",
        f"- Participantes: **{t['participantes']}**",
        f"- Tareas evaluadas: **{t['tareas']}**",
        f"- Registros: **{t['registros']}**",
        f"- Tasa de éxito global: **{t['tasa_exito_global'] * 100:.1f}%**",
        f"- Tiempo promedio global: **{t['tiempo_promedio_global']:.1f} s**",
        f"- Errores promedio: **{t['errores_promedio_global']:.2f}**",
        "",
        "## Resultados por tarea",
        "",
        "| Tarea | n | Éxitos | Tasa de éxito | Tiempo promedio (s) | Errores promedio |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for fila in t["por_tarea"]:
        lineas.append(
            f"| {fila['tarea']} | {fila['n']} | {fila['exito']} | "
            f"{fila['tasa_exito'] * 100:.1f}% | {fila['tiempo_promedio']:.1f} | "
            f"{fila['errores_promedio']:.2f} |"
        )

    if resultado["sus"]:
        s = resultado["sus"]
        lineas += [
            "",
            "## System Usability Scale (SUS)",
            "",
            f"- Participantes: **{s['participantes']}**",
            f"- SUS promedio: **{s['promedio']}**",
            f"- Rango: **{s['minimo']} – {s['maximo']}**",
            "",
            "| Participante | SUS |",
            "|---|---:|",
        ]
        for fila in s["por_participante"]:
            lineas.append(f"| {fila['usuario']} | {fila['sus']} |")
        lineas += [
            "",
            "Interpretación: >80 excelente, 68–80 aceptable, <68 con problemas.",
        ]

    lineas += [
        "",
        "## Lectura",
        "",
        "- Si una tarea tiene tasa de éxito baja, revisar el flujo y el texto de ayuda.",
        "- Si el tiempo es alto, revisar la claridad de las sugerencias y filtros.",
        "- Los comentarios cualitativos deben analizarse junto con los videos/notas.",
    ]

    with open(ruta_md, "w", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analiza resultados de usabilidad.")
    parser.add_argument("--tareas", default=os.path.join(os.path.dirname(__file__), "resultados_tareas.csv"))
    parser.add_argument("--sus", default=os.path.join(os.path.dirname(__file__), "resultados_sus.csv"))
    parser.add_argument("--reporte", default=os.path.join(BASE, "reports", "usabilidad_reporte.md"))
    parser.add_argument("--json", default=os.path.join(BASE, "reports", "usabilidad_metricas.json"))
    args = parser.parse_args()

    if not os.path.exists(args.tareas):
        raise SystemExit(
            f"No existe {args.tareas}. Copia resultados_tareas_ejemplo.csv y captura tus datos."
        )
    tareas = pd.read_csv(args.tareas)
    sus = pd.read_csv(args.sus) if os.path.exists(args.sus) else pd.DataFrame()

    resultado = analizar(tareas, sus)
    ejemplo = "ejemplo" in os.path.basename(args.tareas).lower()
    escribir_reporte(resultado, args.reporte, args.json, ejemplo)

    t = resultado["tareas"]
    print(f"Participantes: {t['participantes']}")
    print(f"Tasa de éxito global: {t['tasa_exito_global'] * 100:.1f}%")
    print(f"Tiempo promedio global: {t['tiempo_promedio_global']:.1f} s")
    if resultado["sus"]:
        print(f"SUS promedio: {resultado['sus']['promedio']}")
    print(f"Reporte: {args.reporte}")


if __name__ == "__main__":
    main()
