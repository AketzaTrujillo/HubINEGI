# Runner del golden set (Fase 5).
# Valida intención, spec y ejecución de SQL (sin depender de Ollama).
# Uso: python run_golden.py
import json
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

import intent_router   # noqa: E402
import query_spec      # noqa: E402
import sql_builder     # noqa: E402
from database import ejecutar_select  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_set.jsonl")


def tipos_esperados(caso):
    tipo = caso["tipo"]
    return tipo if isinstance(tipo, list) else [tipo]


def evaluar(caso):
    pregunta = caso["pregunta"]
    contexto = caso.get("contexto")

    ruta = intent_router.clasificar(pregunta, contexto)
    errores = []

    if ruta["tipo"] not in tipos_esperados(caso):
        errores.append(f"tipo={ruta['tipo']} (esperado {caso['tipo']})")

    if ruta["tipo"] == "FAQ" and caso.get("faq"):
        faq = ruta.get("faq") or {}
        if caso["faq"].lower() not in (faq.get("pregunta") or "").lower():
            errores.append(f"faq={faq.get('pregunta')} (esperado {caso['faq']})")

    if ruta["tipo"] in ("CONSULTA_AGREGACION", "CONSULTA_DETALLE"):
        spec = query_spec.construir_spec(pregunta, ruta, contexto)
        if caso.get("operacion") and spec["operacion"] != caso["operacion"]:
            errores.append(f"operacion={spec['operacion']} (esperado {caso['operacion']})")
        if caso.get("fuente") and spec["fuente"] != caso["fuente"]:
            errores.append(f"fuente={spec['fuente']} (esperado {caso['fuente']})")
        if caso.get("entidad") and spec["entidad"] != caso["entidad"]:
            errores.append(f"entidad={spec['entidad']} (esperado {caso['entidad']})")
        if caso.get("anio") and spec["anio"] != caso["anio"]:
            errores.append(f"anio={spec['anio']} (esperado {caso['anio']})")

        try:
            sql, params = sql_builder.construir_sql(spec)
            ejecutar_select(sql, params=params)
        except Exception as error:
            errores.append(f"sql error: {error}")

    return errores


def main():
    with open(GOLDEN, "r", encoding="utf-8") as f:
        casos = [json.loads(linea) for linea in f if linea.strip()]

    total = len(casos)
    ok = 0
    por_tipo = {}

    for caso in casos:
        errores = evaluar(caso)
        tipo = caso["tipo"] if isinstance(caso["tipo"], str) else "/".join(caso["tipo"])
        por_tipo.setdefault(tipo, [0, 0])
        por_tipo[tipo][1] += 1

        if errores:
            print(f"[FALLA] {caso['pregunta']}")
            for e in errores:
                print(f"        - {e}")
        else:
            ok += 1
            por_tipo[tipo][0] += 1

    print("\n" + "=" * 60)
    print(f"Resultado: {ok}/{total} ({100 * ok // total}%)")
    for tipo, (bien, tot) in sorted(por_tipo.items()):
        print(f"  {tipo:22} {bien}/{tot}")


if __name__ == "__main__":
    main()
