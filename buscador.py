import re
import unicodedata
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from config import MAX_RESULTADOS
from database import cargar_inventario_completo

try:
    from database_backup import cargar_medidas_embragues
except ImportError:
    cargar_medidas_embragues = None


# ==================================================
# NORMALIZACIÓN DE TEXTO
# ==================================================

def normalizar(texto: Any) -> str:
    """
    Prepara un texto para realizar comparaciones.

    Ejemplos:
    - "¿Dónde está?" -> "donde esta"
    - "YQ-4908" -> "yq-4908"
    """

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    texto = re.sub(
        r"[^a-z0-9\- ]+",
        " ",
        texto,
    )

    return " ".join(
        texto.split()
    )


def limpiar_codigo(texto: Any) -> str:
    """
    Elimina espacios, guiones y símbolos del código.

    Ejemplos:
    - YQ-4908 -> yq4908
    - YQ 4908 -> yq4908
    """

    return re.sub(
        r"[^a-z0-9]",
        "",
        normalizar(texto),
    )


# ==================================================
# SINÓNIMOS Y ERRORES FRECUENTES
# ==================================================

SINONIMOS = {
    # Embrague
    "embrage": "embrague",
    "embreague": "embrague",
    "embraguee": "embrague",
    "clutch": "embrague",

    # Discos
    "disko": "disco",
    "diskos": "disco",
    "discos": "disco",
    "disc": "disco",

    # Pastillas
    "pastilla": "past",
    "pastillas": "past",
    "past": "past",

    # Zapatas
    "zapatas": "zapata",

    # Rodamientos
    "rulimanes": "ruliman",
    "rodamiento": "ruliman",
    "rodamientos": "ruliman",
    "balinera": "ruliman",
    "balineras": "ruliman",

    # Volantes
    "volantes": "volante",

    # Vehículos escritos de distintas maneras
    "bt 50": "bt50",
    "bt-50": "bt50",
    "bt 50": "bt50",

    "t 60": "t60",
    "t-60": "t60",

    "d max": "dmax",
    "d-max": "dmax",

    "grand vitara": "grandvitara",

    # Errores frecuentes de marcas o vehículos
    "toyta": "toyota",
    "chevolet": "chevrolet",
    "chevrolet": "chevrolet",
    "hyunday": "hyundai",
    "hiunday": "hyundai",
    "wolkswagen": "volkswagen",
}


def aplicar_sinonimos(texto: Any) -> str:
    """
    Corrige palabras frecuentes antes de buscar.
    """

    resultado = normalizar(texto)

    # Se ordenan las frases por longitud para reemplazar
    # primero las expresiones más largas.
    sinonimos_ordenados = sorted(
        SINONIMOS.items(),
        key=lambda elemento: len(elemento[0]),
        reverse=True,
    )

    for palabra_original, palabra_correcta in sinonimos_ordenados:
        resultado = resultado.replace(
            palabra_original,
            palabra_correcta,
        )

    return resultado


# ==================================================
# LIMPIEZA DE LA CONSULTA
# ==================================================

PALABRAS_IGNORADAS = {
    "a",
    "al",
    "algo",
    "dame",
    "donde",
    "esta",
    "estan",
    "hay",
    "quiero",
    "necesito",
    "busco",
    "buscar",
    "muestrame",
    "mostrar",

    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",

    "de",
    "del",
    "para",
    "por",
    "en",
    "mi",

    "tengo",
    "tienes",
    "tiene",
    "tienen",

    "cuanto",
    "cuantos",
    "cuanta",
    "cuantas",

    "cantidad",
    "stock",
    "total",

    "producto",
    "productos",
    "articulo",
    "articulos",

    "bodega",
    "inventario",

    "solo",
    "solamente",
}


def limpiar_consulta(consulta: Any) -> str:
    """
    Elimina palabras conversacionales que no sirven
    para identificar el producto.
    """

    consulta_normalizada = aplicar_sinonimos(
        consulta
    )

    palabras = consulta_normalizada.split()

    palabras_utiles = [
        palabra
        for palabra in palabras
        if palabra not in PALABRAS_IGNORADAS
    ]

    return " ".join(
        palabras_utiles
    )


# ==================================================
# CONVERSIÓN DE CANTIDADES
# ==================================================

