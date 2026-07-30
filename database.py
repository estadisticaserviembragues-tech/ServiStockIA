from __future__ import annotations

import re
from typing import Any

import pandas as pd
from sqlalchemy import text

from postgres import engine


# ==================================================
# NORMALIZAR CÓDIGOS
# ==================================================

def normalizar_codigo(valor: Any) -> str:
    """
    Normaliza códigos para consultarlos en PostgreSQL.

    Ejemplo:
    HF - 53A -> HF-53A
    """

    texto = str(valor or "").strip().upper()

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


# ==================================================
# VALIDAR COLUMNAS
# ==================================================

def validar_columnas(
    df: pd.DataFrame,
) -> None:
    columnas_requeridas = {
        "CODIGO",
        "ARTICULO",
        "ALMACEN",
        "UBICACION",
        "CANTIDAD",
        "MARCA",
    }

    columnas_faltantes = (
        columnas_requeridas
        - set(df.columns)
    )

    if columnas_faltantes:
        raise ValueError(
            "Faltan columnas en la consulta de PostgreSQL: "
            + ", ".join(
                sorted(columnas_faltantes)
            )
        )


# ==================================================
# CARGAR INVENTARIO DESDE NEON
# ==================================================

def cargar_inventario_completo() -> pd.DataFrame:
    """
    Carga el inventario y las marcas directamente
    desde PostgreSQL Neon.

    Esta función reemplaza la lectura local de:

    - inventario.xlsx
    - marcas.xls
    """

    consulta = text(
        """
        SELECT
            i.codigo AS "CODIGO",
            COALESCE(i.articulo, '') AS "ARTICULO",
            COALESCE(i.almacen, '') AS "ALMACEN",
            COALESCE(i.ubicacion, '') AS "UBICACION",
            COALESCE(i.cantidad, 0) AS "CANTIDAD",
            COALESCE(m.marca, 'SIN MARCA') AS "MARCA"
        FROM inventario AS i
        LEFT JOIN marcas AS m
            ON m.codigo = i.codigo
        ORDER BY
            i.codigo,
            i.almacen,
            i.ubicacion
        """
    )

    with engine.connect() as conexion:
        inventario = pd.read_sql(
            consulta,
            conexion,
        )

    validar_columnas(
        inventario
    )

    columnas_texto = [
        "CODIGO",
        "ARTICULO",
        "ALMACEN",
        "UBICACION",
        "MARCA",
    ]

    for columna in columnas_texto:
        inventario[columna] = (
            inventario[columna]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    inventario["CANTIDAD"] = pd.to_numeric(
        inventario["CANTIDAD"],
        errors="coerce",
    ).fillna(0)

    inventario["MARCA"] = inventario[
        "MARCA"
    ].replace(
        "",
        "SIN MARCA",
    )

    return inventario


# ==================================================
# MEDIDAS DE DISCOS
# ==================================================

def obtener_medidas_disco(
    codigo: str,
) -> dict[str, Any] | None:
    codigo_normalizado = normalizar_codigo(
        codigo
    )

    consulta = text(
        """
        SELECT
            codigo,
            aplicacion,
            tipo,
            diametro_disco,
            grosor_disco,
            altura_total,
            diametro_hub,
            numero_huecos
        FROM medidas_discos
        WHERE codigo = :codigo
        LIMIT 1
        """
    )

    with engine.connect() as conexion:
        resultado = conexion.execute(
            consulta,
            {
                "codigo": codigo_normalizado,
            },
        ).mappings().first()

    if resultado is None:
        return None

    return {
        "tipo_medida": "DISCO",
        "codigo": resultado["codigo"],
        "aplicacion": resultado["aplicacion"],
        "medidas": {
            "tipo": resultado["tipo"],
            "diametro_disco": resultado[
                "diametro_disco"
            ],
            "grosor_disco": resultado[
                "grosor_disco"
            ],
            "altura_total": resultado[
                "altura_total"
            ],
            "diametro_hub": resultado[
                "diametro_hub"
            ],
            "numero_huecos": resultado[
                "numero_huecos"
            ],
        },
    }


# ==================================================
# MEDIDAS DE TAMBORES
# ==================================================

def obtener_medidas_tambor(
    codigo: str,
) -> dict[str, Any] | None:
    codigo_normalizado = normalizar_codigo(
        codigo
    )

    consulta = text(
        """
        SELECT
            codigo,
            aplicacion,
            diametro_interno,
            diametro_exterior,
            altura_total,
            diametro_agujero,
            ancho_pista,
            numero_huecos
        FROM medidas_tambores
        WHERE codigo = :codigo
        LIMIT 1
        """
    )

    with engine.connect() as conexion:
        resultado = conexion.execute(
            consulta,
            {
                "codigo": codigo_normalizado,
            },
        ).mappings().first()

    if resultado is None:
        return None

    return {
        "tipo_medida": "TAMBOR",
        "codigo": resultado["codigo"],
        "aplicacion": resultado["aplicacion"],
        "medidas": {
            "diametro_interno": resultado[
                "diametro_interno"
            ],
            "diametro_exterior": resultado[
                "diametro_exterior"
            ],
            "altura_total": resultado[
                "altura_total"
            ],
            "diametro_agujero": resultado[
                "diametro_agujero"
            ],
            "ancho_pista": resultado[
                "ancho_pista"
            ],
            "numero_huecos": resultado[
                "numero_huecos"
            ],
        },
    }


# ==================================================
# OBTENER CUALQUIER TIPO DE MEDIDA
# ==================================================

def obtener_medidas_producto(
    codigo: str,
) -> dict[str, Any] | None:
    """
    Primero busca medidas de disco.
    Si no existen, busca medidas de tambor.
    """

    medidas_disco = obtener_medidas_disco(
        codigo
    )

    if medidas_disco is not None:
        return medidas_disco

    return obtener_medidas_tambor(
        codigo
    )


# ==================================================
# ÚLTIMA SINCRONIZACIÓN
# ==================================================

def obtener_ultima_sincronizacion() -> dict[str, Any] | None:
    consulta = text(
        """
        SELECT
            fecha_inicio,
            fecha_fin,
            estado,
            registros_inventario,
            registros_marcas,
            registros_discos,
            registros_tambores,
            mensaje
        FROM sincronizaciones
        ORDER BY id DESC
        LIMIT 1
        """
    )

    with engine.connect() as conexion:
        resultado = conexion.execute(
            consulta
        ).mappings().first()

    if resultado is None:
        return None

    return {
        "fecha_inicio": str(
            resultado["fecha_inicio"]
        ),
        "fecha_fin": str(
            resultado["fecha_fin"]
        ),
        "estado": resultado["estado"],
        "registros_inventario": resultado[
            "registros_inventario"
        ],
        "registros_marcas": resultado[
            "registros_marcas"
        ],
        "registros_discos": resultado[
            "registros_discos"
        ],
        "registros_tambores": resultado[
            "registros_tambores"
        ],
        "mensaje": resultado["mensaje"],
    }


# ==================================================
# PRUEBA DEL MÓDULO
# ==================================================

if __name__ == "__main__":
    try:
        df = cargar_inventario_completo()

        print()
        print("=" * 60)
        print("INVENTARIO CARGADO DESDE NEON")
        print("=" * 60)

        print(
            f"Registros: {len(df):,}"
        )

        print(
            f"Productos únicos: "
            f"{df['CODIGO'].nunique():,}"
        )

        print(
            f"Marcas: "
            f"{df['MARCA'].nunique():,}"
        )

        print(
            f"Almacenes: "
            f"{df['ALMACEN'].nunique():,}"
        )

        print()
        print("Columnas:")
        print(
            list(df.columns)
        )

        print()
        print("Primeros registros:")
        print(
            df.head()
        )

        print()
        print("Última sincronización:")

        ultima = obtener_ultima_sincronizacion()

        print(
            ultima
        )

        print()
        print("Prueba de medidas HF-53N:")

        print(
            obtener_medidas_producto(
                "HF-53N"
            )
        )

        print()
        print("Prueba de medidas HF-53A:")

        print(
            obtener_medidas_producto(
                "HF - 53A"
            )
        )

    except Exception as error:
        print()
        print("=" * 60)
        print("ERROR AL LEER NEON")
        print("=" * 60)
        print(
            str(error)
        )
        print("=" * 60)

        raise