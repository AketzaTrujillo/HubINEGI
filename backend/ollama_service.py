import os
import json
import re
import time
import uuid

import requests

import env_config  # noqa: F401  (carga backend/.env al importar)

# ---- Local (Ollama) ----
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODELO = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

# ---- OpenCode Go (compatible con OpenAI) ----
OPENCODE_URL = os.environ.get(
    "OPENCODE_URL", "https://opencode.ai/zen/go/v1/chat/completions"
)
OPENCODE_MODEL = os.environ.get("OPENCODE_GO_MODEL", "deepseek-v4.1-flash")
OPENCODE_API_KEY = os.environ.get("OPENCODE_API_KEY", "")
_OPENCODE_SESSION = str(uuid.uuid4())

# Proveedor: "local" (Ollama) u "opencode".
PROVEEDOR = os.environ.get("MHUB_LLM_PROVIDER", "local").strip().lower()
PROVEEDOR_INTERPRETE = os.environ.get("MHUB_LLM_PROVIDER_INTERPRETE", "").strip().lower()
FALLBACK = os.environ.get("MHUB_LLM_FALLBACK", "").strip().lower()

OPCIONES = {
    "temperature": 0,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    "num_predict": 700,
}


def proveedor_para(tarea=None):
    if tarea in ("interprete", "agente") and PROVEEDOR_INTERPRETE:
        return PROVEEDOR_INTERPRETE
    return PROVEEDOR


def proveedor_actual(tarea=None):
    return proveedor_para(tarea)


def _post(url, payload):
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        raise Exception(
            "No se pudo conectar con Ollama. Verifica que Ollama esté ejecutándose."
        )
    except requests.exceptions.Timeout:
        raise Exception("El modelo tardó demasiado tiempo en responder.")
    except requests.exceptions.RequestException as error:
        raise Exception(f"Error al consultar el modelo: {error}")


# ------------------------------------------------------------
# Local (Ollama)
# ------------------------------------------------------------
def _local(prompt, system=None, json_mode=False):
    mensajes = []
    if system:
        mensajes.append({"role": "system", "content": system})
    mensajes.append({"role": "user", "content": prompt})

    payload = {
        "model": MODELO,
        "messages": mensajes,
        "stream": False,
        "options": {**OPCIONES, "temperature": 0} if json_mode else OPCIONES,
    }
    if json_mode:
        payload["format"] = "json"

    data = _post(OLLAMA_CHAT_URL, payload)
    return data["message"]["content"]


# ------------------------------------------------------------
# OpenCode Go (compatible con OpenAI)
# ------------------------------------------------------------
def _opencode(prompt, system=None, json_mode=False):
    if not OPENCODE_API_KEY:
        raise Exception(
            "Falta OPENCODE_API_KEY. Defínela en backend/.env para usar OpenCode."
        )

    mensajes = []
    if system:
        mensajes.append({"role": "system", "content": system})
    mensajes.append({"role": "user", "content": prompt})

    payload = {"model": OPENCODE_MODEL, "messages": mensajes, "temperature": 0}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {OPENCODE_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "mhub/1.0",
        "x-opencode-session": _OPENCODE_SESSION,
    }

    ultimo = None
    for _ in range(3):
        response = requests.post(OPENCODE_URL, headers=headers, json=payload, timeout=180)
        if response.status_code == 429:
            ultimo = response.text
            time.sleep(5)
            continue
        if response.status_code == 400 and json_mode:
            # reintentar sin response_format (algunos modelos no lo soportan)
            payload.pop("response_format", None)
            json_mode = False
            continue
        if response.status_code >= 400:
            raise Exception(
                f"OpenCode {response.status_code} (modelo={OPENCODE_MODEL}): "
                f"{response.text[:300]}"
            )
        return response.json()["choices"][0]["message"]["content"]

    raise Exception(f"OpenCode: respuesta no válida. {str(ultimo)[:200]}")


# ------------------------------------------------------------
# Despacho por proveedor
# ------------------------------------------------------------
def _ejecutar(proveedor, prompt, system, json_mode):
    if proveedor == "opencode":
        return _opencode(prompt, system, json_mode)
    return _local(prompt, system, json_mode)


def _preguntar(prompt, system=None, json_mode=False, tarea=None):
    proveedor = proveedor_para(tarea)
    try:
        return _ejecutar(proveedor, prompt, system, json_mode)
    except Exception as error:
        if FALLBACK and FALLBACK != proveedor:
            print(f"[llm] fallo {proveedor} ({error}); usando {FALLBACK}")
            return _ejecutar(FALLBACK, prompt, system, json_mode)
        raise


def preguntar_ollama(prompt, system=None):
    return _preguntar(prompt, system, json_mode=False, tarea="respuesta")


def preguntar_json(prompt, system=None, tarea="interprete"):
    return _preguntar(prompt, system, json_mode=True, tarea=tarea)


if __name__ == "__main__":
    print("Proveedor (respuesta):", proveedor_para("respuesta"))
    print("Proveedor (agente):", proveedor_para("agente"))
    print("Modelo opencode:", OPENCODE_MODEL)
