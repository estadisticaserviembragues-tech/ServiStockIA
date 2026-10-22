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
    "embrage": "embrague",
    "embreague": "embrague",
    "embraguee": "embrague",
    "clutch": "embrague",
    "disko": "disco",
    "diskos": "disco",
    "discos": "disco",
    "disc": "disco",
    "pastilla": "past",
    "pastillas": "past",
    "past": "past",
    "zapatas": "zapata",
    "rulimanes": "ruliman",
    "rodamiento": "ruliman",
    "rodamientos": "ruliman",
    "balinera": "ruliman",
    "balineras": "ruliman",
    "volantes": "volante",
    "bt 50": "bt50",
    "bt-50": "bt50",
    "t 60": "t60",
    "t-60": "t60",
    "d max": "dmax",
    "d-max": "dmax",
    "grand vitara": "grandvitara",
    "toyta": "toyota",
    "chevolet": "chevrolet",
    "chevrolet": "chevrolet",
    "hyunday": "hyundai",
    "hiunday": "hyundai",
    "wolkswagen": "volkswagen",
}


def aplicar_sinonimos(texto: Any) -> str:
    resultado = normalizar(texto)

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
    "a", "al", "algo", "dame", "donde", "esta", "estan", "hay", "quiero",
    "necesito", "busco", "buscar", "muestrame", "mostrar", "el", "la",
    "los", "las", "un", "una", "unos", "unas", "de", "del", "para", "por",
    "en", "mi", "tengo", "tienes", "tiene", "tienen", "cuanto", "cuantos",
    "cuanta", "cuantas", "cantidad", "stock", "total", "producto", "productos",
    "articulo", "articulos", "bodega", "inventario", "solo", "solamente",
}


def limpiar_consulta(consulta: Any) -> str:
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
    texto = normalizar(
        consulta
    )

    palabras = set(
        texto.split()
    )

    palabras_cantidad = {
        "cuanto", "cuantos", "cuanta", "cuantas",
        "cantidad", "stock", "total",
    }

    frases_ubicacion = {
        "donde", "ubicacion", "ubicaciones",
    }

    if palabras.intersection(palabras_cantidad):
        return "cantidad"

    if palabras.intersection(frases_ubicacion):
        return "ubicacion"

    if "en que bodega" in texto or "en que ubicacion" in texto:
        return "ubicacion"

    return "buscar"


# ==================================================
# DETECTAR ALMACÉN
# ==================================================

def detectar_almacen(
    consulta: str,
) -> str | None:
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
    codigo = aplicar_sinonimos(fila.get("CODIGO", ""))
    articulo = aplicar_sinonimos(fila.get("ARTICULO", ""))
    marca = aplicar_sinonimos(fila.get("MARCA", ""))
    almacen = aplicar_sinonimos(fila.get("ALMACEN", ""))
    ubicacion = aplicar_sinonimos(fila.get("UBICACION", ""))

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
        if palabra_busqueda in palabras_producto:
            puntajes_palabras.append(100.0)
            continue

        coincidencia_parcial = any(
            (
                palabra_busqueda in palabra_producto
                or palabra_producto in palabra_busqueda
            )
            for palabra_producto in palabras_producto
            if (
                len(palabra_busqueda) >= 3
                and len(palabra_producto) >= 3
            )
        )

        if coincidencia_parcial:
            puntajes_palabras.append(95.0)
            continue

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
        / len(puntajes_palabras)
    )

    if porcentaje_coincidencia < 0.75:
        return 0.0

    return (
        sum(puntajes_palabras)
        / len(puntajes_palabras)
    )


# ==================================================
# BÚSQUEDA INTELIGENTE POR TEXTO
# ==================================================

def buscar_por_texto(
    df: pd.DataFrame,
    consulta: str,
) -> pd.DataFrame:
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

        # Búsqueda inteligente: revisa todas las filas del código en busca de un precio válido
        def obtener_precio_robusto(grupo, *claves):
            for clave in claves:
                if clave in grupo.columns:
                    for val in grupo[clave]:
                        if val is not None and str(val).strip() != "":
                            try:
                                num = float(str(val).replace(",", "."))
                                if num > 0:
                                    return num
                            except (ValueError, TypeError):
                                pass
            return 0.0

        precio_1 = obtener_precio_robusto(grupo_codigo, "precio_1", "PRECIO_1", "PRECIO 1", "PRECIO1")
        precio_2 = obtener_precio_robusto(grupo_codigo, "precio_2", "PRECIO_2", "PRECIO 2", "PRECIO2")
        precio_3 = obtener_precio_robusto(grupo_codigo, "precio_3", "PRECIO_3", "PRECIO 3", "PRECIO3")

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
                "precio_1": precio_1,
                "precio_2": precio_2,
                "precio_3": precio_3,
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