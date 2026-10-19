import os
import sys
import time
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

import win32com.client


# ============================================================
# RUTAS Y CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RUTA_EXCEL = BASE_DIR / "datos" / "inventario.xlsx"
RUTA_SINCRONIZADOR = BASE_DIR / "sincronizar_inventario.py"

CARPETA_LOGS = BASE_DIR / "logs"
ARCHIVO_LOG = CARPETA_LOGS / "servisync.log"
ARCHIVO_BLOQUEO = BASE_DIR / "servisync.lock"

TIEMPO_MAXIMO_ACTUALIZACION = 600  # 10 minutos
TIEMPO_MAXIMO_SINCRONIZADOR = 900  # 15 minutos
TIEMPO_MAXIMO_BLOQUEO = 1800       # 30 minutos
ESPERA_ENTRE_REVISIONES = 5        # segundos


# ============================================================
# LOG
# ============================================================

def escribir_log(mensaje: str) -> None:
    """Escribe un mensaje en consola y en el archivo de log."""
    CARPETA_LOGS.mkdir(parents=True, exist_ok=True)

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{fecha}] {mensaje}"

    print(linea)

    with ARCHIVO_LOG.open("a", encoding="utf-8") as archivo:
        archivo.write(linea + "\n")


# ============================================================
# CONTROL DEL ARCHIVO DE BLOQUEO
# ============================================================

