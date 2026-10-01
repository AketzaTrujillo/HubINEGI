# Runner del golden de paráfrasis para el intérprete LLM (Fase 7).
# Requiere Ollama en marcha. Mide generalización, no casos exactos.
# Uso: python run_interprete.py
import json
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

import interprete  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_interprete.jsonl")


def coincide(valor, esperado):
    if esperado is None:
        return True
    if isinstance(esperado, list):
        return valor in esperado
    return valor == esperado


def evaluar(caso):
    r = interprete.interpretar(caso["pregunta"], caso.get("contexto"))
    if not r:
        return ["intérprete devolvió None"]

    errores = []
    if "intencion" in caso and not coincide(r["intencion"], caso["intencion"]):
        errores.append(f"intencion={r['intencion']} (esp {caso['intencion']})")
    if "operacion" in caso and not coincide(r["operacion"], caso["operacion"]):
        errores.append(f"operacion={r['operacion']} (esp {caso['operacion']})")
    if "fuente" in caso and not coincide(r["fuente"], caso["fuente"]):
        errores.append(f"fuente={r['fuente']} (esp {caso['fuente']})")
    if "entidad" in caso and not coincide(r["entidad"], caso["entidad"]):
        errores.append(f"entidad={r['entidad']} (esp {caso['entidad']})")
    if "anio" in caso and not coincide(r["anio"], caso["anio"]):
        errores.append(f"anio={r['anio']} (esp {caso['anio']})")
    return errores


def main():
    with open(GOLDEN, "r", encoding="utf-8") as f:
        casos = [json.loads(linea) for linea in f if linea.strip()]

    ok = 0
    for caso in casos:
        errores = evaluar(caso)
        if errores:
            print(f"[FALLA] {caso['pregunta']}")
            for e in errores:
                print(f"        - {e}")
        else:
            ok += 1

    total = len(casos)
    print("\n" + "=" * 60)
    print(f"Intérprete: {ok}/{total} ({100 * ok // total}%)")


if __name__ == "__main__":
    main()