def convertir_cantidad(valor: Any) -> float:
    """
    Convierte cantidades provenientes de Excel
    en números utilizables.
    """

    try:
        texto = str(valor).strip()
        texto = texto.replace(" ", "")
        texto = texto.replace(",", ".")

        return float(texto)

    except (ValueError, TypeError):
        return 0.0


# ==================================================
# DETECCIÓN DE INTENCIÓN
# ==================================================

def detectar_intencion(consulta: str) -> str:
    """
    Determina qué desea el usuario.

    Devuelve:
    - "cantidad"
    - "ubicacion"
    - "buscar"
    """

    texto = normalizar(
        consulta
    )

    palabras = set(
        texto.split()
    )

    palabras_cantidad = {
        "cuanto",
        "cuantos",
        "cuanta",
        "cuantas",
        "cantidad",
        "stock",
        "total",
    }

    frases_ubicacion = {
        "donde",
        "ubicacion",
        "ubicaciones",
    }

    if palabras.intersection(
        palabras_cantidad
    ):
        return "cantidad"

    if palabras.intersection(
        frases_ubicacion
    ):
        return "ubicacion"

    if (
        "en que bodega" in texto
        or "en que ubicacion" in texto
    ):
        return "ubicacion"

    return "buscar"


# ==================================================
# DETECTAR ALMACÉN
# ==================================================

def detectar_almacen(
    consulta: str,
) -> str | None:
    """
    Detecta el almacén mencionado por el usuario.

    Importante:
    NORTE FGS se comprueba antes de NORTE.
    """

    texto = normalizar(
        consulta
    )

    if "norte fgs" in texto:
        return "NORTE FGS"

    if "norte" in texto:
        return "NORTE"

    return None


# ==================================================
# EXTRAER POSIBLES CÓDIGOS DE UNA CONSULTA
# ==================================================

def extraer_posibles_codigos(
    consulta: str,
) -> set[str]:
    """
    Extrae palabras que podrían representar códigos.

    Ejemplo:
    "cuanto tengo de YQ4908"
    devuelve {"cuanto", "tengo", "de", "yq4908"}.

    Luego se comparan con los códigos reales.
    """

    texto = normalizar(
        consulta
    )

    palabras = texto.split()

    return {
        limpiar_codigo(palabra)
        for palabra in palabras
        if limpiar_codigo(palabra)
    }


# ==================================================
# BÚSQUEDA EXACTA POR CÓDIGO
# ==================================================

def buscar_codigo_exacto(
    df: pd.DataFrame,
    consulta: str,
) -> pd.DataFrame:
    """
    Busca un código exacto, incluso dentro de una frase.
    """

    posibles_codigos = extraer_posibles_codigos(
        consulta
    )

    mascara = df["CODIGO"].apply(
        limpiar_codigo
    ).isin(
        posibles_codigos
    )

    return df[
        mascara
    ].copy()


# ==================================================
# BÚSQUEDA PARCIAL POR CÓDIGO
# ==================================================

def buscar_codigo_parcial(
    df: pd.DataFrame,
    consulta: str,
) -> pd.DataFrame:
    """
    Permite que 4908 encuentre YQ4908.

    Solo se utiliza cuando la consulta limpia
    contiene una sola palabra.
    """

    consulta_limpia = limpiar_consulta(
        consulta
    )

    palabras = consulta_limpia.split()

    if len(palabras) != 1:
        return df.iloc[0:0].copy()

    codigo_consulta = limpiar_codigo(
        palabras[0]
    )

    if len(codigo_consulta) < 3:
        return df.iloc[0:0].copy()

    mascara = df["CODIGO"].apply(
        limpiar_codigo
    ).str.contains(
        codigo_consulta,
        regex=False,
    )

    return df[
        mascara
    ].copy()


# ==================================================
# CALCULAR SIMILITUD DE UNA FILA
# ==================================================

