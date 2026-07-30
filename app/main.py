import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import unicodedata
import re
import os
import io
import hashlib
import speech_recognition as sr


# ==================================================
# CONFIGURACIÓN DE LA APP
# ==================================================

st.set_page_config(
    page_title="Asistente de Bodega IA",
    page_icon="🤖",
    layout="wide"
)


# ==================================================
# FUNCIONES GENERALES
# ==================================================

def normalizar(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )

    texto = re.sub(
        r"[^a-z0-9\- ]+",
        " ",
        texto
    )

    return " ".join(
        texto.split()
    )


def limpiar_codigo(texto):
    texto = normalizar(texto)

    return re.sub(
        r"[^a-z0-9]",
        "",
        texto
    )


def aplicar_sinonimos(texto):
    texto = normalizar(texto)

    sinonimos = {
        "embrage": "embrague",
        "embreague": "embrague",
        "clutch": "embrague",

        "disko": "disco",
        "diskos": "disco",
        "discos": "disco",
        "disc": "disco",

        "pastilla": "past",
        "pastillas": "past",

        "zapata": "zapata",
        "zapatas": "zapata",

        "ruliman": "ruliman",
        "rulimanes": "ruliman",
        "rodamiento": "ruliman",
        "rodamientos": "ruliman",
        "balinera": "ruliman",

        "bt 50": "bt50",
        "bt-50": "bt50",

        "t 60": "t60",
        "t-60": "t60",
    }

    for palabra, reemplazo in sinonimos.items():
        texto = texto.replace(
            palabra,
            reemplazo
        )

    return texto


def limpiar_consulta(texto):
    texto = aplicar_sinonimos(texto)

    palabras_ignorar = {
        "donde",
        "esta",
        "estan",
        "hay",

        "el",
        "la",
        "los",
        "las",

        "de",
        "del",
        "para",

        "un",
        "una",

        "quiero",
        "necesito",

        "busco",
        "buscar",

        "muestrame",
        "dame",

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

        "en",
        "mi"
    }

    palabras = texto.split()

    palabras_limpias = [
        palabra
        for palabra in palabras
        if palabra not in palabras_ignorar
    ]

    return " ".join(
        palabras_limpias
    )

# ==================================================
# MEMORIA DE CONTEXTO DE CONVERSACIÓN
# ==================================================

def construir_consulta_con_contexto(
    pregunta,
    contexto_anterior
):

    pregunta_normalizada = normalizar(
        pregunta
    )

    if not contexto_anterior:
        return pregunta

    frases_dependientes = [
        "solo",
        "solamente",
        "de esos",
        "de esas",
        "esos",
        "esas",
        "cuantos tengo",
        "cuanto tengo",
        "cuantas tengo",
        "donde estan",
        "donde esta",
        "y en norte",
        "y en norte fgs"
    ]

    usa_contexto = any(
        frase in pregunta_normalizada
        for frase in frases_dependientes
    )

    if usa_contexto:

        return (
            contexto_anterior
            + " "
            + pregunta
        )

    return pregunta

def convertir_cantidad(valor):
    try:
        texto = str(valor).strip()

        texto = texto.replace(
            " ",
            ""
        )

        texto = texto.replace(
            ",",
            "."
        )

        return float(
            texto
        )

    except (ValueError, TypeError):
        return 0.0


# ==================================================
# DETECTAR TIPO DE CONSULTA
# ==================================================

def es_consulta_cantidad(pregunta):
    texto = normalizar(pregunta)

    palabras_cantidad = {
        "cuanto",
        "cuantos",
        "cuanta",
        "cuantas",
        "cantidad",
        "stock",
        "total",
    }

    return any(
        palabra in texto.split()
        for palabra in palabras_cantidad
    )


def es_consulta_ubicacion(pregunta):
    texto = normalizar(pregunta)

    frases = [
        "donde",
        "ubicacion",
        "ubicaciones",
        "en que ubicacion",
        "en que bodega",
    ]

    return any(
        frase in texto
        for frase in frases
    )


