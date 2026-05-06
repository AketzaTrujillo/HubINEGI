from playwright.sync_api import sync_playwright
import json
import os

def parsear_tabla(tabla_texto):
    lineas = [l.strip() for l in tabla_texto.split("\n") if l.strip() != ""]

    # separar encabezados y datos
    columnas = []
    filas = []

    i = 0

    # detectar encabezado (hasta que empiecen datos reales)
    while i < len(lineas) and not any(char.isdigit() for char in lineas[i]):
        columnas.append(lineas[i])
        i += 1

    # procesar filas
    for linea in lineas[i:]:
        partes = linea.split()
        filas.append(partes)

    return {
        "columnas": columnas,
        "filas": filas
    }


def extraer_todo():

    resultados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()


        #ENTRAR
        page.goto("https://sc.inegi.org.mx/SIESVIM1/")
        page.wait_for_load_state("networkidle")

        page.click("text=SITUACIÓN DE LA VIOLENCIA")
        page.wait_for_timeout(3000)

        page.click("text=Situación general")
        page.wait_for_timeout(3000)

        page.locator("text=Prevalencia").first.click()
        page.wait_for_timeout(5000)

        print("Vista lista")


        #NIVEL 1
        page.locator("#listaTemas_label").click()
        page.wait_for_selector("#listaTemas_items li")

        temas_elements = page.locator("#listaTemas_items li")
        temas = temas_elements.all_text_contents()

        print("Temas:", temas)

        for i, tema in enumerate(temas[:2]):

            print(f"\n=== TEMA: {tema} ===")

            page.locator("#listaTemas_label").click()
            page.wait_for_selector("#listaTemas_items li")

            elemento = page.locator("#listaTemas_items li").nth(i)

            selected = elemento.get_attribute("aria-selected")

            if selected == "true":
                print("✔ Tema ya seleccionado, se omite click")
            else:
                elemento.click()
                page.wait_for_timeout(3000)


            #NIVEL 2 (SUBTEMAS CORREGIDO)
            # -------------------------
            page.locator("#listaSubtemas_label").click()
            page.wait_for_selector("#listaSubtemas_items li")

            subtemas_elements = page.locator("#listaSubtemas_items li")
            subtemas = subtemas_elements.all_text_contents()

            for i, sub in enumerate(subtemas[:5]):

                print(f"\n--- SUBTEMA: {sub} ---")

                # abrir dropdown
                page.locator("#listaSubtemas_label").click()
                page.wait_for_selector("#listaSubtemas_items li")

                elemento = page.locator("#listaSubtemas_items li").nth(i)
                selected = elemento.get_attribute("aria-selected")

                if selected != "true":
                    elemento.click()
                    page.wait_for_timeout(3000)
                else:
                    print("✔ Subtema ya seleccionado")

                # cerrar cualquier dropdown 
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

                # asegurar que el siguiente elemento está listo
                page.wait_for_selector("#listaIndicadores_label")


                # -------------------------
                # 🔥 NIVEL 3 (INDICADORES CORREGIDO)
                # -------------------------
                page.locator("#listaIndicadores_label").click()
                page.wait_for_selector("#listaIndicadores_items li")

                indicadores = page.locator("#listaIndicadores_items li").all_text_contents()

                print("Indicadores:", indicadores)

                for ind in indicadores:

                    print(f"\n>>> INDICADOR: {ind}")

                    # 🔥 cerrar overlays antes de interactuar otra vez
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(300)

                    # abrir dropdown SIEMPRE limpio
                    page.locator("#listaIndicadores_label").click()
                    page.wait_for_selector("#listaIndicadores_items li")

                    elementos = page.locator("#listaIndicadores_items li")

                    encontrado = False

                    for j in range(elementos.count()):
                        el = elementos.nth(j)
                        texto = el.inner_text().strip()

                        if texto == ind.strip():

                            selected = el.get_attribute("aria-selected")

                            if selected == "true":
                                print("✔ Indicador ya seleccionado")
                            else:
                                el.click()
                                page.wait_for_timeout(4000)

                            encontrado = True
                            break

                    if not encontrado:
                        print("⚠️ No encontrado:", ind)
                        continue

                    # -------------------------
                    # 🔥 EXTRAER TABLA
                    # -------------------------
                    tablas = page.locator("table")

                    if tablas.count() > 1:
                        tabla_texto = tablas.nth(1).inner_text()

                        datos = parsear_tabla(tabla_texto)

                        resultados.append({
                            "tema": tema,
                            "subtema": sub,
                            "indicador": ind,
                            "tabla": datos
                        })

                        print(f"📦 Total acumulado: {len(resultados)}")

    #se supone que aquí ya guardamos los json
    os.makedirs("data/processed", exist_ok=True)

    with open("data/processed/datos.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=4, ensure_ascii=False)

    print("\n✅ JSON guardado en data/processed/datos.json")

    # VALIDACIÓN AUTOMÁTICA
    print("\n📊 RESUMEN:")

    print("Total de tablas:", len(resultados))

    # contar por tema
    conteo_temas = {}
    for r in resultados:
        tema = r["tema"]
        conteo_temas[tema] = conteo_temas.get(tema, 0) + 1

    print("\nTablas por tema:")
    for k, v in conteo_temas.items():
        print(f"{k}: {v}")

    # verificar tablas vacías
    vacios = [r for r in resultados if len(r["tabla"]["filas"]) == 0]
    print("\nTablas vacías:", len(vacios))

    # ver ejemplo de datos
    if len(resultados) > 0:
        print("\n🔎 EJEMPLO:")
        print(json.dumps(resultados[0], indent=2, ensure_ascii=False)[:1000])

    # combinaciones únicas
    combinaciones = set()
    for r in resultados:
        combinaciones.add((r["tema"], r["subtema"], r["indicador"]))

    print("\nCombinaciones únicas:", len(combinaciones))


if __name__ == "__main__":
    extraer_todo()
    
    
