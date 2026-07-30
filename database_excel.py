import pandas as pd

from config import (
    RUTA_INVENTARIO,
    RUTA_MARCAS,
)


# ==================================================
# LIMPIAR COLUMNAS Y DATOS
# ==================================================

def limpiar_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Limpia nombres de columnas y contenido.

    - Convierte columnas a mayúsculas.
    - Elimina espacios al inicio y al final.
    - Reemplaza valores vacíos por texto vacío.
    """

    df = df.copy()

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.upper()
    )

    for columna in df.columns:
        df[columna] = (
            df[columna]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return df


# ==================================================
# VALIDAR COLUMNAS
# ==================================================

def validar_columnas(
    df: pd.DataFrame,
    columnas_requeridas: set[str],
    nombre_archivo: str,
) -> None:
    """
    Verifica que el archivo contenga las columnas
    necesarias para funcionar.
    """

    columnas_faltantes = (
        columnas_requeridas
        - set(df.columns)
    )

    if columnas_faltantes:
        faltantes = ", ".join(
            sorted(columnas_faltantes)
        )

        raise ValueError(
            f"Faltan columnas en {nombre_archivo}: "
            f"{faltantes}"
        )


# ==================================================
# CARGAR INVENTARIO PRINCIPAL
# ==================================================

def cargar_base_inventario() -> pd.DataFrame:
    """
    Carga inventario.xlsx sin modificar el archivo.
    """

    if not RUTA_INVENTARIO.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: "
            f"{RUTA_INVENTARIO}"
        )

    inventario = pd.read_excel(
        RUTA_INVENTARIO,
        dtype=str,
    )

    inventario = limpiar_dataframe(
        inventario
    )

    columnas_requeridas = {
        "CODIGO",
        "ARTICULO",
        "ALMACEN",
        "UBICACION",
        "CANTIDAD",
    }

    validar_columnas(
        inventario,
        columnas_requeridas,
        "inventario.xlsx",
    )

    return inventario


# ==================================================
# CARGAR BASE DE MARCAS
# ==================================================

def cargar_base_marcas() -> pd.DataFrame:
    """
    Carga marcas.xls sin modificar el archivo.
    """

    if not RUTA_MARCAS.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: "
            f"{RUTA_MARCAS}"
        )

    marcas = pd.read_excel(
        RUTA_MARCAS,
        dtype=str,
    )

    marcas = limpiar_dataframe(
        marcas
    )

    columnas_requeridas = {
        "CODIGO",
        "MARCA",
    }

    validar_columnas(
        marcas,
        columnas_requeridas,
        "marcas.xls",
    )

    marcas = marcas.drop_duplicates(
        subset=["CODIGO"],
        keep="first",
    )

    return marcas


# ==================================================
# UNIR INVENTARIO Y MARCAS
# ==================================================

def cargar_inventario_completo() -> pd.DataFrame:
    """
    Une inventario y marcas por CODIGO.

    La unión ocurre únicamente en memoria.
    No modifica ninguno de los archivos originales.
    """

    inventario = cargar_base_inventario()
    marcas = cargar_base_marcas()

    inventario_completo = inventario.merge(
        marcas[
            [
                "CODIGO",
                "MARCA",
            ]
        ],
        on="CODIGO",
        how="left",
    )

    inventario_completo["MARCA"] = (
        inventario_completo["MARCA"]
        .fillna("SIN MARCA")
        .astype(str)
        .str.strip()
    )

    return inventario_completo


# ==================================================
# PRUEBA DEL MÓDULO
# ==================================================

if __name__ == "__main__":
    try:
        df = cargar_inventario_completo()

        print(
            "Base cargada correctamente."
        )

        print(
            f"Registros: {len(df)}"
        )

        print(
            f"Productos únicos: "
            f"{df['CODIGO'].nunique()}"
        )

        print(
            "Columnas:"
        )

        print(
            list(df.columns)
        )

        print(
            "\nPrimeros registros:"
        )

        print(
            df.head()
        )

    except Exception as error:
        print(
            f"Error al cargar las bases: {error}"
        )