def detectar_almacen_consulta(pregunta):
    texto = normalizar(pregunta)

    # Revisar primero NORTE FGS
    if "norte fgs" in texto:
        return "NORTE FGS"

    if "norte" in texto:
        return "NORTE"

    return None


def filtrar_por_almacen(
    resultados,
    almacen_solicitado
):
    if not almacen_solicitado:
        return resultados

    return [
        producto
        for producto in resultados
        if normalizar(
            producto.get(
                "ALMACEN",
                ""
            )
        )
        ==
        normalizar(
            almacen_solicitado
        )
    ]


# ==================================================
# BUSCAR LOGO DE MARCA
# ==================================================

def obtener_logo_marca(marca):
    marca_normalizada = normalizar(
        marca
    )

    mapa_nombres = {
        "borg wagner": "BORG WAGNER",
        "daikin": "DAIKIN",

        "g-control": "gcontrol",
        "g control": "gcontrol",
        "gcontrol": "gcontrol",

        "gkp": "gkp",
        "gsp": "GSP",

        "hipper freios": "hf",
        "hipper": "hf",

        "hi-q": "hi_q",
        "hi q": "hi_q",
        "hiq": "hi_q",

        "ichiban": "Ichiban",
        "kashima": "kashima",
        "koyo": "koyo",
        "kuruma": "kuruma",

        "luk": "LUK",
        "mobis": "mobis",
        "mrk": "MRK",
        "nachi": "Nachi",
        "nova": "nova",
        "nsk": "NSK",
        "ntn": "NTN",
        "nwo": "NWO",
        "seco": "SECO",
        "shibumi": "shibumi",

        "silver green": "Silver Green",
        "silvergreen": "Silver Green",

        "skf": "skf",

        "valeo": "valo",
        "phc valeo": "valo",

        "x-brake": "X-BRAKE",
        "x brake": "X-BRAKE",

        "yes-q": "YES_Q",
        "yes q": "YES_Q",
        "yes quality": "yes_quality",

        "yq": "yes_quality",
        "yq drum": "YQ_DRUM",
    }

    nombre_archivo = mapa_nombres.get(
        marca_normalizada
    )

    if not nombre_archivo:
        return None

    extensiones = [
        ".png",
        ".jpg",
        ".jpeg",
        ".PNG",
        ".JPG",
        ".JPEG"
    ]

    for extension in extensiones:

        ruta = os.path.join(
            "imagenes",
            "marcas",
            nombre_archivo
            + extension
        )

        if os.path.exists(
            ruta
        ):
            return ruta

    return None


# ==================================================
# BÚSQUEDA INTELIGENTE
# ==================================================

