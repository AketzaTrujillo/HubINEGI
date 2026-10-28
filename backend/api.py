import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import ejecutar_select
from consulta_mhub import responder
from panel import filtros as panel_filtros, construir as panel_construir
import ollama_service


app = FastAPI(title="MHub API", version="0.1.0")


@app.on_event("startup")
def _precargar_corpus():
    """Precarga opcional del índice/modelo para evitar la primera consulta lenta."""
    if os.environ.get("MHUB_PRECARGAR", "0").strip().lower() not in ("1", "true", "si"):
        return
    version = (os.environ.get("MHUB_CORPUS_VERSION") or "v1").strip().lower()
    try:
        if version == "v2":
            import corpus_search_v2
            corpus_search_v2.precargar()
        elif os.environ.get("MHUB_CORPUS_MODE", "fulltext").lower() != "fulltext":
            import corpus_search
            corpus_search.cargar_indice()
            corpus_search.cargar_modelo()
    except Exception as error:
        print(f"[api] precarga de corpus falló: {error}")

_origins = os.environ.get("MHUB_CORS_ORIGINS", "*").strip()
_allow_origins = ["*"] if _origins == "*" else [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConsultaEntrada(BaseModel):
    pregunta: str
    contexto: Optional[dict] = None


class PanelEntrada(BaseModel):
    fuente: str
    entidad: Optional[str] = None
    anio: Optional[Any] = None
    tipo: Optional[str] = None
    delito: Optional[str] = None


class ConfigExperimentoEntrada(BaseModel):
    recuperacion: Optional[str] = None
    llm: Optional[str] = None


CONFIG_RECUPERACION = {
    "v1_fulltext": ("v1", "fulltext"),
    "v1_hybrid": ("v1", "hybrid"),
    "v1_embedding": ("v1", "embedding"),
    "v2_hybrid": ("v2", "hybrid"),
    "v2_bm25": ("v2", "bm25"),
    "v2_embedding": ("v2", "embedding"),
    "v2_rerank": ("v2", "hybrid_rerank"),
}


def _clave_recuperacion(version, modo):
    version = (version or "v1").strip().lower()
    modo = (modo or "fulltext").strip().lower()
    if version == "v2":
        return {
            "hybrid": "v2_hybrid",
            "bm25": "v2_bm25",
            "embedding": "v2_embedding",
            "hybrid_rerank": "v2_rerank",
        }.get(modo, "v2_hybrid")
    return {
        "fulltext": "v1_fulltext",
        "hybrid": "v1_hybrid",
        "embedding": "v1_embedding",
    }.get(modo, "v1_fulltext")


def _config_experimento_actual():
    version = (os.environ.get("MHUB_CORPUS_VERSION") or "v1").strip().lower()
    if version == "v2":
        modo = (os.environ.get("MHUB_V2_MODE") or "hybrid").strip().lower()
    else:
        modo = (os.environ.get("MHUB_CORPUS_MODE") or "fulltext").strip().lower()
    return {
        "recuperacion": _clave_recuperacion(version, modo),
        "version": version,
        "modo": modo,
        "llm": ollama_service.proveedor_actual("respuesta"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
    }


@app.get("/salud")
def salud():
    return {"estado": "ok", "servicio": "MHub API"}


@app.get("/corpus/estado")
def corpus_estado():
    """Diagnóstico de la versión y modo de recuperación activos."""
    version = (os.environ.get("MHUB_CORPUS_VERSION") or "v1").strip().lower()
    try:
        if version == "v2":
            import corpus_search_v2
            return {"version": "v2", **corpus_search_v2.estado()}
        import corpus_search
        return {
            "version": "v1",
            "modo_por_defecto": corpus_search.modo_por_defecto(),
            **corpus_search.estado_indice(),
        }
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error))


@app.get("/config/experimento")
def config_experimento():
    """Configuración de prueba actual (recuperación y proveedor de LLM)."""
    return _config_experimento_actual()


@app.post("/config/experimento")
def cambiar_config_experimento(entrada: ConfigExperimentoEntrada, request: Request):
    """Cambia recuperación/LLM en caliente. Solo para pruebas locales."""
    host = (request.client.host if request.client else "") or ""
    if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(status_code=403, detail="Solo disponible en localhost.")

    if entrada.recuperacion and entrada.recuperacion not in CONFIG_RECUPERACION:
        raise HTTPException(status_code=400, detail="Modo de recuperación no válido.")
    if entrada.llm and entrada.llm not in ("local", "opencode"):
        raise HTTPException(status_code=400, detail="Proveedor de LLM no válido.")

    anterior = _config_experimento_actual()
    try:
        if entrada.recuperacion:
            version, modo = CONFIG_RECUPERACION[entrada.recuperacion]
            os.environ["MHUB_CORPUS_VERSION"] = version
            if version == "v2":
                os.environ["MHUB_V2_MODE"] = modo
                import corpus_search_v2
                if modo == "bm25":
                    corpus_search_v2.cargar_bm25()
                elif modo == "embedding":
                    corpus_search_v2.cargar_indice_v2()
                    corpus_search_v2.cargar_modelo_v2()
                else:
                    corpus_search_v2.precargar()
                    if modo == "hybrid_rerank":
                        corpus_search_v2.cargar_reranker()
            else:
                os.environ["MHUB_CORPUS_MODE"] = modo

        if entrada.llm:
            ollama_service.set_proveedor(entrada.llm)
    except Exception as error:
        # Revertir la configuración anterior si la precarga falla.
        os.environ["MHUB_CORPUS_VERSION"] = anterior["version"]
        if anterior["version"] == "v2":
            os.environ["MHUB_V2_MODE"] = anterior["modo"]
        else:
            os.environ["MHUB_CORPUS_MODE"] = anterior["modo"]
        ollama_service.set_proveedor(anterior["llm"])
        raise HTTPException(status_code=503, detail=f"No se pudo aplicar: {error}")

    return {"ok": True, **_config_experimento_actual()}


@app.get("/estado")
def estado():
    try:
        filas = ejecutar_select(
            """
            SELECT
                (SELECT COUNT(*) FROM indicadores_endireh)   AS endireh,
                (SELECT COUNT(*) FROM indicadores_siesvim)   AS siesvim,
                (SELECT COUNT(*) FROM indicadores_inmujeres) AS inmujeres,
                (SELECT COUNT(*) FROM registros)             AS x
            """
        )
        return {"conectado": True, "conteos": filas[0] if filas else {}}
    except Exception as error:
        return {"conectado": False, "detalle": str(error)}


@app.post("/consulta")
def consulta(entrada: ConsultaEntrada):
    pregunta = (entrada.pregunta or "").strip()

    if not pregunta:
        raise HTTPException(status_code=400, detail="La pregunta está vacía.")

    contexto = entrada.contexto or None

    try:
        return responder(pregunta, contexto)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Error del asistente: {error}")


@app.get("/filtros")
def filtros():
    try:
        return panel_filtros()
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Error al cargar filtros: {error}")


@app.post("/panel")
def panel(entrada: PanelEntrada):
    try:
        data = panel_construir(
            entrada.fuente, entrada.entidad, entrada.anio,
            entrada.tipo, entrada.delito,
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Error al construir el panel: {error}")

    if data is None:
        raise HTTPException(status_code=400, detail="Fuente no válida.")
    return data
