"""Clasificador de publicaciones críticas de X (objetivo 7).

Modelo de Deep Learning: TextCNN (red convolucional de texto) implementado en
PyTorch. El modelo se entrena con etiquetas débiles derivadas de
`tipo_contenido` y se valida contra un conjunto piloto anotado manualmente.

El módulo es tolerante a fallos: si PyTorch o el modelo no están disponibles,
`clasificar_publicaciones()` usa una regla de respaldo basada en el tipo de
contenido. Así el ETL puede seguir funcionando sin el modelo.

Uso:
    from clasificador_dl import clasificar_publicaciones
    resultados = clasificar_publicaciones(textos, tipos_contenido)
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Iterable, Optional

MODELO_VERSION = "textcnn-v1"
MAX_LEN = 128
EMBED_DIM = 100
NUM_FILTERS = 100
KERNEL_SIZES = (3, 4, 5)
DROPOUT = 0.3

PAD_TOKEN = "<pad>"
UNK_TOKEN = "<unk>"
PAD_ID = 0
UNK_ID = 1

TOKEN_RE = re.compile(r"[a-z0-9]+")

_AVISO_MODELO_AUSENTE = False


def _avisar_modelo_ausente() -> None:
    global _AVISO_MODELO_AUSENTE
    if _AVISO_MODELO_AUSENTE:
        return
    print(
        "[criticidad] Modelo no encontrado; usando regla de respaldo. "
        "Entrena con: cd ingestion/X && python entrenar_clasificador.py"
    )
    _AVISO_MODELO_AUSENTE = True


def normalizar_texto(texto: object) -> str:
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"https?://\S+", " ", texto)
    texto = re.sub(r"@\w+", " ", texto)
    texto = re.sub(r"#", "", texto)
    texto = re.sub(r"[^a-z0-9ñ\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def tokenizar(texto: object) -> list[str]:
    return TOKEN_RE.findall(normalizar_texto(texto))


def construir_vocab(textos: Iterable[str], min_freq: int = 2, max_size: int = 20000) -> dict[str, int]:
    from collections import Counter

    contador: Counter[str] = Counter()
    for texto in textos:
        contador.update(tokenizar(texto))

    vocab = {PAD_TOKEN: PAD_ID, UNK_TOKEN: UNK_ID}
    for palabra, frecuencia in contador.most_common(max_size):
        if frecuencia >= min_freq and palabra not in vocab:
            vocab[palabra] = len(vocab)
    return vocab


def codificar(texto: str, vocab: dict[str, int], max_len: int = MAX_LEN) -> list[int]:
    ids = [vocab.get(token, UNK_ID) for token in tokenizar(texto)[:max_len]]
    if len(ids) < max_len:
        ids.extend([PAD_ID] * (max_len - len(ids)))
    return ids


def guardar_vocab(vocab: dict[str, int], ruta: str) -> None:
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(vocab, archivo, ensure_ascii=False, indent=2)


def cargar_vocab(ruta: str) -> dict[str, int]:
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def _torch_disponible() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def construir_modelo(vocab_size: int):
    import torch.nn as nn

    class TextCNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, EMBED_DIM, padding_idx=PAD_ID)
            self.convs = nn.ModuleList(
                [nn.Conv1d(EMBED_DIM, NUM_FILTERS, k) for k in KERNEL_SIZES]
            )
            self.dropout = nn.Dropout(DROPOUT)
            self.fc = nn.Linear(NUM_FILTERS * len(KERNEL_SIZES), 1)

        def forward(self, x):  # type: ignore[no-untyped-def]
            import torch

            x = self.embedding(x)          # [B, L, E]
            x = x.transpose(1, 2)          # [B, E, L]
            x = [torch.relu(conv(x)).max(dim=2).values for conv in self.convs]
            x = torch.cat(x, dim=1)
            x = self.dropout(x)
            return self.fc(x).squeeze(1)

    return TextCNN()


def cargar_modelo(modelo_dir: Optional[str] = None):
    """Carga modelo, vocabulario y configuración. Devuelve None si no es posible."""
    if not _torch_disponible():
        return None

    import torch

    modelo_dir = modelo_dir or os.environ.get(
        "MHUB_MODELO_CRITICIDAD",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "clasificador_criticas"),
    )
    modelo_dir = os.path.abspath(modelo_dir)
    ruta_modelo = os.path.join(modelo_dir, "modelo.pt")
    ruta_vocab = os.path.join(modelo_dir, "vocab.json")
    ruta_config = os.path.join(modelo_dir, "config.json")

    if not (os.path.exists(ruta_modelo) and os.path.exists(ruta_vocab)):
        return None

    vocab = cargar_vocab(ruta_vocab)
    config = {}
    if os.path.exists(ruta_config):
        with open(ruta_config, "r", encoding="utf-8") as archivo:
            config = json.load(archivo)

    modelo = construir_modelo(len(vocab))
    try:
        estado = torch.load(ruta_modelo, map_location="cpu", weights_only=True)
    except TypeError:
        estado = torch.load(ruta_modelo, map_location="cpu")
    modelo.load_state_dict(estado)
    modelo.eval()
    return modelo, vocab, config


def predecir_probs(
    textos: Iterable[str],
    modelo_dir: Optional[str] = None,
    lote: int = 64,
) -> Optional[list[float]]:
    """Devuelve probabilidades de crítica o None si el modelo no está disponible."""
    cargado = cargar_modelo(modelo_dir)
    if cargado is None:
        return None

    import torch

    modelo, vocab, config = cargado
    max_len = int(config.get("max_len", MAX_LEN))
    textos = list(textos)
    probabilidades: list[float] = []

    with torch.no_grad():
        for inicio in range(0, len(textos), lote):
            bloque = textos[inicio : inicio + lote]
            x = torch.tensor(
                [codificar(texto, vocab, max_len) for texto in bloque],
                dtype=torch.long,
            )
            logits = modelo(x)
            probabilidades.extend(torch.sigmoid(logits).cpu().tolist())

    return probabilidades


def texto_util(texto: str) -> bool:
    """Descarta publicaciones sin texto real (solo URL, 'Image', 'Video', etc.)."""
    tokens = TOKEN_RE.findall(normalizar_texto(texto))
    if len(tokens) < 5:
        return False
    ruido = {"image", "video", "quote", "show", "more", "translate", "post", "replying", "to"}
    return not all(token in ruido for token in tokens)


NO_GENERO = (
    "cartel", "cjng", "narcotrafico", "sicario", "homicidio doloso",
    "crimen organizado",
)
GENERO = (
    "mujer", "mujeres", "feminicidio", "pareja", "esposa", "esposo",
    "novia", "novio", "hija", "hijo", "familiar", "sexual", "acoso",
    "abuso", "agredida", "agredido", "asesinada", "asesinado",
    "violencia de genero", "violencia familiar",
)


def es_violencia_de_genero(texto: str) -> bool:
    """Filtro de seguridad: evita crimen organizado sin componente de género."""
    normalizado = normalizar_texto(texto)
    if any(marca in normalizado for marca in NO_GENERO) and not any(
        marca in normalizado for marca in GENERO
    ):
        return False
    return True


def regla_critica(texto: str, tipo_contenido: Optional[str] = None) -> int:
    """Respaldo determinista cuando el modelo no está disponible."""
    if tipo_contenido in ("noticia", "denuncia"):
        return 1
    normalizado = normalizar_texto(texto)
    marcadores = (
        "detuvieron", "detenido", "detenida", "fiscalia", "denuncia",
        "denuncio", "sentencia", "vinculan a proceso", "rescatan",
        "rescate", "localizada", "localizado", "feminicidio", "asesinada",
        "asesinado", "agredida", "agredido", "violencia familiar",
    )
    return 1 if any(m in normalizado for m in marcadores) else 0


def clasificar_publicaciones(
    textos: Iterable[str],
    tipos_contenido: Optional[Iterable[Optional[str]]] = None,
    modelo_dir: Optional[str] = None,
    umbral: Optional[float] = None,
) -> list[dict]:
    """Clasifica una lista de publicaciones y devuelve es_critica/prob_critica."""
    textos = [str(t or "") for t in textos]
    tipos = list(tipos_contenido) if tipos_contenido is not None else [None] * len(textos)
    if len(tipos) < len(textos):
        tipos.extend([None] * (len(textos) - len(tipos)))

    cargado = cargar_modelo(modelo_dir)
    if cargado is None:
        _avisar_modelo_ausente()
        return [
            {
                "es_critica": "si"
                if texto_util(texto)
                and es_violencia_de_genero(texto)
                and regla_critica(texto, tipo)
                else "no",
                "prob_critica": None,
                "modelo_version": "regla-respaldo",
            }
            for texto, tipo in zip(textos, tipos)
        ]

    _, _, config = cargado
    umbral = float(umbral if umbral is not None else config.get("umbral", 0.5))
    probabilidades = predecir_probs(textos, modelo_dir=modelo_dir)
    if probabilidades is None:
        _avisar_modelo_ausente()
        return [
            {
                "es_critica": "si"
                if texto_util(texto)
                and es_violencia_de_genero(texto)
                and regla_critica(texto, tipo)
                else "no",
                "prob_critica": None,
                "modelo_version": "regla-respaldo",
            }
            for texto, tipo in zip(textos, tipos)
        ]

    resultados = []
    for texto, prob in zip(textos, probabilidades):
        if not texto_util(texto) or not es_violencia_de_genero(texto):
            resultados.append(
                {
                    "es_critica": "no",
                    "prob_critica": None,
                    "modelo_version": MODELO_VERSION,
                }
            )
        else:
            resultados.append(
                {
                    "es_critica": "si" if prob >= umbral else "no",
                    "prob_critica": round(float(prob), 4),
                    "modelo_version": MODELO_VERSION,
                }
            )
    return resultados
