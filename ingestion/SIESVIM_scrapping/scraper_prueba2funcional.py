from playwright.sync_api import sync_playwright

def extraer_todo():

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # ENTRAR AL SISTEMA
        page.goto("https://sc.inegi.org.mx/SIESVIM1/")
        page.wait_for_load_state("networkidle")

        page.click("text=SITUACIÓN DE LA VIOLENCIA")
        page.wait_for_timeout(3000)

        page.click("text=Situación general")
        page.wait_for_timeout(3000)

        page.locator("text=Prevalencia").first.click()
        page.wait_for_timeout(5000)

        print("\n✅ Ya cargó la vista de tablas")

        
        # NIVEL 1 (TEMAS)
        page.locator("#listaTemas_label").click()
        page.wait_for_selector("#listaTemas_items li")

        temas = page.locator("#listaTemas_items li").all_text_contents()
        print("Temas:", temas)

        for tema in temas[:1]: #provisional, solo para ver si sí jala 

            print(f"\n=== TEMA: {tema} ===")

            page.locator("#listaTemas_label").click()
            page.wait_for_selector("#listaTemas_items li")

            page.locator("#listaTemas_items li", has_text=tema).click()
            page.wait_for_timeout(3000)


            #NIVEL 2 
            page.locator("#listaSubtemas_label").click()
            page.wait_for_selector("#listaSubtemas_items li")

            subtemas_elements = page.locator("#listaSubtemas_items li")

            subtemas = subtemas_elements.all_text_contents()

            print("Subtemas:", subtemas)

            for i, sub in enumerate(subtemas[:2]):

                print(f"\n--- SUBTEMA: {sub} ---")

                page.locator("#listaSubtemas_label").click()
                page.wait_for_selector("#listaSubtemas_items li")

                elemento = page.locator("#listaSubtemas_items li").nth(i)

                selected = elemento.get_attribute("aria-selected")

                if selected == "true":
                    print("✔ Ya estaba seleccionado, se omite click")
                else:
                    elemento.click()
                    page.wait_for_timeout(3000)


                #NIVEL 3 (INDICADORES)
                page.locator("#listaIndicadores_label").click()
                page.wait_for_selector("#listaIndicadores_items li")

                indicadores = page.locator("#listaIndicadores_items li").all_text_contents()
                print("Indicadores:", indicadores)

                for ind in indicadores[:2]:

                    print(f"\n>>> INDICADOR: {ind}")

                    page.locator("#listaIndicadores_label").click()
                    page.wait_for_selector("#listaIndicadores_items li")

                    page.get_by_role("option", name=ind, exact=True).click()
                    page.wait_for_timeout(4000)

                    #extraemos
                    tablas = page.locator("table")

                    if tablas.count() > 1:
                        tabla = tablas.nth(1).inner_text()

                        print("\nTabla preview:")
                        print(tabla[:200])

        input("\nENTER para cerrar")
        browser.close()


if __name__ == "__main__":
    extraer_todo()