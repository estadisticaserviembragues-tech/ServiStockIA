from sqlalchemy import text

from postgres import engine


SQL_CREAR_TABLAS = """
CREATE TABLE IF NOT EXISTS inventario (
    id BIGSERIAL PRIMARY KEY,
    codigo TEXT NOT NULL,
    articulo TEXT,
    almacen TEXT,
    ubicacion TEXT,
    cantidad NUMERIC DEFAULT 0,
    fecha_actualizacion TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inventario_codigo
ON inventario (codigo);


CREATE TABLE IF NOT EXISTS marcas (
    id BIGSERIAL PRIMARY KEY,
    codigo TEXT NOT NULL,
    marca TEXT,
    fecha_actualizacion TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_marcas_codigo
ON marcas (codigo);


CREATE TABLE IF NOT EXISTS medidas_discos (
    id BIGSERIAL PRIMARY KEY,
    codigo TEXT NOT NULL,
    aplicacion TEXT,
    tipo TEXT,
    diametro_disco NUMERIC,
    grosor_disco NUMERIC,
    altura_total NUMERIC,
    diametro_hub NUMERIC,
    numero_huecos TEXT,
    fecha_actualizacion TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_medidas_discos_codigo
ON medidas_discos (codigo);


CREATE TABLE IF NOT EXISTS medidas_tambores (
    id BIGSERIAL PRIMARY KEY,
    codigo TEXT NOT NULL,
    aplicacion TEXT,
    diametro_interno NUMERIC,
    diametro_exterior NUMERIC,
    altura_total NUMERIC,
    diametro_agujero NUMERIC,
    ancho_pista NUMERIC,
    numero_huecos TEXT,
    fecha_actualizacion TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_medidas_tambores_codigo
ON medidas_tambores (codigo);


CREATE TABLE IF NOT EXISTS sincronizaciones (
    id BIGSERIAL PRIMARY KEY,
    fecha_inicio TIMESTAMPTZ DEFAULT NOW(),
    fecha_fin TIMESTAMPTZ,
    estado TEXT,
    registros_inventario INTEGER DEFAULT 0,
    registros_marcas INTEGER DEFAULT 0,
    registros_discos INTEGER DEFAULT 0,
    registros_tambores INTEGER DEFAULT 0,
    mensaje TEXT
);
"""


def crear_tablas() -> None:
    with engine.begin() as conexion:
        conexion.execute(
            text(SQL_CREAR_TABLAS)
        )


if __name__ == "__main__":
    try:
        crear_tablas()

        print(
            "Tablas creadas correctamente en Neon."
        )

        print(
            "Tablas disponibles:"
        )

        print(
            "- inventario"
        )

        print(
            "- marcas"
        )

        print(
            "- medidas_discos"
        )

        print(
            "- medidas_tambores"
        )

        print(
            "- sincronizaciones"
        )

    except Exception as error:
        print(
            "No fue posible crear las tablas."
        )

        print(
            f"Detalle: {error}"
        )