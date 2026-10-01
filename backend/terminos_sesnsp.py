"""Mapeo determinista de términos de incidencia delictiva / 911 al indicador SESNSP."""
import re
import unicodedata

from database import ejecutar_select

TERMINOS = [
    (r"llamadas?\s*(?:911|9-1-1).*violencia contra (?:la )?mujer", "SESNSP_llamadas_911_violencia_contra_mujer"),
    (r"llamadas?\s*(?:911|9-1-1).*abuso sexual", "SESNSP_llamadas_911_abuso_sexual"),
    (r"llamadas?\s*(?:911|9-1-1).*acoso", "SESNSP_llamadas_911_acoso_hostigamiento_sexual"),
    (r"llamadas?\s*(?:911|9-1-1).*violaci", "SESNSP_llamadas_911_violacion"),
    (r"llamadas?\s*(?:911|9-1-1).*pareja", "SESNSP_llamadas_911_violencia_pareja"),
    (r"llamadas?\s*(?:911|9-1-1).*familiar", "SESNSP_llamadas_911_violencia_familiar"),
    (r"llamadas?\s*(?:911|9-1-1)", "SESNSP_llamadas_911_violencia_contra_mujer"),
    (r"feminicidios?", "SESNSP_victimas_mujeres_feminicidio"),
    (r"homicidios? dolosos?", "SESNSP_victimas_mujeres_homicidio_doloso"),
    (r"homicidios? culposos?", "SESNSP_victimas_mujeres_homicidio_culposo"),
    (r"lesiones? dolosas?", "SESNSP_victimas_mujeres_lesiones_dolosas"),
    (r"lesiones? culposas?", "SESNSP_victimas_mujeres_lesiones_culposas"),
    (r"secuestros?", "SESNSP_victimas_mujeres_secuestro"),
    (r"traficos? de menores", "SESNSP_victimas_mujeres_trafico_menores"),
    (r"extorsion(?:es)?", "SESNSP_victimas_mujeres_extorsion"),
    (r"corrupcion(?:es)? de menores", "SESNSP_victimas_mujeres_corrupcion_menores"),
    (r"trata de personas", "SESNSP_victimas_mujeres_trata_personas"),
    (r"delitos? de violencia familiar", "SESNSP_delitos_violencia_familiar"),
    (r"delitos? de violencia de genero", "SESNSP_delitos_violencia_genero"),
    (r"delitos? de violacion|violacion simple|violacion equiparada", "SESNSP_delitos_violacion_simple_equiparada"),
]


def _norm(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def indicador_id(texto):
    """Devuelve id_indicador del SESNSP que corresponde al texto, o None."""
    n = _norm(texto)
    codigo = None
    for patron, cod in TERMINOS:
        if re.search(patron, n):
            codigo = cod
            break
    if not codigo:
        return None
    try:
        filas = ejecutar_select(
            "SELECT id_indicador FROM dim_indicador WHERE codigo = %s",
            params=(codigo,),
        )
        return filas[0]["id_indicador"] if filas else None
    except Exception:
        return None