def buscar_productos(
    df,
    consulta
):

    consulta_original = normalizar(
        consulta
    )

    consulta_limpia = limpiar_consulta(
        consulta
    )

    if not consulta_limpia:
        return []

    resultados = []


    # ==================================================
    # 1. BUSCAR CÓDIGO EXACTO DENTRO DE FRASE
    #
    # Ejemplo:
    # cuanto tengo de YQ4908
    # ==================================================

    palabras_consulta = (
        consulta_original
        .replace(
            "?",
            " "
        )
        .split()
    )

    codigos_consulta = [
        limpiar_codigo(
            palabra
        )
        for palabra in palabras_consulta
        if limpiar_codigo(
            palabra
        )
    ]

    filas_codigo_exacto = []

    for _, fila in df.iterrows():

        codigo_fila = limpiar_codigo(
            fila[
                "CODIGO"
            ]
        )

        if codigo_fila in codigos_consulta:

            producto = fila.to_dict()

            producto[
                "PUNTAJE"
            ] = 3000

            filas_codigo_exacto.append(
                producto
            )


    # Devuelve todas las filas del código.
    # Por ejemplo NORTE y NORTE FGS.

    if filas_codigo_exacto:

        return filas_codigo_exacto


    # ==================================================
    # 2. CÓDIGO PARCIAL
    #
    # 4908 encuentra YQ4908
    # ==================================================

    if len(
        consulta_limpia.split()
    ) == 1:

        consulta_codigo = limpiar_codigo(
            consulta_limpia
        )

        if len(
            consulta_codigo
        ) >= 3:

            for _, fila in df.iterrows():

                codigo = limpiar_codigo(
                    fila[
                        "CODIGO"
                    ]
                )

                if consulta_codigo in codigo:

                    producto = (
                        fila.to_dict()
                    )

                    producto[
                        "PUNTAJE"
                    ] = 2500

                    resultados.append(
                        producto
                    )

            if resultados:

                return resultados


    # ==================================================
    # 3. BÚSQUEDA POR:
    #
    # ARTÍCULO
    # MARCA
    # ALMACÉN
    # UBICACIÓN
    # ==================================================

    palabras_busqueda = (
        consulta_limpia.split()
    )

    for _, fila in df.iterrows():

        articulo = aplicar_sinonimos(
            fila.get(
                "ARTICULO",
                ""
            )
        )

        marca = aplicar_sinonimos(
            fila.get(
                "MARCA",
                ""
            )
        )

        almacen = aplicar_sinonimos(
            fila.get(
                "ALMACEN",
                ""
            )
        )

        ubicacion = aplicar_sinonimos(
            fila.get(
                "UBICACION",
                ""
            )
        )

        codigo = aplicar_sinonimos(
            fila.get(
                "CODIGO",
                ""
            )
        )

        texto_producto = (
            codigo
            + " "
            + articulo
            + " "
            + marca
            + " "
            + almacen
            + " "
            + ubicacion
        )

        palabras_producto = (
            texto_producto.split()
        )

        puntajes = []


        for palabra_busqueda in palabras_busqueda:


            # Coincidencia exacta

            if (
                palabra_busqueda
                in palabras_producto
            ):

                puntajes.append(
                    100
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

                for palabra_producto
                in palabras_producto

                if (
                    len(
                        palabra_producto
                    ) >= 3

                    and

                    len(
                        palabra_busqueda
                    ) >= 3
                )

            )


            if coincidencia_parcial:

                puntajes.append(
                    95
                )

                continue


            # Coincidencia aproximada

            mejor_puntaje = max(

                (

                    fuzz.ratio(
                        palabra_busqueda,
                        palabra_producto
                    )

                    for palabra_producto
                    in palabras_producto

                ),

                default=0

            )


            puntajes.append(
                mejor_puntaje
            )


        if puntajes:

            coincidencias_buenas = sum(

                puntaje >= 70

                for puntaje
                in puntajes

            )


            porcentaje_coincidencia = (

                coincidencias_buenas

                /

                len(
                    puntajes
                )

            )


            if porcentaje_coincidencia >= 0.75:

                puntaje_final = (

                    sum(
                        puntajes
                    )

                    /

                    len(
                        puntajes
                    )

                )


                producto = (
                    fila.to_dict()
                )


                producto[
                    "PUNTAJE"
                ] = puntaje_final


                resultados.append(
                    producto
                )


    resultados.sort(

        key=lambda x: x[
            "PUNTAJE"
        ],

        reverse=True

    )


    return resultados[:500]


# ==================================================
# AGRUPAR RESULTADOS POR CÓDIGO
# ==================================================

def agrupar_resultados_por_codigo(
    resultados
):

    grupos = {}


    for producto in resultados:


        codigo = str(

            producto.get(
                "CODIGO",
                ""
            )

        ).strip()


        clave = limpiar_codigo(
            codigo
        )


        if clave not in grupos:


            grupos[
                clave
            ] = {

                "CODIGO":
                codigo,

                "ARTICULO":
                producto.get(
                    "ARTICULO",
                    ""
                ),

                "MARCA":
                producto.get(
                    "MARCA",
                    "SIN MARCA"
                ),

                "FILAS":
                [],

                "TOTAL":
                0.0

            }


        cantidad = convertir_cantidad(

            producto.get(

                "CANTIDAD",

                0

            )

        )


        grupos[
            clave
        ][
            "FILAS"
        ].append(
            producto
        )


        grupos[
            clave
        ][
            "TOTAL"
        ] += cantidad


    return list(
        grupos.values()
    )


