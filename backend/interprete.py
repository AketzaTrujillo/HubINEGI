"""Intérprete LLM (Fase 7).

Convierte la pregunta en un JSON de intención + slots usando el modelo local
(Ollama con `format: json`), con memoria de los últimos turnos. Valida el
resultado contra la base de datos. Si algo falla, devuelve None para que el
sistema use el enrutador por reglas.
"""
import json

import semantic_loader
import vocabulario
from ollama_service import preguntar_json, proveedor_actual

INTENCIONES = {
    "consulta", "catalogo", "explicar", "ayuda", "definicion", "seguir",
    "conversacion", "fuera_de_tema", "no_soportado", "aclarar", "rutas",
}

RECURSOS = {
    "tipos_violencia", "fuentes", "entidades", "indicadores", "unidades",
}

OPERACIONES = {
    "detalle", "conteo", "promedio", "maximo", "minimo", "suma",
    "top_n", "por_anio", "por_entidad", "por_tipo_violencia",
    "anios_disponibles", "comparar",
}

SISTEMA = """Eres el intérprete de MHub, un asistente de indicadores de violencia contra las mujeres en México.
Tu tarea es convertir la pregunta del usuario en un objeto JSON. Responde SOLO con JSON válido.

Claves del JSON:
- intencion: "consulta" | "catalogo" | "explicar" | "ayuda" | "definicion" | "seguir" | "conversacion" | "fuera_de_tema" | "no_soportado" | "aclarar" | "rutas"
- recurso: si intencion es "catalogo", cuál de estos:
    tipos_violencia (tipos/clases de violencia) |
    fuentes (de dónde vienen los datos) |
    entidades (estados, entidades federativas) |
    indicadores (métricas) |
    unidades (porcentaje/conteo/tasa).
  Si no aplica, null.
- operacion: "detalle" | "conteo" | "promedio" | "maximo" | "minimo" | "suma" | "top_n" | "por_anio" | "por_entidad" | "por_tipo_violencia" | "anios_disponibles" | null
- fuente: "ENDIREH" | "SIESVIM" | "INMUJERES" | "X" | null
- entidad: nombre del estado o "Estados Unidos Mexicanos" | null
- entidad_b: segunda entidad, SOLO si pide comparar dos entidades | null
- anio: número de 4 dígitos | null
- grupo: lista con "anio" o "entidad" | []
- tipo_violencia: "física" | "psicológica" | "sexual" | "económica" | "patrimonial" | "discriminación" | null
- indicador: texto del indicador si el usuario lo menciona | null
- aclaracion: si intencion es "aclarar" o "no_soportado", la pregunta o explicación para el usuario | null
- confianza: número entre 0 y 1

Reglas de operación:
- "cuántos", "cuántas", "número de" -> "conteo"
- "promedio", "media" -> "promedio"
- "más alto", "mayor", "máximo" -> "maximo"
- "más bajo", "menor", "mínimo" -> "minimo"
- "por año", "cada año" -> "por_anio". "por entidad", "por estado" -> "por_entidad"
- "tipo de violencia más común", "qué violencia predomina" -> "por_tipo_violencia"
- "qué años hay", "de qué años", "años disponibles", "solo tienes de ese año" -> "anios_disponibles"
- "muéstrame", "dame los", "lista", "cuáles son" -> "detalle"
- "compara X y Z", "diferencia entre X y Z", "X vs Z" -> "comparar" con entidad=X y entidad_b=Z
- Si no hay operación clara, usa "detalle".

Reglas de intención:
- "qué es", "qué significa", "háblame de", "cuéntame sobre" -> "definicion"
- "no entiendo", "explícame", "y eso qué significa" -> "explicar"
- Si pide cuántos/quiénes/cuáles existen o hay de un CATÁLOGO (tipos de violencia, fuentes, entidades/estados, indicadores, unidades), aunque esté mal escrito o use sinónimos -> "catalogo" con el recurso más parecido.
- Si pide ayuda porque está viviendo violencia, o dónde acudir/denunciar (CJM, 911, refugio) -> "rutas".
- Tema ajeno (programación, cocina, clima, etc.) -> "fuera_de_tema"
- Del dominio pero no respondible con la base -> "no_soportado" y explica en aclaracion
- Falta un dato clave -> "aclarar" y pon una pregunta concreta en aclaracion
- Si se refiere al turno anterior ("eso", "ese año", "y en X"), usa el CONTEXTO.

Ejemplos:
P: cuántas publicaciones de X hay en Jalisco
R: {"intencion":"consulta","recurso":null,"operacion":"conteo","fuente":"X","entidad":"Jalisco","anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.95}
P: cuántos tipos de violencia existen
R: {"intencion":"catalogo","recurso":"tipos_violencia","operacion":null,"fuente":null,"entidad":null,"anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: cuántas clases de violencia hay
R: {"intencion":"catalogo","recurso":"tipos_violencia","operacion":null,"fuente":null,"entidad":null,"anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: qué fuentes tienen
R: {"intencion":"catalogo","recurso":"fuentes","operacion":null,"fuente":null,"entidad":null,"anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: cuántos indicadores tienes
R: {"intencion":"catalogo","recurso":"indicadores","operacion":null,"fuente":null,"entidad":null,"anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: de qué estados tienes datos
R: {"intencion":"catalogo","recurso":"entidades","operacion":null,"fuente":null,"entidad":null,"anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: tipo de violencia más común en México
R: {"intencion":"consulta","recurso":null,"operacion":"por_tipo_violencia","fuente":null,"entidad":"Estados Unidos Mexicanos","anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: qué años hay para Puebla
R: {"intencion":"consulta","recurso":null,"operacion":"anios_disponibles","fuente":null,"entidad":"Puebla","anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: cuál es el estado con más violencia
R: {"intencion":"consulta","recurso":null,"operacion":"por_entidad","fuente":null,"entidad":null,"anio":null,"grupo":["entidad"],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: qué tipos de violencia hay en Veracruz
R: {"intencion":"consulta","recurso":null,"operacion":"por_tipo_violencia","fuente":null,"entidad":"Veracruz","anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: en qué año hubo el mayor índice de violencia psicológica
R: {"intencion":"consulta","recurso":null,"operacion":"maximo","fuente":null,"entidad":null,"anio":null,"grupo":[],"tipo_violencia":"psicológica","indicador":null,"aclaracion":null,"confianza":0.9}
P: gráfica de la violencia familiar en 2024
R: {"intencion":"consulta","recurso":null,"operacion":"por_entidad","fuente":null,"entidad":null,"anio":2024,"grupo":["entidad"],"tipo_violencia":"familiar","indicador":null,"aclaracion":null,"confianza":0.9}
P: divídelo por cada estado
R: {"intencion":"consulta","recurso":null,"operacion":"por_entidad","fuente":null,"entidad":null,"anio":null,"grupo":["entidad"],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.85}
P: publicaciones de X por año en Jalisco
R: {"intencion":"consulta","recurso":null,"operacion":"por_anio","fuente":"X","entidad":"Jalisco","anio":null,"grupo":["anio"],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: compara la violencia de pareja entre Jalisco y Puebla en 2021
R: {"intencion":"consulta","recurso":null,"operacion":"comparar","fuente":null,"entidad":"Jalisco","entidad_b":"Puebla","anio":2021,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: háblame de SIESVIM
R: {"intencion":"definicion","recurso":null,"operacion":null,"fuente":"SIESVIM","entidad":null,"anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.9}
P: estoy sufriendo violencia, dónde puedo pedir ayuda
R: {"intencion":"rutas","recurso":null,"operacion":null,"fuente":null,"entidad":null,"anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.95}
P: dame el código de hola mundo en C
R: {"intencion":"fuera_de_tema","recurso":null,"operacion":null,"fuente":null,"entidad":null,"anio":null,"grupo":[],"tipo_violencia":null,"indicador":null,"aclaracion":null,"confianza":0.95}

Nunca inventes cifras ni entidades.
"""


