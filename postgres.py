import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# ==================================================
# CARGAR VARIABLES PRIVADAS
# ==================================================

BASE_DIR = Path(__file__).resolve().parent
RUTA_ENV = BASE_DIR / ".env"

load_dotenv(RUTA_ENV)


# ==================================================
# OBTENER URL DE NEON
# ==================================================

def obtener_database_url() -> str:
    database_url = os.getenv(
        "DATABASE_URL",
        "",
    ).strip()

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL no está configurada en el archivo .env."
        )

    # Usaremos Psycopg 3 explícitamente.
    if database_url.startswith(
        "postgresql://"
    ):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return database_url


# ==================================================
# CREAR MOTOR DE CONEXIÓN
# ==================================================

def crear_motor() -> Engine:
    return create_engine(
        obtener_database_url(),
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "connect_timeout": 15,
        },
    )


engine = crear_motor()


# ==================================================
# PROBAR CONEXIÓN
# ==================================================

def probar_conexion() -> dict:
    with engine.connect() as conexion:
        resultado = conexion.execute(
            text(
                """
                SELECT
                    current_database() AS base,
                    current_user AS usuario,
                    NOW() AS fecha_servidor
                """
            )
        ).mappings().one()

        return {
            "base": resultado["base"],
            "usuario": resultado["usuario"],
            "fecha_servidor": str(
                resultado["fecha_servidor"]
            ),
        }


# ==================================================
# PRUEBA DIRECTA
# ==================================================

if __name__ == "__main__":
    try:
        datos = probar_conexion()

        print(
            "Conexión con Neon correcta."
        )

        print(
            f"Base: {datos['base']}"
        )

        print(
            f"Usuario: {datos['usuario']}"
        )

        print(
            f"Fecha del servidor: "
            f"{datos['fecha_servidor']}"
        )

    except Exception as error:
        print(
            "No fue posible conectar con Neon."
        )

        print(
            f"Detalle: {error}"
        )