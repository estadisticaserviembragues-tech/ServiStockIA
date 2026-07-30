from rapidfuzz import fuzz
import unicodedata
import re


def normalizar(texto):
    texto = str(texto).lower().strip()

    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )

    texto = re.sub(r"[^a-z0-9\- ]+", " ", texto)
    texto = " ".join(texto.split())

    return texto


def limpiar_consulta(texto):
    texto = normalizar(texto)

    palabras_ignorar = {
        "donde", "esta", "estan", "hay",
        "el", "la", "los", "las",
        "de", "del", "para", "un", "una",
        "quiero", "necesito", "busco",
        "buscar", "muestrame", "dame",
        "tengo", "tienes", "cuantos",
        "cuantas", "cantidad", "producto",
        "productos", "articulo", "articulos",
        "tiene", "tienen"
    }

    palabras = texto.split()

    palabras_limpias = [
        palabra
        for palabra in palabras
        if palabra not in palabras_ignorar
    ]

    return " ".join(palabras_limpias)


def buscar_productos(df, consulta):

    consulta_limpia = limpiar_consulta(consulta)

    if not consulta_limpia:
        return []

    palabras_busqueda = consulta_limpia.split()

    resultados = []

    for _, fila in df.iterrows():

        codigo = normalizar(fila["CODIGO"])
        articulo = normalizar(fila["ARTICULO"])

        texto_producto = f"{codigo} {articulo}"

        # Código exacto
        if consulta_limpia == codigo:

            producto = fila.to_dict()
            producto["PUNTAJE"] = 1000
            resultados.append(producto)

            continue

        # Código parcial
        if consulta_limpia in codigo:

            producto = fila.to_dict()
            producto["PUNTAJE"] = 900
            resultados.append(producto)

            continue

        palabras_producto = texto_producto.split()

        puntajes = []

        for palabra_busqueda in palabras_busqueda:

            # Coincidencia exacta
            if palabra_busqueda in palabras_producto:

                puntajes.append(100)

            else:

                # Buscar palabra más parecida
                mejor_puntaje = max(
                    (
                        fuzz.ratio(
                            palabra_busqueda,
                            palabra_producto
                        )
                        for palabra_producto
                        in palabras_producto
                    ),
                    default=0
                )

                puntajes.append(mejor_puntaje)

        # Todas las palabras deben tener
        # una similitud razonable
        if puntajes and min(puntajes) >= 65:

            puntaje_final = sum(puntajes) / len(puntajes)

            producto = fila.to_dict()

            producto["PUNTAJE"] = puntaje_final

            resultados.append(producto)

    resultados.sort(
        key=lambda x: x["PUNTAJE"],
        reverse=True
    )

    return resultados