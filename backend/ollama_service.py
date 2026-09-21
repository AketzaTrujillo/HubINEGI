import os

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODELO = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

OPCIONES = {
    "temperature": 0,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    "num_predict": 500,
}


def _post(url, payload):
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        raise Exception(
            "No se pudo conectar con Ollama. "
            "Verifica que Ollama esté ejecutándose."
        )

    except requests.exceptions.Timeout:
        raise Exception(
            "Ollama tardó demasiado tiempo en responder."
        )

    except requests.exceptions.RequestException as error:
        raise Exception(
            f"Error al consultar Ollama: {error}"
        )


def preguntar_ollama(prompt, system=None):
    if system:
        data = _post(
            OLLAMA_CHAT_URL,
            {
                "model": MODELO,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": OPCIONES,
            },
        )
        return data["message"]["content"]

    data = _post(
        OLLAMA_URL,
        {
            "model": MODELO,
            "prompt": prompt,
            "stream": False,
            "options": OPCIONES,
        },
    )
    return data["response"]


if __name__ == "__main__":
    print(
        preguntar_ollama(
            "Responde en español: ¿qué es un indicador estadístico?"
        )
    )
