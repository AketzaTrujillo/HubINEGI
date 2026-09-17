import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.2"


def preguntar_ollama(prompt):
    payload = {
        "model": MODELO,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        return data["response"]

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


if __name__ == "__main__":
    respuesta = preguntar_ollama(
        "Responde en español: ¿qué es un indicador estadístico?"
    )

    print(respuesta)