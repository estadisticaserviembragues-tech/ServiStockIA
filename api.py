from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config import (
    API_DESCRIPCION,
    API_TITULO,
    API_VERSION,
)

from database import (
    cargar_inventario_completo,
    obtener_medidas_producto,
    obtener_ultima_sincronizacion,
)

from buscador import (
    limpiar_codigo,
    procesar_consulta,
)


# ==================================================
# CREAR APLICACIÓN
# ==================================================

app = FastAPI(
    title=API_TITULO,
    description=API_DESCRIPCION,
    version=API_VERSION,
)


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# RESPUESTA DE ERROR
# ==================================================

def respuesta_error(
    mensaje: str,
    detalle: str | None = None,
) -> dict[str, Any]:

    respuesta: dict[str, Any] = {
        "estado": "error",
        "mensaje": mensaje,
    }

    if detalle:
        respuesta["detalle"] = detalle

    return respuesta


# ==================================================
# INICIO
# ==================================================

@app.get("/")
def inicio() -> dict[str, Any]:

    return {
        "estado": "activo",
        "nombre": API_TITULO,
        "version": API_VERSION,
        "mensaje": (
            "ServiStock IA está funcionando correctamente."
        ),
    }


# ==================================================
# SALUD
# ==================================================

@app.get("/salud")
def comprobar_salud() -> dict[str, Any]:

    try:
        inventario = cargar_inventario_completo()

        return {
            "estado": "correcto",
            "mensaje": (
                "La base en Neon se cargó correctamente."
            ),
            "registros": int(
                len(inventario)
            ),
            "productos_unicos": int(
                inventario["CODIGO"].nunique()
            ),
            "almacenes": sorted(
                inventario["ALMACEN"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            ),
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=respuesta_error(
                "No fue posible cargar el inventario.",
                str(error),
            ),
        ) from error


# ==================================================
# VERSIÓN
# ==================================================

@app.get("/version")
def obtener_version() -> dict[str, Any]:

    return {
        "nombre": API_TITULO,
        "version": API_VERSION,
        "estado": "desarrollo",
    }


# ==================================================
# BUSCAR
# ==================================================

@app.get("/buscar")
def buscar(
    consulta: str = Query(
        ...,
        min_length=1,
        description=(
            "Código, artículo, vehículo, marca "
            "o pregunta en lenguaje natural."
        ),
    ),
) -> dict[str, Any]:

    try:
        resultado = procesar_consulta(
            consulta
        )

        # Agregar ficha técnica.
        # Puede ser DISCO, TAMBOR o EMBRAGUE.
        for producto in resultado.get(
            "productos",
            [],
        ):

            codigo = producto.get(
                "codigo",
                "",
            )

            ficha_tecnica = (
                obtener_medidas_producto(
                    codigo
                )
            )

            if ficha_tecnica is not None:
                producto[
                    "ficha_tecnica"
                ] = ficha_tecnica

        return {
            "estado": "correcto",
            **resultado,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=respuesta_error(
                "No fue posible procesar la consulta.",
                str(error),
            ),
        ) from error


# ==================================================
# PRODUCTO POR CÓDIGO
# ==================================================

@app.get("/producto/{codigo}")
def obtener_producto(
    codigo: str,
) -> dict[str, Any]:

    try:
        resultado = procesar_consulta(
            codigo
        )

        codigo_buscado = limpiar_codigo(
            codigo
        )

        productos_exactos = [
            producto
            for producto in resultado.get(
                "productos",
                [],
            )
            if limpiar_codigo(
                producto.get(
                    "codigo",
                    "",
                )
            ) == codigo_buscado
        ]

        if not productos_exactos:

            raise HTTPException(
                status_code=404,
                detail=respuesta_error(
                    "Producto no encontrado."
                ),
            )

        producto = productos_exactos[0]

        ficha_tecnica = (
            obtener_medidas_producto(
                codigo
            )
        )

        if ficha_tecnica is not None:
            producto[
                "ficha_tecnica"
            ] = ficha_tecnica

        return {
            "estado": "correcto",
            "producto": producto,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=respuesta_error(
                "No fue posible consultar el producto.",
                str(error),
            ),
        ) from error


# ==================================================
# STOCK POR CÓDIGO
# ==================================================

@app.get("/stock/{codigo}")
def obtener_stock(
    codigo: str,
    almacen: str | None = Query(
        default=None,
        description=(
            "Ejemplo: NORTE, NORTE FGS, "
            "SUR o SUR FGS."
        ),
    ),
) -> dict[str, Any]:

    try:
        consulta = (
            f"cuanto tengo de {codigo}"
        )

        if almacen:
            consulta += (
                f" en {almacen}"
            )

        resultado = procesar_consulta(
            consulta
        )

        if not resultado.get(
            "productos"
        ):

            raise HTTPException(
                status_code=404,
                detail=respuesta_error(
                    "Producto no encontrado."
                ),
            )

        return {
            "estado": "correcto",
            "codigo": codigo,
            "almacen": almacen,
            "stock_total": resultado[
                "stock_total"
            ],
            "mensaje": resultado[
                "mensaje"
            ],
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=respuesta_error(
                "No fue posible consultar el stock.",
                str(error),
            ),
        ) from error


# ==================================================
# MEDIDAS TÉCNICAS
# ==================================================

@app.get("/medidas/{codigo}")
def consultar_medidas(
    codigo: str,
) -> dict[str, Any]:

    try:
        ficha_tecnica = (
            obtener_medidas_producto(
                codigo
            )
        )

        if ficha_tecnica is None:

            raise HTTPException(
                status_code=404,
                detail=respuesta_error(
                    "Este producto no tiene "
                    "medidas técnicas registradas."
                ),
            )

        return {
            "estado": "correcto",
            "ficha_tecnica": ficha_tecnica,
        }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=respuesta_error(
                "No fue posible consultar las medidas.",
                str(error),
            ),
        ) from error