# ==================================================
# TRANSCRIBIR AUDIO
# ==================================================

def transcribir_audio(
    audio_file
):

    reconocedor = sr.Recognizer()


    try:

        audio_bytes = (
            audio_file.getvalue()
        )


        audio_stream = io.BytesIO(
            audio_bytes
        )


        with sr.AudioFile(
            audio_stream
        ) as fuente:

            audio_data = (
                reconocedor.record(
                    fuente
                )
            )


        texto = (
            reconocedor
            .recognize_google(

                audio_data,

                language="es-EC"

            )
        )


        return (
            texto,
            None
        )


    except sr.UnknownValueError:

        return (

            None,

            "No pude entender el audio. "
            "Prueba hablando más despacio "
            "y cerca del micrófono."

        )


    except sr.RequestError as error:

        return (

            None,

            "No pude conectar con el "
            "servicio de reconocimiento de voz. "
            f"Detalle: {error}"

        )


    except Exception as error:

        return (

            None,

            "Ocurrió un error al procesar "
            "el audio. "
            f"Detalle: {error}"

        )


# ==================================================
# DISEÑO PERSONALIZADO
# ==================================================

st.markdown(
    """
<style>

.stApp {

    background:
    linear-gradient(
        135deg,
        #f5f7fa,
        #eef3f8
    );

}


h1,
h2,
h3 {

    color:
    #0b3c5d;

    font-family:
    Arial,
    sans-serif;

}


/* Chat usuario */

[data-testid="stChatMessage"]:has(
    [data-testid="chatAvatarIcon-user"]
) {

    background-color:
    #e8f1f8;

    border-radius:
    18px;

    padding:
    10px;

}


/* Chat asistente */

[data-testid="stChatMessage"]:has(
    [data-testid="chatAvatarIcon-assistant"]
) {

    background-color:
    #fff4e8;

    border-radius:
    18px;

    padding:
    10px;

}


/* Sidebar */

[data-testid="stSidebar"] {

    background-color:
    #0b3c5d;

}


[data-testid="stSidebar"] * {

    color:
    white;

}


/* Ocultar menú */

#MainMenu {

    visibility:
    hidden;

}


footer {

    visibility:
    hidden;

}

</style>
""",

    unsafe_allow_html=True

)


# ==================================================
# ENCABEZADO
# ==================================================

col_logo, col_titulo = st.columns(
    [
        1,
        5
    ]
)


with col_logo:


    if os.path.exists(
        "imagenes/logo.png"
    ):


        st.image(

            "imagenes/logo.png",

            width=220

        )


with col_titulo:


    st.markdown(
        """
# Asistente Inteligente de Inventario

### Serviembragues y Partes

Consulta códigos, productos, marcas, stock y ubicaciones.
"""
    )


# ==================================================
# CARGAR INVENTARIO
# ==================================================

try:


    df = pd.read_excel(

        "datos/inventario.xlsx",

        dtype=str

    )


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


    # ==================================================
    # CARGAR MARCAS
    # ==================================================


    df_marcas = pd.read_excel(

        "datos/marcas.xls",

        dtype=str

    )


    df_marcas.columns = (

        df_marcas.columns

        .astype(str)

        .str.strip()

        .str.upper()

    )


    for columna in df_marcas.columns:


        df_marcas[columna] = (

            df_marcas[columna]

            .fillna("")

            .astype(str)

            .str.strip()

        )


    # ==================================================
    # ELIMINAR DUPLICADOS DE MARCA
    # ==================================================

    df_marcas = (

        df_marcas

        .drop_duplicates(

            subset=[
                "CODIGO"
            ],

            keep="first"

        )

    )


    # ==================================================
    # UNIR INVENTARIO + MARCAS
    # ==================================================

    df = df.merge(


        df_marcas[

            [

                "CODIGO",

                "MARCA"

            ]

        ],


        on="CODIGO",


        how="left"

    )


    df[
        "MARCA"
    ] = (

        df[
            "MARCA"
        ]

        .fillna(
            "SIN MARCA"
        )

        .astype(str)

        .str.strip()

    )


