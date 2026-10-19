from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.types import Numeric, Text

from postgres import engine


# ==================================================
# RUTAS
# ==================================================

BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR / "datos"

RUTA_INVENTARIO = DATOS_DIR / "inventario.xlsx"
RUTA_MARCAS = DATOS_DIR / "marcas.xls"
RUTA_DISCOS = DATOS_DIR / "medidas_discos.xlsx"
RUTA_TAMBORES = DATOS_DIR / "medidas_tambores.xlsx"
RUTA_EMBRAGUES = DATOS_DIR / "medidas_embragues.xlsx"


# ==================================================
# NORMALIZACIÓN
# ==================================================

def normalizar_texto(valor: Any) -> str:
    """
    Convierte texto a una forma uniforme.
    """

    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    return texto


def normalizar_nombre_columna(nombre: Any) -> str:
    """
    Ejemplos:

    APLICACIÓN       -> APLICACION
    Diamet Interno   -> DIAMET_INTERNO
    Numero Hue       -> NUMERO_HUE
    """

    texto = str(nombre).strip().upper()

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
        r"[^A-Z0-9]+",
        "_",
        texto,
    )

    return texto.strip("_")


def normalizar_codigo(valor: Any) -> str:
    """
    Normaliza códigos como:

    HF - 53A -> HF-53A
    HF  -53A -> HF-53A
    """

    texto = normalizar_texto(valor).upper()

    texto = re.sub(
        r"\s*-\s*",
        "-",
        texto,
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


def convertir_numero(valor: Any) -> float | None:
    """
    Convierte valores numéricos de Excel.

    Soporta:
    65.5
    65,5
    espacios
    """

    if pd.isna(valor):
        return None

    texto = str(valor).strip()

    if not texto:
        return None

    texto = texto.replace(" ", "")

    # Caso decimal con coma.
    if "," in texto and "." not in texto:
        texto = texto.replace(",", ".")

    # Caso 1.234,56
    elif "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "")
            texto = texto.replace(",", ".")

    try:
        return float(texto)

    except (TypeError, ValueError):
        return None


def limpiar_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    df.columns = [
        normalizar_nombre_columna(columna)
        for columna in df.columns
    ]

    # Eliminar filas totalmente vacías.
    df = df.dropna(
        how="all",
    )

    return df


def buscar_columna(
    df: pd.DataFrame,
    opciones: list[str],
    obligatoria: bool = True,
) -> str | None:
    columnas = set(df.columns)

    for opcion in opciones:
        opcion_normalizada = normalizar_nombre_columna(
            opcion
        )

        if opcion_normalizada in columnas:
            return opcion_normalizada

    if obligatoria:
        raise ValueError(
            "No se encontró ninguna de estas columnas: "
            + ", ".join(opciones)
            + f". Columnas disponibles: {list(df.columns)}"
        )

    return None


# ==================================================
# CARGAR INVENTARIO
# ==================================================

def cargar_inventario() -> pd.DataFrame:
    if not RUTA_INVENTARIO.exists():
        raise FileNotFoundError(
            f"No existe: {RUTA_INVENTARIO}"
        )

    df = pd.read_excel(
        RUTA_INVENTARIO,
        dtype=object,
    )

    df = limpiar_dataframe(df)

    columna_codigo = buscar_columna(
        df,
        ["CODIGO", "CÓDIGO"],
    )

    columna_articulo = buscar_columna(
        df,
        ["ARTICULO", "ARTÍCULO", "NOMBRE"],
    )

    columna_almacen = buscar_columna(
        df,
        ["ALMACEN", "ALMACÉN", "BODEGA"],
    )

    columna_ubicacion = buscar_columna(
        df,
        ["UBICACION", "UBICACIÓN"],
    )

    columna_cantidad = buscar_columna(
        df,
        ["CANTIDAD", "STOCK", "EXISTENCIA"],
    )

    resultado = pd.DataFrame(
        {
            "codigo": df[columna_codigo].apply(
                normalizar_codigo
            ),
            "articulo": df[columna_articulo].apply(
                normalizar_texto
            ),
            "almacen": df[columna_almacen].apply(
                normalizar_texto
            ),
            "ubicacion": df[columna_ubicacion].apply(
                normalizar_texto
            ),
            "cantidad": df[columna_cantidad].apply(
                convertir_numero
            ),
        }
    )

    resultado = resultado[
        resultado["codigo"] != ""
    ].copy()

    resultado["cantidad"] = (
        resultado["cantidad"]
        .fillna(0)
        .astype(float)
    )

    return resultado


# ==================================================
# CARGAR MARCAS
# ==================================================

def cargar_marcas() -> pd.DataFrame:
    if not RUTA_MARCAS.exists():
        raise FileNotFoundError(
            f"No existe: {RUTA_MARCAS}"
        )

    df = pd.read_excel(
        RUTA_MARCAS,
        dtype=object,
    )

    df = limpiar_dataframe(df)

    columna_codigo = buscar_columna(
        df,
        ["CODIGO", "CÓDIGO"],
    )

    columna_marca = buscar_columna(
        df,
        ["MARCA"],
    )

    resultado = pd.DataFrame(
        {
            "codigo": df[columna_codigo].apply(
                normalizar_codigo
            ),
            "marca": df[columna_marca].apply(
                normalizar_texto
            ),
        }
    )

    resultado = resultado[
        resultado["codigo"] != ""
    ].copy()

    resultado = resultado.drop_duplicates(
        subset=["codigo"],
        keep="first",
    )

    return resultado


# ==================================================
# CARGAR MEDIDAS DE DISCOS
# ==================================================

def cargar_discos() -> pd.DataFrame:
    if not RUTA_DISCOS.exists():
        raise FileNotFoundError(
            f"No existe: {RUTA_DISCOS}"
        )

    df = pd.read_excel(
        RUTA_DISCOS,
        dtype=object,
    )

    df = limpiar_dataframe(df)

    columna_codigo = buscar_columna(
        df,
        ["CODIGO", "CÓDIGO", "CODIGO HIPPER"],
    )

    columna_aplicacion = buscar_columna(
        df,
        ["APLICACION", "APLICACIÓN"],
    )

    columna_tipo = buscar_columna(
        df,
        ["TIPO"],
    )

    columna_diametro = buscar_columna(
        df,
        ["DIAMETRO DISCO", "DIAMETRO_DISCO"],
    )

    columna_grosor = buscar_columna(
        df,
        ["GROSOR DISCO", "GROSOR_DISCO"],
    )

    columna_altura = buscar_columna(
        df,
        ["ALTURA TOTAL", "ALTURA_TOTAL"],
    )

    columna_hub = buscar_columna(
        df,
        ["DIAMETRO HUB", "DIAMETRO_HUB"],
    )

    columna_huecos = buscar_columna(
        df,
        [
            "NUMERO HUE",
            "NUMERO HUECOS",
            "NÚMERO HUE",
            "NÚMERO HUECOS",
        ],
    )

    resultado = pd.DataFrame(
        {
            "codigo": df[columna_codigo].apply(
                normalizar_codigo
            ),
            "aplicacion": df[columna_aplicacion].apply(
                normalizar_texto
            ),
            "tipo": df[columna_tipo].apply(
                normalizar_texto
            ),
            "diametro_disco": df[columna_diametro].apply(
                convertir_numero
            ),
            "grosor_disco": df[columna_grosor].apply(
                convertir_numero
            ),
            "altura_total": df[columna_altura].apply(
                convertir_numero
            ),
            "diametro_hub": df[columna_hub].apply(
                convertir_numero
            ),
            "numero_huecos": df[columna_huecos].apply(
                normalizar_texto
            ),
        }
    )

    resultado = resultado[
        resultado["codigo"] != ""
    ].copy()

    resultado = resultado.drop_duplicates(
        subset=["codigo"],
        keep="first",
    )

    return resultado


# ==================================================
# CARGAR MEDIDAS DE TAMBORES
# ==================================================

def cargar_tambores() -> pd.DataFrame:
    if not RUTA_TAMBORES.exists():
        raise FileNotFoundError(
            f"No existe: {RUTA_TAMBORES}"
        )

    df = pd.read_excel(
        RUTA_TAMBORES,
        dtype=object,
    )

    df = limpiar_dataframe(df)

    columna_codigo = buscar_columna(
        df,
        [
            "CODIGO",
            "CÓDIGO",
            "CODIGO 3 HIPPER",
        ],
    )

    columna_aplicacion = buscar_columna(
        df,
        ["APLICACION", "APLICACIÓN"],
    )

    columna_interno = buscar_columna(
        df,
        [
            "DIAMET INTERNO",
            "DIAMETRO INTERNO",
            "DIAMETRO_INTERNO",
        ],
    )

    columna_exterior = buscar_columna(
        df,
        [
            "DIAMET EXTERIO",
            "DIAMET EXTERIOR",
            "DIAMETRO EXTERIOR",
            "DIAMETRO_EXTERIOR",
        ],
    )

    columna_altura = buscar_columna(
        df,
        ["ALTURA TOTAL", "ALTURA_TOTAL"],
    )

    columna_agujero = buscar_columna(
        df,
        [
            "DIAMET AGUJERO",
            "DIAMETRO AGUJERO",
            "DIAMETRO_AGUJERO",
        ],
    )

    columna_pista = buscar_columna(
        df,
        ["ANCHO PISTA", "ANCHO_PISTA"],
    )

    columna_huecos = buscar_columna(
        df,
        [
            "NUMERO HUE",
            "NUMERO HUECOS",
            "NÚMERO HUE",
            "NÚMERO HUECOS",
        ],
    )

    resultado = pd.DataFrame(
        {
            "codigo": df[columna_codigo].apply(
                normalizar_codigo
            ),
            "aplicacion": df[columna_aplicacion].apply(
                normalizar_texto
            ),
            "diametro_interno": df[columna_interno].apply(
                convertir_numero
            ),
            "diametro_exterior": df[columna_exterior].apply(
                convertir_numero
            ),
            "altura_total": df[columna_altura].apply(
                convertir_numero
            ),
            "diametro_agujero": df[columna_agujero].apply(
                convertir_numero
            ),
            "ancho_pista": df[columna_pista].apply(
                convertir_numero
            ),
            "numero_huecos": df[columna_huecos].apply(
                normalizar_texto
            ),
        }
    )

    resultado = resultado[
        resultado["codigo"] != ""
    ].copy()

    resultado = resultado.drop_duplicates(
        subset=["codigo"],
        keep="first",
    )

    return resultado


# ==================================================
# CARGAR MEDIDAS DE EMBRAGUES
# ==================================================

def cargar_embragues() -> pd.DataFrame:
    if not RUTA_EMBRAGUES.exists():
        raise FileNotFoundError(
            f"No existe: {RUTA_EMBRAGUES}"
        )

    df = pd.read_excel(
        RUTA_EMBRAGUES,
        dtype=object,
    )

    df = limpiar_dataframe(df)

    columna_codigo = buscar_columna(
        df,
        ["CODIGO", "CÓDIGO"],
    )

    columna_referencia = buscar_columna(
        df,
        ["REFERENCIA", "DESCRIPCION", "DESCRIPCIÓN"],
    )

    columna_diametro_pd = buscar_columna(
        df,
        [
            "DIAMETRO P-D",
            "DIAMETRO P_D",
            "DIAMETRO_PD",
            "DIAMETRO_P-D",
        ],
    )

    columna_manzana_pd = buscar_columna(
        df,
        [
            "MANZANA P-D",
            "MANZANA P_D",
            "MANZANA_PD",
            "MANZANA_P-D",
        ],
    )

    columna_dientes = buscar_columna(
        df,
        [
            "N DIENTES",
            "N_DIENTES",
            "NUMERO DIENTES",
            "NÚMERO DIENTES",
        ],
        obligatoria=False,
    )

    columna_diametro_motriz = buscar_columna(
        df,
        [
            "DIAMETRO MOTRIZ",
            "DIAMETRO_MOTRIZ",
        ],
        obligatoria=False,
    )

    columna_perno = buscar_columna(
        df,
        [
            "DIAM PERNO A PERNO",
            "DIAM_PERNO_A_PERNO",
            "DIAMETRO PERNO A PERNO",
            "DIAMETRO_PERNO_A_PERNO",
        ],
        obligatoria=False,
    )

    columna_aplicacion = buscar_columna(
        df,
        ["APLICACION", "APLICACIÓN"],
        obligatoria=False,
    )

    columna_observacion = buscar_columna(
        df,
        ["OBSERVACION", "OBSERVACIÓN"],
        obligatoria=False,
    )

    def obtener_texto(
        columna: str | None,
    ) -> pd.Series:
        if columna is None:
            return pd.Series(
                [""] * len(df),
                index=df.index,
                dtype=object,
            )

        return df[columna].apply(
            normalizar_texto
        )

    resultado = pd.DataFrame(
        {
            "codigo": df[columna_codigo].apply(
                normalizar_codigo
            ),
            "referencia": df[columna_referencia].apply(
                normalizar_texto
            ),
            # Se guardan como texto porque existen valores como
            # 200-205, 133-134, EA 15.3, etc.
            "diametro_pd": obtener_texto(
                columna_diametro_pd
            ),
            "manzana_pd": obtener_texto(
                columna_manzana_pd
            ),
            "n_dientes": obtener_texto(
                columna_dientes
            ),
            "diametro_motriz": obtener_texto(
                columna_diametro_motriz
            ),
            "diam_perno_a_perno": obtener_texto(
                columna_perno
            ),
            "aplicacion": obtener_texto(
                columna_aplicacion
            ),
            "observacion": obtener_texto(
                columna_observacion
            ),
        }
    )

    resultado = resultado[
        resultado["codigo"] != ""
    ].copy()

    resultado = resultado.drop_duplicates(
        subset=["codigo"],
        keep="first",
    )

    return resultado


# ==================================================
# VALIDACIONES
# ==================================================

def validar_datos(
    inventario: pd.DataFrame,
    marcas: pd.DataFrame,
    discos: pd.DataFrame,
    tambores: pd.DataFrame,
    embragues: pd.DataFrame,
) -> None:
    if inventario.empty:
        raise ValueError(
            "El inventario está vacío."
        )

    if inventario["codigo"].eq("").any():
        raise ValueError(
            "El inventario contiene códigos vacíos."
        )

    if inventario["cantidad"].isna().any():
        raise ValueError(
            "El inventario contiene cantidades inválidas."
        )

    print(
        f"Inventario preparado: {len(inventario):,} filas"
    )

    print(
        f"Marcas preparadas: {len(marcas):,} filas"
    )

    print(
        f"Discos preparados: {len(discos):,} filas"
    )

    print(
        f"Tambores preparados: {len(tambores):,} filas"
    )

    print(
        f"Embragues preparados: {len(embragues):,} filas"
    )


# ==================================================
# SUBIR A POSTGRESQL
# ==================================================

def sincronizar() -> None:
    fecha_inicio = datetime.now()

    inventario = cargar_inventario()
    marcas = cargar_marcas()
    discos = cargar_discos()
    tambores = cargar_tambores()
    embragues = cargar_embragues()

    validar_datos(
        inventario,
        marcas,
        discos,
        tambores,
        embragues,
    )

    with engine.begin() as conexion:
        # Tablas temporales de carga.
        inventario.to_sql(
            "stg_inventario",
            con=conexion,
            if_exists="replace",
            index=False,
            chunksize=1000,
            method="multi",
            dtype={
                "codigo": Text(),
                "articulo": Text(),
                "almacen": Text(),
                "ubicacion": Text(),
                "cantidad": Numeric(),
            },
        )

        marcas.to_sql(
            "stg_marcas",
            con=conexion,
            if_exists="replace",
            index=False,
            chunksize=1000,
            method="multi",
            dtype={
                "codigo": Text(),
                "marca": Text(),
            },
        )

        discos.to_sql(
            "stg_medidas_discos",
            con=conexion,
            if_exists="replace",
            index=False,
            chunksize=1000,
            method="multi",
        )

        tambores.to_sql(
            "stg_medidas_tambores",
            con=conexion,
            if_exists="replace",
            index=False,
            chunksize=1000,
            method="multi",
        )

        embragues.to_sql(
            "stg_medidas_embragues",
            con=conexion,
            if_exists="replace",
            index=False,
            chunksize=1000,
            method="multi",
            dtype={
                "codigo": Text(),
                "referencia": Text(),
                "diametro_pd": Text(),
                "manzana_pd": Text(),
                "n_dientes": Text(),
                "diametro_motriz": Text(),
                "diam_perno_a_perno": Text(),
                "aplicacion": Text(),
                "observacion": Text(),
            },
        )

        # Reemplazar inventario definitivo.
        conexion.execute(
            text(
                """
                DELETE FROM inventario;

                INSERT INTO inventario (
                    codigo,
                    articulo,
                    almacen,
                    ubicacion,
                    cantidad,
                    fecha_actualizacion
                )
                SELECT
                    codigo,
                    articulo,
                    almacen,
                    ubicacion,
                    cantidad,
                    NOW()
                FROM stg_inventario;
                """
            )
        )

        # Reemplazar marcas.
        conexion.execute(
            text(
                """
                DELETE FROM marcas;

                INSERT INTO marcas (
                    codigo,
                    marca,
                    fecha_actualizacion
                )
                SELECT
                    codigo,
                    marca,
                    NOW()
                FROM stg_marcas;
                """
            )
        )

        # Reemplazar medidas de discos.
        conexion.execute(
            text(
                """
                DELETE FROM medidas_discos;

                INSERT INTO medidas_discos (
                    codigo,
                    aplicacion,
                    tipo,
                    diametro_disco,
                    grosor_disco,
                    altura_total,
                    diametro_hub,
                    numero_huecos,
                    fecha_actualizacion
                )
                SELECT
                    codigo,
                    aplicacion,
                    tipo,
                    diametro_disco,
                    grosor_disco,
                    altura_total,
                    diametro_hub,
                    numero_huecos,
                    NOW()
                FROM stg_medidas_discos;
                """
            )
        )

        # Reemplazar medidas de tambores.
        conexion.execute(
            text(
                """
                DELETE FROM medidas_tambores;

                INSERT INTO medidas_tambores (
                    codigo,
                    aplicacion,
                    diametro_interno,
                    diametro_exterior,
                    altura_total,
                    diametro_agujero,
                    ancho_pista,
                    numero_huecos,
                    fecha_actualizacion
                )
                SELECT
                    codigo,
                    aplicacion,
                    diametro_interno,
                    diametro_exterior,
                    altura_total,
                    diametro_agujero,
                    ancho_pista,
                    numero_huecos,
                    NOW()
                FROM stg_medidas_tambores;
                """
            )
        )

        # Reemplazar medidas de embragues.
        conexion.execute(
            text(
                """
                DELETE FROM medidas_embragues;

                INSERT INTO medidas_embragues (
                    codigo,
                    referencia,
                    diametro_pd,
                    manzana_pd,
                    n_dientes,
                    diametro_motriz,
                    diam_perno_a_perno,
                    aplicacion,
                    observacion,
                    fecha_actualizacion
                )
                SELECT
                    codigo,
                    referencia,
                    diametro_pd,
                    manzana_pd,
                    n_dientes,
                    diametro_motriz,
                    diam_perno_a_perno,
                    aplicacion,
                    observacion,
                    NOW()
                FROM stg_medidas_embragues;
                """
            )
        )

        # Eliminar tablas de trabajo.
        conexion.execute(
            text(
                """
                DROP TABLE IF EXISTS stg_inventario;
                DROP TABLE IF EXISTS stg_marcas;
                DROP TABLE IF EXISTS stg_medidas_discos;
                DROP TABLE IF EXISTS stg_medidas_tambores;
                DROP TABLE IF EXISTS stg_medidas_embragues;
                """
            )
        )

        fecha_fin = datetime.now()

        conexion.execute(
            text(
                """
                INSERT INTO sincronizaciones (
                    fecha_inicio,
                    fecha_fin,
                    estado,
                    registros_inventario,
                    registros_marcas,
                    registros_discos,
                    registros_tambores,
                    mensaje
                )
                VALUES (
                    :fecha_inicio,
                    :fecha_fin,
                    'CORRECTO',
                    :registros_inventario,
                    :registros_marcas,
                    :registros_discos,
                    :registros_tambores,
                    :mensaje
                )
                """
            ),
            {
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "registros_inventario": len(inventario),
                "registros_marcas": len(marcas),
                "registros_discos": len(discos),
                "registros_tambores": len(tambores),
                "mensaje": (
                    "Sincronización completada correctamente."
                ),
            },
        )

    duracion = datetime.now() - fecha_inicio

    print()
    print("=" * 55)
    print("SERVISTOCK IA SINCRONIZADO CORRECTAMENTE")
    print("=" * 55)
    print(f"Inventario: {len(inventario):,}")
    print(f"Marcas: {len(marcas):,}")
    print(f"Medidas de discos: {len(discos):,}")
    print(f"Medidas de tambores: {len(tambores):,}")
    print(f"Medidas de embragues: {len(embragues):,}")
    print(f"Duración: {duracion}")
    print("=" * 55)


# ==================================================
# EJECUCIÓN
# ==================================================

if __name__ == "__main__":
    try:
        sincronizar()

    except Exception as error:
        print()
        print("=" * 55)
        print("ERROR DURANTE LA SINCRONIZACIÓN")
        print("=" * 55)
        print(str(error))
        print("=" * 55)

        raise