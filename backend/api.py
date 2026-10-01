import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import ejecutar_select
from consulta_mhub import responder
from panel import filtros as panel_filtros, construir as panel_construir


app = FastAPI(title="MHub API", version="0.1.0")

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


@app.get("/salud")
def salud():
    return {"estado": "ok", "servicio": "MHub API"}


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