except Exception as error:


    st.error(

        f"""
❌ Error al cargar las bases:

{error}
"""

    )


    st.stop()


# ==================================================
# MENÚ LATERAL
# ==================================================

with st.sidebar:


    if os.path.exists(
        "imagenes/logo.png"
    ):


        st.image(

            "imagenes/logo.png",

            use_container_width=True

        )


    st.markdown(
        "## Menú"
    )


    opcion = st.radio(


        "",


        [

            "🤖 Asistente IA",

            "📦 Buscar Productos",

            "📍 Ubicaciones",

            "📊 Inventario"

        ]

    )


    st.markdown(
        "---"
    )


    if st.button(

        "🗑️ Nueva conversación",

        use_container_width=True

    ):


        st.session_state.mensajes = []
        st.session_state.contexto_busqueda = ""


        st.session_state.pop(

            "pregunta_pendiente",

            None

        )


        st.session_state.pop(

            "ultimo_audio_hash",

            None

        )


        st.rerun()


    st.markdown(
        "---"
    )


    st.write(
        "Serviembragues y Partes"
    )


# ==================================================
# HISTORIAL
# ==================================================

if (
    "mensajes"
    not in
    st.session_state
):


    st.session_state.mensajes = []
    # ==================================================
# MEMORIA DEL CONTEXTO
# ==================================================

if "contexto_busqueda" not in st.session_state:

    st.session_state.contexto_busqueda = ""


# ==================================================
# MENSAJE INICIAL
# ==================================================

if len(
    st.session_state.mensajes
) == 0:


    with st.chat_message(
        "assistant"
    ):


        st.markdown(
            """
👋 Hola. Soy tu **Asistente de Bodega IA**.

Puedes escribir o grabar consultas como:

- `YQ4908`
- `cuanto tengo de YQ4908`
- `cuanto tengo de YQ4908 en NORTE`
- `cuanto tengo de YQ4908 en NORTE FGS`
- `donde esta YQ4908`
- `cuantos discos de freno tengo`
- `embrague sail`
- `disco bt50`
"""
        )


# ==================================================
# MOSTRAR HISTORIAL
# ==================================================

for mensaje in (

    st.session_state.mensajes

):


    with st.chat_message(

        mensaje[
            "rol"
        ]

    ):


        st.markdown(

            mensaje[
                "texto"
            ]

        )


# ==================================================
# ENTRADA POR VOZ
# ==================================================

st.markdown(
    "### 🎤 Consulta por voz"
)


audio_voz = st.audio_input(

    "Graba tu consulta y luego presiona detener",

    key="audio_consulta"

)


if audio_voz is not None:


    audio_bytes = (
        audio_voz.getvalue()
    )


    audio_hash = hashlib.md5(

        audio_bytes

    ).hexdigest()


    ultimo_audio_hash = (

        st.session_state.get(

            "ultimo_audio_hash"

        )

    )


    # Evitar procesar el mismo audio varias veces

    if audio_hash != ultimo_audio_hash:


        with st.spinner(

            "🎤 Transcribiendo audio..."

        ):


            texto_transcrito, error_audio = (

                transcribir_audio(

                    audio_voz

                )

            )


        st.session_state[

            "ultimo_audio_hash"

        ] = audio_hash


        if texto_transcrito:


            st.success(

                f"🎤 Entendí: "
                f"{texto_transcrito}"

            )


            st.session_state[

                "pregunta_pendiente"

            ] = texto_transcrito


        elif error_audio:


            st.warning(

                error_audio

            )


# ==================================================
# ENTRADA POR TEXTO
# ==================================================

pregunta_texto = st.chat_input(

    "¿Qué deseas buscar?"

)


if pregunta_texto:


    st.session_state[

        "pregunta_pendiente"

    ] = pregunta_texto


# ==================================================
# RECUPERAR PREGUNTA
# ==================================================