def proceso_esta_activo(pid: int) -> bool:
    """Comprueba en Windows si un PID continúa activo."""
    if pid <= 0:
        return False

    try:
        resultado = subprocess.run(
            [
                "tasklist",
                "/FI",
                f"PID eq {pid}",
                "/FO",
                "CSV",
                "/NH",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        salida = resultado.stdout.strip()

        if not salida:
            return False

        if salida.startswith("INFO:"):
            return False

        if "No tasks are running" in salida:
            return False

        return f'"{pid}"' in salida

    except Exception as error:
        escribir_log(
            f"No se pudo comprobar el PID {pid}: {error}"
        )
        return False


def bloqueo_es_antiguo() -> bool:
    """Comprueba si el archivo de bloqueo tiene más de 30 minutos."""
    try:
        fecha_modificacion = ARCHIVO_BLOQUEO.stat().st_mtime
        antiguedad = time.time() - fecha_modificacion

        return antiguedad > TIEMPO_MAXIMO_BLOQUEO

    except OSError:
        return True


def crear_bloqueo() -> None:
    """
    Crea el archivo de bloqueo.

    Si encuentra un bloqueo anterior:
    - comprueba su antigüedad;
    - lee el PID guardado;
    - comprueba si ese proceso continúa activo;
    - elimina automáticamente bloqueos abandonados.
    """
    if ARCHIVO_BLOQUEO.exists():
        try:
            contenido = ARCHIVO_BLOQUEO.read_text(
                encoding="utf-8"
            ).strip()

            pid_anterior = int(contenido)

            if bloqueo_es_antiguo():
                escribir_log(
                    "Se encontró un bloqueo antiguo de más de "
                    "30 minutos. Se eliminará automáticamente."
                )

                ARCHIVO_BLOQUEO.unlink(missing_ok=True)

            elif proceso_esta_activo(pid_anterior):
                escribir_log(
                    "Se canceló porque ya existe otra "
                    f"sincronización activa. PID: {pid_anterior}."
                )
                sys.exit(0)

            else:
                escribir_log(
                    "Se encontró un bloqueo abandonado. "
                    f"El PID {pid_anterior} ya no está activo. "
                    "Se eliminará automáticamente."
                )

                ARCHIVO_BLOQUEO.unlink(missing_ok=True)

        except (ValueError, OSError) as error:
            escribir_log(
                "El archivo de bloqueo estaba dañado o era inválido. "
                f"Se eliminará. Detalle: {error}"
            )

            try:
                ARCHIVO_BLOQUEO.unlink(missing_ok=True)
            except OSError as error_eliminacion:
                raise RuntimeError(
                    "No se pudo eliminar el bloqueo inválido: "
                    f"{error_eliminacion}"
                ) from error_eliminacion

    try:
        descriptor = os.open(
            str(ARCHIVO_BLOQUEO),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )

        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            archivo.write(str(os.getpid()))

        escribir_log(
            f"Bloqueo creado correctamente. PID: {os.getpid()}."
        )

    except FileExistsError:
        escribir_log(
            "Se canceló porque otra sincronización creó "
            "el bloqueo al mismo tiempo."
        )
        sys.exit(0)


def eliminar_bloqueo() -> None:
    """
    Elimina el archivo de bloqueo únicamente si pertenece
    al proceso actual.
    """
    try:
        if not ARCHIVO_BLOQUEO.exists():
            return

        contenido = ARCHIVO_BLOQUEO.read_text(
            encoding="utf-8"
        ).strip()

        pid_bloqueo = int(contenido)
        pid_actual = os.getpid()

        if pid_bloqueo == pid_actual:
            ARCHIVO_BLOQUEO.unlink(missing_ok=True)

            escribir_log(
                "Archivo de bloqueo eliminado correctamente."
            )
        else:
            escribir_log(
                "No se eliminó el bloqueo porque pertenece "
                f"a otro proceso. PID del bloqueo: {pid_bloqueo}."
            )

    except ValueError:
        escribir_log(
            "El archivo de bloqueo tenía un contenido inválido. "
            "Se intentará eliminar."
        )

        try:
            ARCHIVO_BLOQUEO.unlink(missing_ok=True)
        except OSError as error:
            escribir_log(
                f"No se pudo eliminar el bloqueo inválido: {error}"
            )

    except OSError as error:
        escribir_log(
            f"No se pudo eliminar el archivo de bloqueo: {error}"
        )


# ============================================================
# VALIDACIÓN DE ARCHIVOS
# ============================================================

def validar_archivos() -> None:
    """Comprueba que existan los archivos necesarios."""
    if not RUTA_EXCEL.exists():
        raise FileNotFoundError(
            f"No se encontró el Excel: {RUTA_EXCEL}"
        )

    if not RUTA_SINCRONIZADOR.exists():
        raise FileNotFoundError(
            f"No se encontró el sincronizador: "
            f"{RUTA_SINCRONIZADOR}"
        )


# ============================================================
# ACTUALIZACIÓN DE EXCEL Y POWER QUERY
# ============================================================

def actualizar_excel() -> None:
    """Abre Excel, actualiza Power Query, guarda y cierra."""
    escribir_log("Abriendo Excel en segundo plano.")

    excel = None
    libro = None

    try:
        excel = win32com.client.DispatchEx(
            "Excel.Application"
        )

        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AskToUpdateLinks = False

        libro = excel.Workbooks.Open(
            str(RUTA_EXCEL),
            UpdateLinks=3,
            ReadOnly=False,
        )

        escribir_log("Actualizando Power Query.")

        libro.RefreshAll()

        inicio = time.time()

        try:
            excel.CalculateUntilAsyncQueriesDone()
        except Exception as error:
            escribir_log(
                "CalculateUntilAsyncQueriesDone no estuvo "
                f"disponible: {error}"
            )

        while True:
            tiempo_transcurrido = time.time() - inicio

            if tiempo_transcurrido > TIEMPO_MAXIMO_ACTUALIZACION:
                raise TimeoutError(
                    "Power Query superó el tiempo máximo "
                    "de 10 minutos."
                )

            actualizando = False

            for conexion in libro.Connections:
                try:
                    if conexion.OLEDBConnection.Refreshing:
                        actualizando = True
                        break
                except Exception:
                    pass

                try:
                    if conexion.ODBCConnection.Refreshing:
                        actualizando = True
                        break
                except Exception:
                    pass

            if not actualizando:
                break

            time.sleep(ESPERA_ENTRE_REVISIONES)

        excel.CalculateFull()
        libro.Save()

        escribir_log("Excel actualizado y guardado.")

    finally:
        if libro is not None:
            try:
                libro.Close(SaveChanges=True)
            except Exception as error:
                escribir_log(
                    f"No se pudo cerrar el libro normalmente: {error}"
                )

        if excel is not None:
            try:
                excel.Quit()
            except Exception as error:
                escribir_log(
                    f"No se pudo cerrar Excel normalmente: {error}"
                )


# ============================================================
# SINCRONIZACIÓN CON NEON
# ============================================================

def sincronizar_neon() -> None:
    """Ejecuta el sincronizador que sube los datos a Neon."""
    escribir_log("Sincronizando con Neon.")

    resultado = subprocess.run(
        [
            sys.executable,
            str(RUTA_SINCRONIZADOR),
        ],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=TIEMPO_MAXIMO_SINCRONIZADOR,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    if resultado.stdout:
        for linea in resultado.stdout.splitlines():
            escribir_log(
                f"SINCRONIZADOR: {linea}"
            )

    if resultado.stderr:
        for linea in resultado.stderr.splitlines():
            escribir_log(
                f"ERROR SINCRONIZADOR: {linea}"
            )

    if resultado.returncode != 0:
        raise RuntimeError(
            "El sincronizador terminó con código "
            f"{resultado.returncode}."
        )

    escribir_log("Neon actualizado correctamente.")


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

def main() -> None:
    """Ejecuta todo el proceso de ServiSync."""
    crear_bloqueo()

    try:
        escribir_log("=" * 50)
        escribir_log("Inicio de ServiSync.")

        validar_archivos()
        actualizar_excel()
        sincronizar_neon()

        escribir_log("ServiSync terminó correctamente.")

    except subprocess.TimeoutExpired as error:
        escribir_log(
            "ServiSync terminó con error de tiempo máximo: "
            f"{error}"
        )

        for linea in traceback.format_exc().splitlines():
            escribir_log(
                f"DETALLE: {linea}"
            )

        sys.exit(1)

    except Exception as error:
        escribir_log(
            "ServiSync terminó con error: "
            f"{type(error).__name__}: {error}"
        )

        for linea in traceback.format_exc().splitlines():
            escribir_log(
                f"DETALLE: {linea}"
            )

        sys.exit(1)

    finally:
        eliminar_bloqueo()
        escribir_log("=" * 50)


if __name__ == "__main__":
    main()