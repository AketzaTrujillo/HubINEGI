"""Agente de MHub (Fase 10).

Convierte la pregunta en un ciclo:
  plan -> usar herramienta -> observar -> (¿responde?) -> responder o reintentar.

El LLM decide la herramienta y los parámetros; el `sql_builder` ejecuta el SQL
(único ejecutor, con validación). Nunca se inventan cifras.
"""
import json

import database
import graficas
import query_spec
import sql_builder
import semantic_loader
import catalogo
import faq_store
from ollama_service import preguntar_json

MAX_PASOS = 3

INSTRUCCION = """Eres el agente de MHub, un asistente de indicadores de violencia contra las mujeres en México.
Tienes DATOS OFICIALES (ENDIREH, SIESVIM, INMUJERES) y publicaciones de X. Nunca inventas cifras.

En cada paso respondes SOLO con un JSON:
{"accion": "...", "args": {...}, "pensamiento": "breve"}

ACCIONES:
- "consultar": pedir datos. args:
    operacion: "detalle"|"conteo"|"promedio"|"maximo"|"minimo"|"suma"|"top_n"|"por_anio"|"por_entidad"|"por_tipo_violencia"|"anios_disponibles"|"comparar"
    fuente: "ENDIREH"|"SIESVIM"|"INMUJERES"|"X"|null
    entidad: estado o "Estados Unidos Mexicanos" | null
    entidad_b: segunda entidad solo si comparas | null
    anio: 4 dígitos | null
    tipo_violencia: "física"|"psicológica"|"sexual"|"económica"|"patrimonial"|"discriminación"|"familiar"|"pareja"|"laboral"|"escolar" | null
    grupo: ["anio"]|["entidad"]|[]
    indicador: texto | null
- "catalogo": args {"recurso": "tipos_violencia"|"fuentes"|"entidades"|"indicadores"|"unidades"}
- "cobertura": args {"fuente": ..., "entidad": ...}  -> qué años hay
- "definicion": args {"termino": "..."}  -> definiciones y rutas de atención
- "responder": args {"respuesta": "..."}  -> cuando ya tienes lo necesario
- "aclarar": args {"pregunta": "..."}  -> si falta un dato clave
- "fuera_de_tema": {}  -> si no es sobre violencia contra las mujeres en México

REGLAS:
- Preguntas de datos -> "consultar". Revisa el resultado; si NO responde, ajusta y vuelve a intentar (máx 3).
- Si el usuario pregunta por "el estado con más violencia" -> operacion "por_entidad".
- Si pregunta "de qué tipo de violencia" -> operacion "por_tipo_violencia".
- Si pregunta "en qué año" -> operacion "maximo"/"minimo" con tipo_violencia si aplica.
- Si pide una gráfica -> usa una operacion con varios valores ("por_entidad", "por_anio", "por_tipo_violencia").
- Cuando los datos respondan, usa "responder" con una respuesta breve y cita la fuente.
- Al responder, puedes usar Markdown (negritas, listas y tablas) para organizar la respuesta.
- Usa solo lo que devuelvan las herramientas. No inventes teléfonos, cifras ni entidades.
"""


def _contexto_texto(contexto):
    lineas = []
    tema = (contexto or {}).get("tema") or {}
    if tema:
        lineas.append("TEMA ACTUAL: " + json.dumps(
            {k: tema.get(k) for k in ("tema", "recurso", "entidad", "entidad_top",
                                      "fuente", "anio", "indicador", "operacion")},
            ensure_ascii=False,
        ))
    historial = (contexto or {}).get("historial") or []
    if historial:
        lineas.append("TURNOS ANTERIORES:")
        for t in historial[-2:]:
            lineas.append(f"- U: {t.get('pregunta')}")
            lineas.append(f"  M: {str(t.get('respuesta') or '')[:150]}")
    return "\n".join(lineas)