# ==================================================
# ÚLTIMA SINCRONIZACIÓN
# ==================================================

@app.get("/ultima-sincronizacion")
def ultima_sincronizacion() -> dict[str, Any]:

    try:
        sincronizacion = (
            obtener_ultima_sincronizacion()
        )

        if sincronizacion is None:

            return {
                "estado": "sin_registros",
                "mensaje": (
                    "Todavía no existen "
                    "sincronizaciones registradas."
                ),
                "sincronizacion": None,
            }

        return {
            "estado": "correcto",
            "sincronizacion": sincronizacion,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=respuesta_error(
                "No fue posible consultar "
                "la sincronización.",
                str(error),
            ),
        ) from error


# ==================================================
# ESTADÍSTICAS
# ==================================================

@app.get("/estadisticas")
def obtener_estadisticas() -> dict[str, Any]:

    try:
        inventario = cargar_inventario_completo()

        cantidades = inventario[
            "CANTIDAD"
        ].apply(
            lambda valor: (
                float(
                    str(valor)
                    .replace(" ", "")
                    .replace(",", ".")
                )
                if str(valor).strip()
                not in {
                    "",
                    "nan",
                    "None",
                }
                else 0.0
            )
        )

        resumen_almacenes: list[
            dict[str, Any]
        ] = []

        for almacen, grupo in inventario.groupby(
            "ALMACEN",
            sort=False,
        ):

            stock_almacen = sum(
                grupo[
                    "CANTIDAD"
                ].apply(
                    lambda valor: (
                        float(
                            str(valor)
                            .replace(" ", "")
                            .replace(",", ".")
                        )
                        if str(valor).strip()
                        not in {
                            "",
                            "nan",
                            "None",
                        }
                        else 0.0
                    )
                )
            )

            resumen_almacenes.append(
                {
                    "almacen": str(
                        almacen
                    ),
                    "registros": int(
                        len(grupo)
                    ),
                    "productos_unicos": int(
                        grupo[
                            "CODIGO"
                        ].nunique()
                    ),
                    "stock_total": float(
                        stock_almacen
                    ),
                }
            )

        return {
            "estado": "correcto",
            "registros": int(
                len(inventario)
            ),
            "productos_unicos": int(
                inventario[
                    "CODIGO"
                ].nunique()
            ),
            "marcas": int(
                inventario[
                    "MARCA"
                ].nunique()
            ),
            "stock_total": float(
                cantidades.sum()
            ),
            "almacenes": resumen_almacenes,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=respuesta_error(
                "No fue posible calcular "
                "las estadísticas.",
                str(error),
            ),
        ) from error