def calcular_puntaje_producto(
    fila: pd.Series,
    palabras_busqueda: list[str],
) -> float:
    """
    Calcula qué tan relacionado está un producto
    con la búsqueda del usuario.
    """

    codigo = aplicar_sinonimos(
        fila.get(
            "CODIGO",
            "",
        )
    )

    articulo = aplicar_sinonimos(
        fila.get(
            "ARTICULO",
            "",
        )
    )

    marca = aplicar_sinonimos(
        fila.get(
            "MARCA",
            "",
        )
    )

    almacen = aplicar_sinonimos(
        fila.get(
            "ALMACEN",
            "",
        )
    )

    ubicacion = aplicar_sinonimos(
        fila.get(
            "UBICACION",
            "",
        )
    )

    texto_producto = " ".join(
        [
            codigo,
            articulo,
            marca,
            almacen,
            ubicacion,
        ]
    )

    palabras_producto = (
        texto_producto.split()
    )

    puntajes_palabras = []

    for palabra_busqueda in palabras_busqueda:

        # Coincidencia exacta
        if palabra_busqueda in palabras_producto:
            puntajes_palabras.append(
                100.0
            )
            continue

        # Coincidencia parcial
        coincidencia_parcial = any(
            (
                palabra_busqueda
                in palabra_producto
                or
                palabra_producto
                in palabra_busqueda
            )
            for palabra_producto in palabras_producto
            if (
                len(palabra_busqueda) >= 3
                and
                len(palabra_producto) >= 3
            )
        )

        if coincidencia_parcial:
            puntajes_palabras.append(
                95.0
            )
            continue

        # Coincidencia aproximada
        mejor_puntaje = max(
            (
                fuzz.ratio(
                    palabra_busqueda,
                    palabra_producto,
                )
                for palabra_producto in palabras_producto
            ),
            default=0.0,
        )

        puntajes_palabras.append(
            float(mejor_puntaje)
        )

    if not puntajes_palabras:
        return 0.0

    coincidencias_buenas = sum(
        puntaje >= 70
        for puntaje in puntajes_palabras
    )

    porcentaje_coincidencia = (
        coincidencias_buenas
        /
        len(puntajes_palabras)
    )

    # Exigimos que al menos el 75 % de las palabras
    # importantes estén relacionadas.
    if porcentaje_coincidencia < 0.75:
        return 0.0

    return (
        sum(puntajes_palabras)
        /
        len(puntajes_palabras)
    )


# ==================================================
# BÚSQUEDA INTELIGENTE POR TEXTO
# ==================================================

def buscar_por_texto(
    df: pd.DataFrame,
    consulta: str,
) -> pd.DataFrame:
    """
    Busca por artículo, vehículo, marca,
    almacén y ubicación.
    """

    consulta_limpia = limpiar_consulta(
        consulta
    )

    palabras_busqueda = (
        consulta_limpia.split()
    )

    if not palabras_busqueda:
        return df.iloc[0:0].copy()

    resultados = []

    for indice, fila in df.iterrows():
        puntaje = calcular_puntaje_producto(
            fila,
            palabras_busqueda,
        )

        if puntaje > 0:
            resultado = fila.to_dict()
            resultado["PUNTAJE"] = puntaje
            resultado["_INDICE"] = indice

            resultados.append(
                resultado
            )

    if not resultados:
        return df.iloc[0:0].copy()

    resultados_df = pd.DataFrame(
        resultados
    )

    resultados_df = resultados_df.sort_values(
        by="PUNTAJE",
        ascending=False,
    )

    return resultados_df.head(
        MAX_RESULTADOS
    )


# ==================================================
# MOTOR PRINCIPAL DE BÚSQUEDA
# ==================================================

def buscar_filas(
    df: pd.DataFrame,
    consulta: str,
) -> pd.DataFrame:
    """
    Ejecuta la búsqueda siguiendo prioridades:

    1. Código exacto.
    2. Código parcial.
    3. Texto inteligente.
    """

    consulta = str(
        consulta
    ).strip()

    if not consulta:
        return df.iloc[0:0].copy()

    resultado_exacto = buscar_codigo_exacto(
        df,
        consulta,
    )

    if not resultado_exacto.empty:
        resultado_exacto = (
            resultado_exacto.copy()
        )

        resultado_exacto[
            "PUNTAJE"
        ] = 3000.0

        return resultado_exacto

    resultado_parcial = buscar_codigo_parcial(
        df,
        consulta,
    )

    if not resultado_parcial.empty:
        resultado_parcial = (
            resultado_parcial.copy()
        )

        resultado_parcial[
            "PUNTAJE"
        ] = 2500.0

        return resultado_parcial

    return buscar_por_texto(
        df,
        consulta,
    )


