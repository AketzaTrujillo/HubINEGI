import os
import asyncio
import pandas as pd
from twscrape import API

QUERIES = [
    '("violencia contra la mujer" OR "violencia de género" OR feminicidio OR "violencia familiar" OR "abuso sexual" OR acoso) '
    '(México OR CDMX OR "Estado de México" OR Jalisco OR Puebla OR "Nuevo León") lang:es'
]

RANGOS_2021 = [("2021-01-01", "2021-02-01")]
SALIDA_CSV = "x_mexico_violencia_mujer_2021.csv"

def limpiar_lista(val):
    return list(val) if val else []

async def recolectar_2021():
    api = API()

    username = os.getenv("X_USERNAME")
    password = os.getenv("X_PASSWORD")
    email = os.getenv("X_EMAIL")
    email_password = os.getenv("X_EMAIL_PASSWORD")

    print("USERNAME =", repr(username))
    print("EMAIL =", repr(email))
    print("PASSWORD cargada =", password is not None)
    print("EMAIL_PASSWORD cargada =", email_password is not None)

    if not username or not password or not email or not email_password:
        raise ValueError("Faltan variables de entorno")

    await api.pool.add_account(username, password, email, email_password)
    await api.pool.login_all()

    rows = []

    for base_query in QUERIES:
        for inicio, fin in RANGOS_2021:
            query = f"{base_query} since:{inicio} until:{fin}"
            print(f"Buscando: {query}")

            async for tweet in api.search(query, limit=100):
                texto = getattr(tweet, "rawContent", None) or getattr(tweet, "content", "")
                hashtags = [h.text if hasattr(h, "text") else str(h) for h in getattr(tweet, "hashtags", []) or []]
                menciones = [u.username if hasattr(u, "username") else str(u) for u in getattr(tweet, "mentionedUsers", []) or []]
                fecha = pd.to_datetime(tweet.date)

                rows.append({
                    "id_publicacion": str(tweet.id),
                    "fecha": fecha,
                    "anio": fecha.year,
                    "mes": fecha.month,
                    "texto": texto,
                    "usuario": getattr(tweet.user, "username", None) if getattr(tweet, "user", None) else None,
                    "url": getattr(tweet, "url", None),
                    "idioma": getattr(tweet, "lang", None),
                    "hashtags": limpiar_lista(hashtags),
                    "menciones": limpiar_lista(menciones),
                    "es_repost": bool(getattr(tweet, "retweetedTweet", None)),
                    "query_origen": query,
                    "plataforma": "X"
                })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["id_publicacion"]).sort_values("fecha")
        df.to_csv(SALIDA_CSV, index=False, encoding="utf-8-sig")

    print(f"Registros guardados: {len(df)}")
    print(f"Archivo: {SALIDA_CSV}")

if __name__ == "__main__":
    asyncio.run(recolectar_2021())