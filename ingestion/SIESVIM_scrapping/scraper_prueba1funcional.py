from playwright.sync_api import sync_playwright

def extraer_tabla():

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        #URL directa de la tabla
        page.goto("https://sc.inegi.org.mx/SIESVIM1/paginas/contenido.jsf?t=24&s=49&c=49&i=551")

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        # obtener todas las tablas
        tablas = page.locator("table")

        print("Número de tablas:", tablas.count())

        tabla_texto = tablas.nth(1).inner_text()

        print("\n TEXTO ORIGINAL \n")
        print(tabla_texto)

        
        lineas = tabla_texto.split("\n")

        # limpiar líneas vacías
        lineas = [l.strip() for l in lineas if l.strip() != ""]

        #quitar encabezado (ajustable)
        lineas = lineas[5:]

        datos = []

        for linea in lineas:
            partes = linea.split()

            # evitar errores
            if len(partes) < 5:
                continue

            #nota de que el estado puede tener varias palabras
            estado = " ".join(partes[:-4])

            valores = partes[-4:]
            anios = [2006, 2011, 2016, 2021]

            for i in range(4):
                try:
                    valor = float(valores[i])
                except:
                    continue

                datos.append({
                    "estado": estado,
                    "anio": anios[i],
                    "valor": valor
                })

        #resultados
        print("\n DATOS PROCESADOS \n")
        for d in datos[:10]:
            print(d)

        print(f"\nTotal de registros: {len(datos)}")

        input("\nPresiona ENTER para cerrar...")
        browser.close()



if __name__ == "__main__":
    extraer_tabla()