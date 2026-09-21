import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import ejecutar_select
from consulta_mhub import responder


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