def _contexto_interprete(contexto):
    lineas = []

    try:
        fuentes = semantic_loader.ejecutar_select(
            "SELECT codigo FROM fuentes WHERE codigo IS NOT NULL ORDER BY id_fuente"
        )
        lineas.append("FUENTES DISPONIBLES: " + ", ".join(f["codigo"] for f in fuentes))
    except Exception:
        pass

    datos = semantic_loader.ayuda_datos()
    if datos:
        lineas.append(
            f"AÑOS DISPONIBLES: {datos.get('anio_min')} a {datos.get('anio_max')}"
        )

    tipos = semantic_loader.tipos_violencia()
    if tipos:
        lineas.append("TIPOS DE VIOLENCIA: " + ", ".join(tipos))

    historial = (contexto or {}).get("historial") or []
    if historial:
        lineas.append("\nCONTEXTO (turnos anteriores):")
        for turno in historial[-2:]:
            respuesta = str(turno.get("respuesta") or "")[:120]
            lineas.append(f"- Usuario: {turno.get('pregunta')}")
            lineas.append(f"  MHub: {respuesta}")
            if turno.get("spec"):
                spec = {k: turno["spec"].get(k) for k in ("operacion", "fuente", "entidad", "anio")}
                lineas.append(f"  spec: {json.dumps(spec, ensure_ascii=False)}")

    return "\n".join(lineas)