def _resumen_resultado(obs):
    if not obs.get("ok"):
        return f"ERROR: {obs.get('error')}"
    filas = obs.get("filas") or []
    if not filas:
        return "SIN RESULTADOS (ajusta los filtros o los años)"
    return json.dumps(filas[:20], ensure_ascii=False, default=str)[:3000]


def _llamar(pregunta, contexto, observaciones):
    obs_txt = ""
    if observaciones:
        obs_txt = "\n\nOBSERVACIONES (lo que ya intentaste):\n"
        for o in observaciones:
            obs_txt += f"- acción {o['accion']} args={json.dumps(o['args'], ensure_ascii=False)} -> {o['resumen']}\n"

    prompt = f"""{_contexto_texto(contexto)}

PREGUNTA DEL USUARIO: {pregunta}
{obs_txt}

¿Qué haces ahora? Devuelve el JSON."""

    try:
        crudo = preguntar_json(prompt, system=INSTRUCCION, tarea="agente")
        return json.loads(crudo)
    except Exception as error:
        print(f"[agente] no se pudo interpretar el plan: {error}")
        return None


def _spec_desde_args(args):
    import consulta_mhub as cm

    operacion = args.get("operacion") or "detalle"
    if operacion not in query_spec.OPERACIONES:
        operacion = "detalle"

    fuente = None
    if args.get("fuente"):
        fuente = semantic_loader.resolver_fuente(str(args["fuente"]))

    entidad = None
    if args.get("entidad"):
        id_e = semantic_loader.resolver_entidad(str(args["entidad"]))
        if id_e:
            entidad = semantic_loader.nombre_entidad(id_e)

    entidad_b = None
    if args.get("entidad_b"):
        id_b = semantic_loader.resolver_entidad(str(args["entidad_b"]))
        if id_b:
            entidad_b = semantic_loader.nombre_entidad(id_b)

    try:
        anio = int(args["anio"]) if args.get("anio") not in (None, "") else None
    except (TypeError, ValueError):
        anio = None

    tipo = args.get("tipo_violencia")
    tipo_res = semantic_loader.resolver_tipo_violencia(str(tipo)) if tipo else None
    filtro_texto = None
    if tipo and not tipo_res:
        ambitos = {
            "familiar": "familiar", "intrafamiliar": "familiar",
            "pareja": "pareja", "conyugal": "pareja",
            "laboral": "laboral", "escolar": "escolar",
        }
        filtro_texto = ambitos.get(str(tipo).strip().lower())

    grupo = args.get("grupo") or []
    if not isinstance(grupo, list):
        grupo = []

    spec = {
        "operacion": operacion,
        "metrica": query_spec._metrica_de_operacion(operacion),
        "fuente": fuente,
        "entidad": entidad,
        "entidad_id": None,
        "entidad_b": entidad_b,
        "anio": anio,
        "grupo": grupo,
        "orden": "desc",
        "limite": 100,
        "indicador": args.get("indicador"),
        "tipo_violencia": tipo_res,
        "filtro_texto": filtro_texto,
    }
    return cm._preparar_ranking(spec)


