# Runner del golden conversacional (determinista, sin LLM).
# Prueba el enrutador y los manejadores de anáfora/seguimiento.
# Uso: python run_conversacion.py
import json
import os
import sys
import unicodedata

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "backend"))

import intent_router  # noqa: E402
import consulta_mhub  # noqa: E402
import query_spec  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_conversacion.jsonl")


def norm(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def tema_ranking():
    general = consulta_mhub._indicador_general(None) or {"id_indicador": None, "nombre": ""}
    return {
        "tema": "indicador",
        "entidad_top": "Estado de México",
        "anio": 2021,
        "indicador": general["nombre"],
        "_id_indicador": general["id_indicador"],
        "fuente": None,
    }


def evaluar(caso):
    pregunta = caso["pregunta"]

    if "operacion_esperada" in caso:
        spec = query_spec.desde_interpretacion(
            {"intencion": "consulta", "operacion": "maximo"}, None, pregunta
        )
        if spec["operacion"] != caso["operacion_esperada"]:
            return [f"operacion={spec['operacion']} (esp {caso['operacion_esperada']})"]
        return []

    if "tipo" in caso:
        ruta = intent_router.clasificar(pregunta)
        errores = []
        if ruta["tipo"] != caso["tipo"]:
            errores.append(f"tipo={ruta['tipo']} (esp {caso['tipo']})")
        if caso.get("recurso") and ruta.get("recurso") != caso["recurso"]:
            errores.append(f"recurso={ruta.get('recurso')} (esp {caso['recurso']})")
        return errores

    tema = tema_ranking() if caso.get("tema_tipo") == "ranking" else caso["tema"]
    resultado = consulta_mhub._resolver_anafora(pregunta, {"tema": tema})

    if not resultado:
        return ["la anáfora no produjo respuesta"]

    if caso.get("contiene"):
        if norm(caso["contiene"]) not in norm(resultado.get("respuesta", "")):
            return [f"falta «{caso['contiene']}» en la respuesta"]

    return []


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
    print(f"Conversación: {ok}/{total} ({100 * ok // total}%)")


if __name__ == "__main__":
    main()