def _validar(bruto, pregunta_original=None, pista=None):
    if not isinstance(bruto, dict):
        return None

    intencion = str(bruto.get("intencion") or "").strip().lower()
    if intencion not in INTENCIONES:
        intencion = "aclarar"

    recurso = str(bruto.get("recurso") or "").strip().lower() or None
    if recurso not in RECURSOS:
        recurso = None

    operacion = bruto.get("operacion")
    if operacion not in OPERACIONES:
        operacion = None

    if operacion and intencion in ("definicion", "aclarar"):
        intencion = "consulta"

    if intencion == "seguir" and operacion is None:
        bajo = str(pregunta_original or "").lower()
        if "año" in bajo or "ano" in bajo or "solo tienes" in bajo:
            operacion = "anios_disponibles"

    # Respaldo: usar la pista borrosa si el modelo no lo captó y no hay
    # una operación de datos claramente distinta.
    if (
        not recurso
        and pista
        and intencion in ("consulta", "aclarar", "catalogo")
        and operacion in (None, "conteo", "detalle", "anios_disponibles")
    ):
        recurso = pista
        intencion = "catalogo"

    fuente = bruto.get("fuente")
    if fuente:
        fuente = semantic_loader.resolver_fuente(str(fuente)) or None

    entidad = bruto.get("entidad")
    entidad_nombre = None
    if entidad:
        id_entidad = semantic_loader.resolver_entidad(str(entidad))
        if id_entidad:
            entidad_nombre = semantic_loader.nombre_entidad(id_entidad)

    entidad_b = bruto.get("entidad_b")
    entidad_b_nombre = None
    if entidad_b:
        id_b = semantic_loader.resolver_entidad(str(entidad_b))
        if id_b:
            entidad_b_nombre = semantic_loader.nombre_entidad(id_b)

    anio = bruto.get("anio")
    try:
        anio = int(anio) if anio not in (None, "") else None
    except (TypeError, ValueError):
        anio = None

    grupo = bruto.get("grupo")
    if not isinstance(grupo, list):
        grupo = []
    grupo = [g for g in grupo if g in ("anio", "entidad")]

    tipo_violencia = bruto.get("tipo_violencia")
    filtro_texto = None
    if tipo_violencia:
        resuelto = semantic_loader.resolver_tipo_violencia(str(tipo_violencia))
        if resuelto:
            tipo_violencia = resuelto
        else:
            palabra = str(tipo_violencia).strip().lower()
            ambitos = {
                "familiar": "familiar", "intrafamiliar": "familiar",
                "pareja": "pareja", "conyugal": "pareja",
                "laboral": "laboral", "escolar": "escolar",
            }
            filtro_texto = ambitos.get(palabra)
            tipo_violencia = None
    else:
        tipo_violencia = None

    try:
        confianza = float(bruto.get("confianza"))
    except (TypeError, ValueError):
        confianza = 0.0

    # Catálogo solo si NO hay filtros concretos (fuente/entidad/año).
    if (
        recurso
        and intencion in ("consulta", "aclarar", "definicion", "no_soportado")
        and operacion in (None, "detalle")
        and not fuente and not entidad_nombre and not anio
    ):
        intencion = "catalogo"

    # Si hay filtros concretos, no es un catálogo: es una consulta de datos.
    if intencion == "catalogo" and (fuente or entidad_nombre or anio):
        intencion = "consulta"

    # "qué datos tienes de <entidad>" -> cobertura, no ayuda genérica
    if intencion == "ayuda" and (entidad_nombre or fuente):
        intencion = "consulta"
        operacion = "anios_disponibles"

    return {
        "intencion": intencion,
        "recurso": recurso,
        "operacion": operacion,
        "fuente": fuente,
        "entidad": entidad_nombre,
        "entidad_b": entidad_b_nombre,
        "anio": anio,
        "grupo": grupo,
        "tipo_violencia": tipo_violencia,
        "indicador": bruto.get("indicador") or None,
        "filtro_texto": filtro_texto,
        "aclaracion": bruto.get("aclaracion") or None,
        "confianza": confianza,
    }


def interpretar(pregunta, contexto=None):
    if proveedor_actual("interprete") not in ("local", "groq"):
        return None

    pista = vocabulario.pista(pregunta)

    prompt = f"""{_contexto_interprete(contexto)}

PISTA DE VOCABULARIO: {pista or "(ninguna)"}

PREGUNTA DEL USUARIO: {pregunta}

Devuelve el JSON."""

    try:
        crudo = preguntar_json(prompt, system=SISTEMA)
        bruto = json.loads(crudo)
    except Exception as error:
        print(f"[interprete] no se pudo interpretar: {error}")
        return None

    return _validar(bruto, pregunta, pista)


if __name__ == "__main__":
    pruebas = [
        "Cuál fue el tipo de violencia más común en México?",
        "Solo tienes de ese año?",
        "dame el código de hola mundo en C",
        "¿qué años tienes para Puebla?",
    ]
    contexto = {
        "historial": [
            {
                "pregunta": "Indicadores de ENDIREH para Puebla",
                "respuesta": "Los indicadores de ENDIREH para Puebla en 2021 son...",
                "spec": {"operacion": "detalle", "fuente": "ENDIREH", "entidad": "Puebla", "anio": 2021},
            }
        ]
    }
    for p in pruebas:
        print("=" * 60)
        print(p)
        print(json.dumps(interpretar(p, contexto), ensure_ascii=False, indent=1))