# ==================================================
# FILTRAR POR ALMACÉN
# ==================================================

def filtrar_almacen(
    filas: pd.DataFrame,
    almacen: str | None,
) -> pd.DataFrame:
    """
    Filtra resultados por almacén exacto.
    """

    if not almacen:
        return filas

    almacen_normalizado = normalizar(
        almacen
    )

    mascara = filas[
        "ALMACEN"
    ].apply(
        normalizar
    ) == almacen_normalizado

    return filas[
        mascara
    ].copy()


# ==================================================
# AGRUPAR PRODUCTOS
# ==================================================

def agrupar_productos(
    filas: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Agrupa todas las filas del mismo código.

    Ejemplo:
    YQ4908 en NORTE y NORTE FGS se convierte
    en una sola ficha con el stock total.
    """

    productos = []

    if filas.empty:
        return productos

    for codigo, grupo_codigo in filas.groupby(
        "CODIGO",
        sort=False,
    ):
        primera_fila = grupo_codigo.iloc[0]

        almacenes = []
        stock_total = 0.0

        for almacen, grupo_almacen in grupo_codigo.groupby(
            "ALMACEN",
            sort=False,
        ):
            cantidad_almacen = sum(
                convertir_cantidad(
                    valor
                )
                for valor in grupo_almacen[
                    "CANTIDAD"
                ]
            )

            ubicaciones = sorted(
                {
                    str(
                        ubicacion
                    ).strip()
                    for ubicacion
                    in grupo_almacen[
                        "UBICACION"
                    ]
                    if str(
                        ubicacion
                    ).strip()
                }
            )

            almacenes.append(
                {
                    "almacen": str(
                        almacen
                    ),
                    "ubicaciones": ubicaciones,
                    "cantidad": cantidad_almacen,
                }
            )

            stock_total += cantidad_almacen

        puntaje = 0.0

        if "PUNTAJE" in grupo_codigo.columns:
            puntaje = float(
                grupo_codigo[
                    "PUNTAJE"
                ].max()
            )

        productos.append(
            {
                "codigo": str(
                    codigo
                ),
                "articulo": str(
                    primera_fila.get(
                        "ARTICULO",
                        "",
                    )
                ),
                "marca": str(
                    primera_fila.get(
                        "MARCA",
                        "SIN MARCA",
                    )
                ),
                "stock_total": stock_total,
                "almacenes": almacenes,
                "puntaje": puntaje,
            }
        )

    productos.sort(
        key=lambda producto: producto[
            "puntaje"
        ],
        reverse=True,
    )

    return productos



# ==================================================
# FICHA TÉCNICA DE EMBRAGUES
# ==================================================

def _valor_limpio(valor: Any) -> Any:
    """Convierte NaN/None en None y deja los demás valores listos para JSON."""
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass
    texto = str(valor).strip()
    return texto if texto else None


def obtener_ficha_embrague(codigo: Any) -> dict[str, Any] | None:
    """
    Busca las medidas de embrague por código y devuelve una ficha técnica.
    Requiere que database.py exponga cargar_medidas_embragues().
    """
    if cargar_medidas_embragues is None:
        return None

    try:
        df_medidas = cargar_medidas_embragues()
    except Exception:
        return None

    if df_medidas is None or df_medidas.empty or "CODIGO" not in df_medidas.columns:
        return None

    codigo_limpio = limpiar_codigo(codigo)
    coincidencias = df_medidas[
        df_medidas["CODIGO"].apply(limpiar_codigo) == codigo_limpio
    ]

    if coincidencias.empty:
        return None

    fila = coincidencias.iloc[0]

    return {
        "tipo_medida": "EMBRAGUE",
        "codigo": _valor_limpio(fila.get("CODIGO")),
        "aplicacion": _valor_limpio(
            fila.get("APLICACION")
            if "APLICACION" in fila.index
            else fila.get("REFERENCIA")
        ),
        "referencia": _valor_limpio(fila.get("REFERENCIA")),
        "medidas": {
            "diametro_p_d": _valor_limpio(fila.get("DIAMETRO_P_D")),
            "manzana_p_d": _valor_limpio(fila.get("MANZANA_P_D")),
            "n_dientes": _valor_limpio(fila.get("N_DIENTES")),
            "diametro_motriz": _valor_limpio(fila.get("DIAMETRO_MOTRIZ")),
            "diam_perno_a_perno": _valor_limpio(fila.get("DIAM_PERNO_A_PERNO")),
        },
        "observacion": _valor_limpio(fila.get("OBSERVACION")),
    }


def agregar_fichas_embrague(productos: list[dict[str, Any]]) -> None:
    """Agrega ficha_tecnica a productos que tengan medidas de embrague."""
    for producto in productos:
        ficha = obtener_ficha_embrague(producto.get("codigo"))
        if ficha:
            producto["ficha_tecnica"] = ficha


# ==================================================
# RESPUESTA PRINCIPAL DEL MOTOR
# ==================================================

def procesar_consulta(
    consulta: str,
    df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Función principal que utilizarán FastAPI,
    Streamlit y posteriormente Flutter.
    """

    if df is None:
        df = cargar_inventario_completo()

    consulta = str(
        consulta
    ).strip()

    if not consulta:
        return {
            "consulta": consulta,
            "intencion": "buscar",
            "almacen_solicitado": None,
            "cantidad_productos": 0,
            "stock_total": 0.0,
            "productos": [],
            "mensaje": "La consulta está vacía.",
        }

    intencion = detectar_intencion(
        consulta
    )

    almacen_solicitado = detectar_almacen(
        consulta
    )

    filas = buscar_filas(
        df,
        consulta,
    )

    filas_filtradas = filtrar_almacen(
        filas,
        almacen_solicitado,
    )

    productos = agrupar_productos(
        filas_filtradas
    )

    agregar_fichas_embrague(productos)

    stock_total = sum(
        producto[
            "stock_total"
        ]
        for producto in productos
    )

    if not productos:
        mensaje = (
            "No se encontraron productos relacionados."
        )

    elif intencion == "cantidad":
        if almacen_solicitado:
            mensaje = (
                f"Stock en {almacen_solicitado}: "
                f"{stock_total:g} unidades."
            )
        else:
            mensaje = (
                f"Stock total: "
                f"{stock_total:g} unidades."
            )

    elif intencion == "ubicacion":
        mensaje = (
            f"Se encontraron ubicaciones para "
            f"{len(productos)} producto(s)."
        )

    else:
        mensaje = (
            f"Se encontraron "
            f"{len(productos)} producto(s)."
        )

    return {
        "consulta": consulta,
        "intencion": intencion,
        "almacen_solicitado": almacen_solicitado,
        "cantidad_productos": len(productos),
        "stock_total": stock_total,
        "productos": productos,
        "mensaje": mensaje,
    }


# ==================================================
# PRUEBAS DEL MÓDULO
# ==================================================

if __name__ == "__main__":
    try:
        inventario = cargar_inventario_completo()

        consultas_prueba = [
            "YQ4908",
            "cuanto tengo de YQ4908",
            "cuanto tengo de YQ4908 en NORTE",
            "cuanto tengo de YQ4908 en NORTE FGS",
            "donde esta YQ4908",
            "cuantos discos de freno tengo",
            "embrage sail",
            "disko bt50",
        ]

        for consulta_prueba in consultas_prueba:
            print(
                "\n"
                + "=" * 60
            )

            print(
                f"CONSULTA: {consulta_prueba}"
            )

            resultado = procesar_consulta(
                consulta_prueba,
                inventario,
            )

            print(
                resultado[
                    "mensaje"
                ]
            )

            print(
                f"Intención: "
                f"{resultado['intencion']}"
            )

            print(
                f"Almacén: "
                f"{resultado['almacen_solicitado']}"
            )

            print(
                f"Productos: "
                f"{resultado['cantidad_productos']}"
            )

            print(
                f"Stock total: "
                f"{resultado['stock_total']}"
            )

            for producto in resultado[
                "productos"
            ][:3]:
                print(
                    f"- {producto['codigo']} | "
                    f"{producto['marca']} | "
                    f"{producto['articulo']} | "
                    f"Stock: {producto['stock_total']}"
                )

    except Exception as error:
        print(
            f"Error al probar buscador.py: {error}"
        )