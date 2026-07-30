from pathlib import Path


# Carpeta principal del proyecto
BASE_DIR = Path(__file__).resolve().parent


# Archivos de datos
RUTA_INVENTARIO = (
    BASE_DIR
    / "datos"
    / "inventario.xlsx"
)

RUTA_MARCAS = (
    BASE_DIR
    / "datos"
    / "marcas.xls"
)


# Carpetas de imágenes
RUTA_IMAGENES = (
    BASE_DIR
    / "imagenes"
)

RUTA_LOGOS_MARCAS = (
    RUTA_IMAGENES
    / "marcas"
)


# Configuración API
API_TITULO = "ServiStock IA API"

API_DESCRIPCION = (
    "API de consulta de inventario "
    "para Serviembragues y Partes"
)

API_VERSION = "1.0.0"


# Cantidad máxima de productos
MAX_RESULTADOS = 500