pregunta = st.session_state.get(

    "pregunta_pendiente"

)


# ==================================================
# PROCESAR PREGUNTA
# ==================================================

if pregunta:


    st.session_state.pop(

        "pregunta_pendiente",

        None

    )


    st.session_state.mensajes.append(

        {

            "rol":
            "user",

            "texto":
            pregunta

        }

    )


    with st.chat_message(
        "user"
    ):


        st.markdown(
            pregunta
        )


# ==================================================
# CONSTRUIR CONSULTA CON MEMORIA
# ==================================================

consulta_completa = construir_consulta_con_contexto(

    pregunta,

    st.session_state.contexto_busqueda

)


# ==================================================
# BUSCAR
# ==================================================

resultados = buscar_productos(

    df,

    consulta_completa

)


# ==================================================
# ACTUALIZAR MEMORIA DEL ASISTENTE
# ==================================================

if resultados:

    pregunta_normalizada_contexto = normalizar(
        pregunta
    )

    frases_dependientes_contexto = [
        "solo",
        "solamente",
        "de esos",
        "de esas",
        "cuantos tengo",
        "cuanto tengo",
        "cuantas tengo",
        "donde estan",
        "donde esta",
        "y en norte",
        "y en norte fgs"
    ]

    es_dependiente = any(

        frase in pregunta_normalizada_contexto

        for frase in frases_dependientes_contexto

    )

    if es_dependiente:

        st.session_state.contexto_busqueda = (
            consulta_completa
        )

    else:

        st.session_state.contexto_busqueda = (
            pregunta
        )

    consulta_cantidad = (

        es_consulta_cantidad(

            pregunta

        )

    )


    consulta_ubicacion = (

        es_consulta_ubicacion(

            pregunta

        )

    )


    almacen_solicitado = (

        detectar_almacen_consulta(

            pregunta

        )

    )


    resultados_filtrados = (

        filtrar_por_almacen(

            resultados,

            almacen_solicitado

        )

    )


    # ==================================================
    # SIN RESULTADOS
    # ==================================================

    if not resultados:


        respuesta = f"""
😕 No encontré productos relacionados con:

**{pregunta}**
"""


        st.session_state.mensajes.append(

            {

                "rol":
                "assistant",

                "texto":
                respuesta

            }

        )


        with st.chat_message(
            "assistant"
        ):


            st.markdown(
                respuesta
            )


    # ==================================================
    # ALMACÉN SOLICITADO SIN RESULTADOS
    # ==================================================

    elif (

        almacen_solicitado

        and

        not resultados_filtrados

    ):


        respuesta = f"""
📦 Encontré el producto, pero no tiene stock registrado en:

### **{almacen_solicitado}**
"""


        st.session_state.mensajes.append(

            {

                "rol":
                "assistant",

                "texto":
                respuesta

            }

        )


        with st.chat_message(
            "assistant"
        ):


            st.markdown(
                respuesta
            )


    # ==================================================
    # CONSULTA DE UBICACIÓN
    # ==================================================

    elif consulta_ubicacion:


        grupos = agrupar_resultados_por_codigo(

            resultados_filtrados

        )


        respuesta = (

            "📍 **Ubicaciones encontradas:**\n\n"

        )


        for grupo in grupos[:20]:


            respuesta += (

                f"### 📦 "
                f"{grupo['CODIGO']}\n\n"

                f"**"
                f"{grupo['ARTICULO']}"
                f"**\n\n"

            )


            ubicaciones_vistas = set()


            for fila in grupo["FILAS"]:


                almacen = str(

                    fila.get(

                        "ALMACEN",

                        ""

                    )

                ).strip()


                ubicacion = str(

                    fila.get(

                        "UBICACION",

                        ""

                    )

                ).strip()


                clave = (

                    normalizar(
                        almacen
                    ),

                    normalizar(
                        ubicacion
                    )

                )


                if clave in ubicaciones_vistas:

                    continue


                ubicaciones_vistas.add(

                    clave

                )


                respuesta += (

                    f"🏬 **"
                    f"{almacen}"
                    f"** — "

                    f"📍 **"
                    f"{ubicacion}"
                    f"**\n\n"

                )


        st.session_state.mensajes.append(

            {

                "rol":
                "assistant",

                "texto":
                respuesta

            }

        )


        with st.chat_message(
            "assistant"
        ):


            st.markdown(
                respuesta
            )


    # ==================================================
    # CONSULTA DE CANTIDAD
    # ==================================================

    elif consulta_cantidad:


        total_stock = sum(


            convertir_cantidad(

                producto.get(

                    "CANTIDAD",

                    0

                )

            )


            for producto
            in resultados_filtrados

        )


        if almacen_solicitado:


            respuesta = f"""
## 📦 Stock en {almacen_solicitado}

### **{total_stock:g} unidades**
"""


        else:


            respuesta = f"""
## 📦 Stock total

### **{total_stock:g} unidades**
"""


        st.session_state.mensajes.append(

            {

                "rol":
                "assistant",

                "texto":
                respuesta

            }

        )


        with st.chat_message(
            "assistant"
        ):


            st.markdown(
                respuesta
            )


    # ==================================================
    # CONSULTA NORMAL
    # MOSTRAR FICHA AGRUPADA
    # ==================================================

    else:


        grupos = agrupar_resultados_por_codigo(

            resultados_filtrados

        )


        respuesta = (

            f"🔎 Encontré "
            f"**{len(grupos)} producto(s)**."

        )


        st.session_state.mensajes.append(

            {

                "rol":
                "assistant",

                "texto":
                respuesta

            }

        )


        with st.chat_message(
            "assistant"
        ):


            st.markdown(
                respuesta
            )


            for grupo in grupos[:20]:


                st.markdown(
                    "---"
                )


                col_marca, col_info = st.columns(

                    [

                        1,

                        5

                    ]

                )


                # ======================================
                # LOGO MARCA
                # ======================================

                with col_marca:


                    logo_marca = obtener_logo_marca(

                        grupo.get(

                            "MARCA",

                            ""

                        )

                    )


                    if logo_marca:


                        st.image(

                            logo_marca,

                            width=120

                        )


                    else:


                        st.markdown(
                            "### 🏷️"
                        )


                # ======================================
                # FICHA AGRUPADA
                # ======================================

                with col_info:


                    st.markdown(

                        f"""
### 📦 {grupo['CODIGO']}

🏷️ **Marca:** {grupo.get('MARCA', 'SIN MARCA')}

**Artículo:** {grupo['ARTICULO']}
"""

                    )


                    almacenes = {}


                    for fila in grupo[

                        "FILAS"

                    ]:


                        almacen = str(

                            fila.get(

                                "ALMACEN",

                                ""

                            )

                        ).strip()


                        ubicacion = str(

                            fila.get(

                                "UBICACION",

                                ""

                            )

                        ).strip()


                        cantidad = convertir_cantidad(

                            fila.get(

                                "CANTIDAD",

                                0

                            )

                        )


                        if almacen not in almacenes:


                            almacenes[

                                almacen

                            ] = {

                                "cantidad":
                                0.0,

                                "ubicaciones":
                                set()

                            }


                        almacenes[

                            almacen

                        ][

                            "cantidad"

                        ] += cantidad


                        if ubicacion:


                            almacenes[

                                almacen

                            ][

                                "ubicaciones"

                            ].add(

                                ubicacion

                            )


                    for almacen, datos in (

                        almacenes.items()

                    ):


                        ubicaciones_texto = (

                            ", ".join(

                                sorted(

                                    datos[

                                        "ubicaciones"

                                    ]

                                )

                            )

                            if datos[

                                "ubicaciones"

                            ]

                            else

                            "Sin ubicación"

                        )


                        st.markdown(

                            f"""
🏬 **{almacen}**

📍 {ubicaciones_texto}

📦 **{datos['cantidad']:g} unidades**
"""

                        )


                    st.success(

                        f"📊 STOCK TOTAL: "
                        f"{grupo['TOTAL']:g} unidades"

                    )