def _ejecutar_accion(accion, args, contexto):
    args = args or {}

    if accion == "consultar":
        try:
            spec = _spec_desde_args(args)
            valido, error = query_spec.validar_spec(spec)
            if not valido:
                return {"ok": False, "error": error}
            sql, params = sql_builder.construir_sql(spec)
            filas = database.ejecutar_select(sql, params=params)
            return {"ok": True, "spec": spec, "sql": sql, "filas": filas}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    if accion == "catalogo":
        recurso = args.get("recurso")
        return {"ok": True, "filas": [], "texto": catalogo.responder(recurso)}

    if accion == "cobertura":
        import consulta_mhub as cm
        fuente = semantic_loader.resolver_fuente(str(args.get("fuente") or ""))
        entidad_id = None
        entidad = args.get("entidad")
        if entidad:
            entidad_id = semantic_loader.resolver_entidad(str(entidad))
        spec = {
            "operacion": "anios_disponibles", "metrica": "detalle", "fuente": fuente,
            "entidad": semantic_loader.nombre_entidad(entidad_id) if entidad_id else None,
            "entidad_id": entidad_id, "entidad_b": None, "anio": None, "grupo": [],
            "orden": "desc", "limite": 100, "indicador": None, "tipo_violencia": None,
        }
        try:
            sql, params = sql_builder.construir_sql(spec)
            anios = [f["anio"] for f in database.ejecutar_select(sql, params=params)]
            return {"ok": True, "filas": [], "texto": "Años disponibles: " + ", ".join(str(a) for a in anios)}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    if accion == "definicion":
        termino = str(args.get("termino") or "")
        entrada = faq_store.buscar_glosario(termino)
        if entrada:
            return {"ok": True, "filas": [], "texto": entrada["definicion"]}
        faq = faq_store.buscar_exacta(termino) or faq_store.buscar_semantica(termino)
        if faq:
            return {"ok": True, "filas": [], "texto": faq["respuesta"]}
        fragmentos = faq_store.buscar_corpus(termino, limite=3)
        if fragmentos:
            texto = "\n\n".join(f"[{f.get('documento')}] {str(f.get('texto'))[:600]}" for f in fragmentos)
            return {"ok": True, "filas": [], "texto": texto}
        return {"ok": False, "error": "sin definición"}

    return {"ok": False, "error": f"acción desconocida: {accion}"}


def _respuesta_agotada(pregunta, contexto, observaciones, ultimo):
    obs_txt = "\n".join(
        f"- {o['accion']} -> {o['resumen']}" for o in observaciones
    )
    prompt = f"""Pregunta: {pregunta}

Observaciones:
{obs_txt}

Redacta la mejor respuesta posible SOLO con esos datos. Si no alcanza, dilo y ofrece qué sí puedes responder. Cita la fuente. No inventes cifras. Puedes usar Markdown (negritas, listas y tablas)."""
    from ollama_service import preguntar_ollama
    return preguntar_ollama(prompt).strip()


def ejecutar(pregunta, contexto=None):
    observaciones = []
    ultimo = {"spec": None, "sql": None, "filas": None}

    for _ in range(MAX_PASOS + 1):
        plan = _llamar(pregunta, contexto, observaciones)
        if not plan:
            return None

        accion = str(plan.get("accion") or "").strip().lower()
        args = plan.get("args") or {}

        if accion == "responder":
            texto = args.get("respuesta") or plan.get("respuesta")
            if not texto:
                return None
            grafica = None
            if ultimo["spec"] and ultimo["filas"]:
                grafica = graficas.construir_grafica(ultimo["spec"], ultimo["filas"])
            return {
                "tipo": "final", "respuesta": texto,
                "spec": ultimo["spec"], "sql": ultimo["sql"],
                "resultados": ultimo["filas"], "grafica": grafica,
            }

        if accion == "aclarar":
            return {
                "tipo": "aclarar",
                "respuesta": args.get("pregunta") or plan.get("pregunta"),
            }

        if accion == "fuera_de_tema":
            return {"tipo": "fuera_de_tema"}

        if accion not in ("consultar", "catalogo", "cobertura", "definicion"):
            return None

        obs = _ejecutar_accion(accion, args, contexto)
        if accion == "consultar" and obs.get("ok"):
            ultimo = {"spec": obs["spec"], "sql": obs["sql"], "filas": obs["filas"]}

        observaciones.append({
            "accion": accion,
            "args": args,
            "resumen": obs.get("texto") or _resumen_resultado(obs),
        })

    texto = _respuesta_agotada(pregunta, contexto, observaciones, ultimo)
    grafica = None
    if ultimo["spec"] and ultimo["filas"]:
        grafica = graficas.construir_grafica(ultimo["spec"], ultimo["filas"])
    return {
        "tipo": "final", "respuesta": texto,
        "spec": ultimo["spec"], "sql": ultimo["sql"],
        "resultados": ultimo["filas"], "grafica": grafica,
    }
