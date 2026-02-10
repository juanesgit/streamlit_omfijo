import streamlit as st
import utilidades as util
import pandas as pd
from sqlalchemy import create_engine
import numpy as np
import data_utils as du
import os
import time
from datetime import datetime, timedelta
import auth

st.set_page_config(
    layout="wide", initial_sidebar_state="collapsed"
)  # Habilitar pantalla ancha

# Requerir autenticación antes de continuar
auth.require_login("Seguimiento O&M R3")

usuario = "ccot"
contraseña = "ccot"
host = "10.108.34.32"  # O la IP del servidor MySQL
puerto_mysql = "33063"
base_datos = "ccot"

# Crear engine con caché y variables de entorno
@st.cache_resource
def get_engine():
    user = os.getenv("DB_USER", usuario)
    password = os.getenv("DB_PASSWORD", contraseña)
    host_env = os.getenv("DB_HOST", host)
    port_env = os.getenv("DB_PORT", puerto_mysql)
    db_name = os.getenv("DB_NAME", base_datos)
    possible_paths = [
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
        "/app/.streamlit/secrets.toml",
        os.path.expanduser("~/.streamlit/secrets.toml"),
    ]
    if any(os.path.exists(p) for p in possible_paths):
        try:
            secrets = st.secrets
            if "DB_USER" in secrets:
                user = secrets["DB_USER"]
            if "DB_PASSWORD" in secrets:
                password = secrets["DB_PASSWORD"]
            if "DB_HOST" in secrets:
                host_env = secrets["DB_HOST"]
            if "DB_PORT" in secrets:
                port_env = secrets["DB_PORT"]
            if "DB_NAME" in secrets:
                db_name = secrets["DB_NAME"]
        except Exception:
            pass
    return create_engine(
        f"mysql+pymysql://{user}:{password}@{host_env}:{port_env}/{db_name}"
    )

qry = """
WITH tiempo_limite_cte AS (
    SELECT
        inc.`Orden de trabajo`,
        inc.`Tipo de trabajo`,
        fa.SEGMENTO,
        COALESCE(IF(INSTR(inc.`Ruta de clasificación`,'RUIDO')>0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') AS TIPIFICACION,
        inc.Prioridad,
        TIMESTAMPDIFF(MINUTE, inc.`Fecha de creación`, NOW()) AS TIEMPO_TRANSCURRIDO,
        CASE
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'AFECTACION' AND inc.Prioridad = 'ALTO' THEN 210
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'AFECTACION' AND inc.Prioridad = 'MEDIO' THEN 360
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'AFECTACION' AND inc.Prioridad = 'BAJO' THEN 720
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'DEGRADACION' AND inc.Prioridad = 'ALTO' THEN 570
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'DEGRADACION' AND inc.Prioridad = 'MEDIO' THEN 822
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'DEGRADACION' AND inc.Prioridad = 'BAJO' THEN 4380
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'RECLAMACION' THEN 720
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'QoE' THEN 240
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'RUIDO' AND inc.Prioridad = 'ALTO' THEN 720
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'RUIDO' AND inc.Prioridad = 'MEDIO' THEN 1440
            WHEN COALESCE(IF(INSTR(inc.`Ruta de clasificación`, 'RUIDO') > 0, 'RUIDO', UPPER(fa.familia)), 'SIN TIPIFICACION') = 'RUIDO' AND inc.Prioridad = 'BAJO' THEN 1440
            ELSE NULL
        END AS TIEMPO_LIMITE
    FROM ccot.incidentes inc
    LEFT JOIN ccot.familias fa
        ON inc.`Ruta de clasificación` = fa.`clasificación`
)
SELECT
    inc.`Orden de trabajo` AS ORDEN,
    UPPER(inc.`Descripción`) AS DESCRIPCION,
    fa.SEGMENTO,
    CASE
        WHEN UPPER(inc.Prioridad) = 'ALTO' THEN 'P1'
        WHEN UPPER(inc.Prioridad) = 'MEDIO' THEN 'P2'
        WHEN UPPER(inc.Prioridad) = 'BAJO' THEN 'P3'
        ELSE NULL
    END AS PRIORIDAD,
    inc.`Articulo de configuración` AS ARTICULO_CONFIG,
    UPPER(mnod.ID_NODO) UBICACION,
    inc.`Ubicación` AS UBICACION_MAXIMO,
    inc.`Ciudad / Municipio` AS CIUDAD,
    COALESCE(mnod.CIUDAD, mnods.CIUDAD) AS CIUDAD_ESTRUCTURA,
    inc.Departamento AS DEPARTAMENTO,
    inc.`OT WFM`,
    inc.Aliado AS `ALIADO MAX`,
    wf.Compañia AS `ALIADO WF`,
    inc.`Tipo de trabajo` AS TIPO,
    inc.Estado AS ESTADO_MAXIMO,
    UPPER(inc.`Descripcion estado`) AS DESC_ESTADO,
    inc.`Incidente relacionado` AS INCIDENTE_RELACIONADO,
    inc.`Clasificación` AS CLASIFICACION,
    inc.`Ruta de clasificación` AS RUTA_CLASIFICACION,
    inc.`Fecha de creación` AS FECHA_CREACION,
    CONCAT(
    LPAD(FLOOR(TIME_TO_SEC(TIMEDIFF(NOW(), inc.`Fecha de creación`)) / 3600), 2, '0'),
    ':',
    LPAD(MOD(TIME_TO_SEC(TIMEDIFF(NOW(), inc.`Fecha de creación`)) DIV 60, 60), 2, '0')
    ) AS TIEMPO,
    ROUND((TIMESTAMPDIFF(SECOND, inc.`Fecha de creación`, NOW()) / 86400),1) AS DIAS,
    t.TIEMPO_TRANSCURRIDO AS MIN,
    t.TIEMPO_LIMITE AS TIEMPO_LIMITE_SLA,
    UPPER(CONCAT(
    LPAD(FLOOR(t.TIEMPO_LIMITE / 60), 2, '0'),
    ':',
    LPAD(MOD(t.TIEMPO_LIMITE, 60), 2, '0')
    )) AS `TIEMPO SLA`,
    GREATEST(t.TIEMPO_LIMITE - t.TIEMPO_TRANSCURRIDO, 0) AS TIEMPO_RESTANTE_EN_MINUTOS,
    CONCAT(
    LPAD(FLOOR(GREATEST(t.TIEMPO_LIMITE - t.TIEMPO_TRANSCURRIDO, 0) / 60), 2, '0'),
    ':',
    LPAD(MOD(GREATEST(t.TIEMPO_LIMITE - t.TIEMPO_TRANSCURRIDO, 0), 60), 2, '0')
) AS `RESTANTE SLA`,
    IF(COALESCE(IF(INSTR(inc.`Ruta de clasificación`,'RUIDO')>0,"RUIDO",UPPER(fa.familia)),"SIN TIPIFICACION")="NOTIFICACION","NO APLICA",
    CASE
        WHEN GREATEST(t.TIEMPO_LIMITE - t.TIEMPO_TRANSCURRIDO, 0) > 0.2 * t.TIEMPO_LIMITE THEN 'EN TIEMPO'
        WHEN GREATEST(t.TIEMPO_LIMITE - t.TIEMPO_TRANSCURRIDO, 0) > 0 THEN 'PRÓXIMO A VENCER'
        ELSE 'VENCIDO'
    END) AS `CUMP SLA`,
    CASE
        WHEN TIMESTAMPDIFF(HOUR, inc.`Fecha de creación`, NOW()) < 24
            THEN '< 1 DÍA (0H - 24H)'
        WHEN TIMESTAMPDIFF(HOUR, inc.`Fecha de creación`, NOW()) BETWEEN 24 AND 47
            THEN '> 1 DÍA Y <= 2 DÍAS (24H - 48H)'
        WHEN TIMESTAMPDIFF(HOUR, inc.`Fecha de creación`, NOW()) BETWEEN 48 AND 71
            THEN '> 2 DÍAS Y <= 3 DÍAS (48H - 72H)'
        WHEN TIMESTAMPDIFF(HOUR, inc.`Fecha de creación`, NOW()) BETWEEN 72 AND 167
            THEN '> 3 DÍAS Y <= 7 DÍAS (72H - 168H)'
        WHEN TIMESTAMPDIFF(DAY, inc.`Fecha de creación`, NOW()) BETWEEN 8 AND 30
            THEN '> 7 DÍAS Y <= 30 DÍAS (8D - 30D)'
        WHEN TIMESTAMPDIFF(DAY, inc.`Fecha de creación`, NOW()) BETWEEN 31 AND 60
            THEN '> 30 DÍAS Y <= 60 DÍAS (31D - 60D)'
        ELSE
            '> 60 DÍAS (61D +)'
    END AS ANTIGÜEDAD,
    inc.`Inicio real` AS INICIO_REAL,
    inc.`Inicio programado` AS INICIO_PROGRAMADO,
    inc.`Estado Incidente` AS ESTADO_INCIDENTE,
    wf.Fecha AS FECHA_WF,
    DATE_ADD(wf.Fecha, INTERVAL wf.inicio HOUR_MINUTE) AS FECHA_INICIO_WF,
    UPPER(wf.`Técnico`) AS TECNICO,
    COALESCE(UPPER(wf.Ult_Estado),"SIN AGENDA") AS ESTADO,
    wf.Iniciado AS INICIADO, wf.Pendiente AS PENDIENTE, wf.Suspendido AS SUSPENDIDO, wf.Completado AS COMPLETADO, wf.Cancelado AS CANCELADO,
    COALESCE(
        CASE
            WHEN wf.`Tipo de Actividad` = 'CFIBRA' THEN 'CORRECTIVO FIBRA ÓPTICA'
            WHEN wf.`Tipo de Actividad` = 'CCOAX' THEN 'CORRECTIVO COAXIAL'
            WHEN wf.`Tipo de Actividad` IS NOT NULL
                THEN UPPER(REGEXP_REPLACE(wf.`Tipo de Actividad`, 'Planta Externa - | - CFIBRA| - CCOAX', ''))
        END,
        CASE
            WHEN inc.`Tipo de trabajo` = 'CFIBRA' THEN 'CORRECTIVO FIBRA ÓPTICA'
            WHEN inc.`Tipo de trabajo` = 'CCOAX' THEN 'CORRECTIVO COAXIAL'
            ELSE UPPER(inc.`Tipo de trabajo`)
        END
    ) AS TIPO_ACTIVIDAD,
    COALESCE(IF(INSTR(inc.`Ruta de clasificación`,'RUIDO')>0,"RUIDO",UPPER(fa.familia)),"SIN TIPIFICACION") AS TIPIFICACION,
    COALESCE(COALESCE(mnod.DISTRITO, mnods.DISTRITO),"SIN DISTRITO") AS DISTRITO,
    COALESCE(COALESCE(mnod.OPERA, mnods.OPERA),"SIN OPERA") AS OPERA,
    COALESCE(COALESCE(mnod.JEFE_INTEGRAL, mnods.JEFE_INTEGRAL),"SIN JEFE INTEGRAL") AS `JEFE INTEGRAL`,
    inc.`Fecha_carga` AS FECHA_ACTUALIZACION_MAXIMO,
    wf.`Fecha_Actualizacion` AS FECHA_ACTUALIZACION_AGENDA,
    COALESCE(mnod.RED, mnods.RED) AS RED,
    COALESCE(COALESCE(bs1.`SITE Owner`, bs2.`SITE Owner`), 'SIN OWNER') AS `OWNER`
FROM ccot.incidentes inc
LEFT JOIN tiempo_limite_cte t ON inc.`Orden de trabajo` = t.`Orden de trabajo`
LEFT JOIN ccot.wf_om_back wf ON inc.`Orden de trabajo` = wf.`Orden de trabajo`
LEFT JOIN ccot.familias fa ON inc.`Ruta de clasificación` = fa.`clasificación`
LEFT JOIN ccot.nodos_marca_om mnod ON mnod.NODO_TK = inc.`Articulo de configuración`
LEFT JOIN ccot.nodos_marca_om mnods ON mnods.NODO_TK = inc.`Ubicación` 
LEFT JOIN `o&m`.SR_Baseline bs1 ON bs1.ID COLLATE utf8mb4_unicode_ci = inc.`Articulo de configuración`
LEFT JOIN `o&m`.SR_Baseline bs2 ON bs2.ID COLLATE utf8mb4_unicode_ci = inc.`Ubicación`
WHERE inc.`Estado Incidente` <> "CANCELADO"
ORDER BY (TIMESTAMPDIFF(DAY, inc.`Fecha de creación`, NOW()) * 1440) +
        (TIMESTAMPDIFF(HOUR, inc.`Fecha de creación`, NOW()) * 60) +
        (TIME_TO_SEC(TIMEDIFF(NOW(), inc.`Fecha de creación`)) DIV 60) ASC;
"""


# 🔹 Configuración de la actualización automática
HORA_INICIO = "00:00"  # Hora de inicio en formato HH:MM (24h)
INTERVALO_MINUTOS = 5  # Cada cuántos minutos debe actualizarse

# Convertir la hora de inicio a un objeto datetime
hora_actual = datetime.now()
hora_inicio = datetime.strptime(HORA_INICIO, "%H:%M").replace(
    year=hora_actual.year, month=hora_actual.month, day=hora_actual.day
)

# Si la hora de inicio ya pasó hoy, calcular la próxima ocurrencia
if hora_actual < hora_inicio:
    proxima_actualizacion = hora_inicio
else:
    minutos_transcurridos = (hora_actual - hora_inicio).seconds // 60
    minutos_faltantes = INTERVALO_MINUTOS - (minutos_transcurridos % INTERVALO_MINUTOS)
    proxima_actualizacion = hora_actual + timedelta(minutes=minutos_faltantes)

# Guardar el tiempo de la última actualización en la sesión de Streamlit
if "last_update" not in st.session_state:
    st.session_state.last_update = time.time()

# Si es la hora de actualización, recargar la página
if datetime.now() >= proxima_actualizacion:
    st.session_state.last_update = time.time()
    st.rerun()  # Recargar la página


# 🔹 Función para cargar datos (se invalida cada 10 minutos)
@st.cache_data(ttl=INTERVALO_MINUTOS * 60)
def cargar_datos():
    try:
        engine = get_engine()
        df = pd.read_sql(qry, engine)
        df = du.postprocess_dataframe(df)
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        columnas_fallback = [
            "ORDEN","TIPO","SEGMENTO","DIAS","JEFE INTEGRAL","OWNER","CIUDAD","TIEMPO SLA","TIEMPO",
            "RESTANTE SLA","CUMP SLA","PRIORIDAD","TIPIFICACION","ESTADO","TECNICO",
            "ALIADO MAX","ALIADO WF","INICIO(H)","DISTRITO","RED","UBICACION","DESCRIPCION","REPRO",
            "FECHA_ACTUALIZACION_MAXIMO","FECHA_ACTUALIZACION_AGENDA","FECHA_INICIO_WF","FECHA_CREACION",
            "MIN","TIEMPO_RESTANTE_EN_MINUTOS","INICIADO","PENDIENTE","SUSPENDIDO","CANCELADO"
        ]
        return pd.DataFrame(columns=columnas_fallback)


df = cargar_datos()

# Lista corregida de columnas visibles (sin "DIA" si no existe)
columnas_visibles = [
    "ORDEN",
    "TIPO",
    "SEGMENTO",
    "DIAS",
    "JEFE INTEGRAL",
    "OWNER",
    "CIUDAD",
    "TIEMPO SLA",
    "TIEMPO",
    "RESTANTE SLA",
    "CUMP SLA",
    "PRIORIDAD",
    "TIPIFICACION",
    "ESTADO",
    "TECNICO",
    "ALIADO MAX",
    "ALIADO WF",
    "INICIO(H)",
    "DISTRITO",
    "RED",
    "UBICACION",
    "DESCRIPCION",
    "REPRO",
]

# Verificar si todas las columnas existen antes de usarlas
columnas_disponibles = [col for col in columnas_visibles if col in df.columns]

# Renombrar las columnas visibles
df_visible = df[columnas_visibles].copy()  # Crear una copia del DataFrame

# Ajustar el tamaño de la tabla dinámicamente
num_columnas = len(df.columns)
num_filas = len(df)
ancho = max(1200, num_columnas * 100)  # Ajustar mínimo a 1200px
altura = min(800, max(400, num_filas * 25))  # Ajusta entre 400 y 800 px


# Aplicar el formato condicional solo a la columna "CUMP SLA"
def resaltar_sla(val):
    if val == "VENCIDO":
        return "background-color: #cb4335; color: white; text-align: center;"
    elif val == "PRÓXIMO A VENCER":
        return "background-color: #e67e22; color: white; text-align: center;"
    elif val == "EN TIEMPO":
        return "background-color: #2ecc71; color: white; text-align: center;"
    elif val == "NO APLICA":
        return "background-color: #808b96; color: white; text-align: center;"
    return ""


# Aplicar el formato condicional solo a la columna "PRIORIDAD"
def resaltar_prioridad(val):
    if val == "P1":
        return "background-color: #cb4335; color: white; text-align: center;"
    elif val == "P2":
        return "background-color: #e67e22; color: white; text-align: center;"
    elif val == "P3":
        return "background-color: #f1c40f; color: white; text-align: center;"
    return ""


def resaltar_tipificacion(val):
    if val == "AFECTACION":
        return "background-color: #cb4335; color: white; text-align: center;"
    elif val == "DEGRADACION":
        return "background-color: #e67e22; color: white; text-align: center;"
    elif val == "RECLAMACION":
        return "background-color: #f1c40f; color: white; text-align: center;"
    elif val == "RUIDO":
        return "background-color: #8e44ad; color: white; text-align: center;"
    elif val == "NOTIFICACION":
        return "background-color: #2980b9; color: white; text-align: center;"
    elif val == "SIN TIPIFICACION":
        return "background-color: #808b96; color: white; text-align: center;"
    elif val == "QOE":
        return "background-color: #e84393; color: white; text-align: center;"  # Rosado vibrante
    elif val == "RECLAMACION RECURRENTE":
        return "background-color: #00cec9; color: white; text-align: center;"  # Celeste turquesa
    return ""


# Aplicar el formato condicional solo a la columna "AGENDAMIENTO"
def resaltar_agendamiento(val):
    if val == "SIN AGENDA":
        return "background-color: #cb4335; color: white; text-align: center;"
    elif val == "PENDIENTE":
        return "background-color: #e67e22; color: white; text-align: center;"
    elif val == "INICIADO":
        return "background-color: #a7d100; color: white; text-align: center;"
    elif val == "SUSPENDIDO":
        return "background-color: #8e44ad; color: white; text-align: center;"
    elif val == "NOTIFICACION":
        return "background-color: #2980b9; color: white; text-align: center;"
    elif val == "COMPLETADO":
        return "background-color: #808b96; color: white; text-align: center;"
    return ""


# Mostrar la última hora de actualización
# Obtener la fecha máxima de la columna FECHA_ACTUALIZACION_MAXIMO
if "FECHA_ACTUALIZACION_MAXIMO" in df.columns:
    fecha_maxima = df["FECHA_ACTUALIZACION_MAXIMO"].max()
    fecha_actualizacion_maximo = (
        fecha_maxima.strftime("%Y-%m-%d %H:%M:%S")
        if pd.notna(fecha_maxima)
        else "No disponible"
    )
else:
    fecha_actualizacion_maximo = "No disponible"

# Mostrar la última fecha de actualización basada en los datos del DataFrame
st.sidebar.write(f"📅 Actualización Maximo: {fecha_actualizacion_maximo}")

# Obtener la fecha máxima de la columna FECHA_ACTUALIZACION_AGENDA
if "FECHA_ACTUALIZACION_AGENDA" in df.columns:
    fecha_maxima = df["FECHA_ACTUALIZACION_AGENDA"].max()
    fecha_actualizacion_agenda = (
        fecha_maxima.strftime("%Y-%m-%d %H:%M:%S")
        if pd.notna(fecha_maxima)
        else "No disponible"
    )
else:
    fecha_actualizacion_agenda = "No disponible"

# Mostrar la última fecha de actualización basada en los datos del DataFrame
st.sidebar.write(f"📅 Actualización OFSC: {fecha_actualizacion_agenda}")

util.mostrar_menu()

# --- Agregar filtro en la barra lateral ---
st.sidebar.title("🔍 Filtros")

# Filtro por Red (selección múltiple)
valores_defecto = ["SDS", "HFC", "FTTH", "MOV","FTN", None]
valores_defecto = [r for r in valores_defecto if r in df["RED"].unique()]
red_seleccionada = st.sidebar.multiselect(
    "Red:", df["RED"].unique(), default=valores_defecto
)

# Filtro por Jefe
jefe_seleccionado = st.sidebar.selectbox(
    "Jefe Integral:", ["TODOS"] + list(df["JEFE INTEGRAL"].unique())
)

valor_defecto = "TODOS"
opciones_tipificacion = ["TODOS"] + list(df["TIPIFICACION"].unique())
index_defecto = (
    opciones_tipificacion.index(valor_defecto)
    if valor_defecto in opciones_tipificacion
    else 0
)
tipificacion_seleccionada = st.sidebar.selectbox(
    "Tipificación:", opciones_tipificacion, index=index_defecto
)

# Filtro por owner
owner_seleccionado = st.sidebar.selectbox(
    "Owner:", ["TODOS"] + list(df["OWNER"].unique())
)

# Filtro por aliado
aliado_seleccionado = st.sidebar.selectbox(
    "Aliado:", ["TODOS"] + list(df["ALIADO MAX"].unique())
)

# Filtro por distrito
distrito_seleccionado = st.sidebar.selectbox(
    "Distrito:", ["TODOS"] + list(df["DISTRITO"].unique())
)

# Filtro por Estado WF (selección múltiple)
estado_wf_seleccionado = st.sidebar.selectbox(
    "Estado OFSC:", ["TODOS"] + list(df["ESTADO"].unique())
)

# Filtro por Estado SLA (selección múltiple)
estado_sla_seleccionado = st.sidebar.selectbox(
    "Estado SLA:", ["TODOS"] + list(df["CUMP SLA"].unique())
)

# --- Aplicar los filtros ---
df_filtrado = df.copy()

# Aplicar filtro de Estado si hay selección
if red_seleccionada:
    df_filtrado = df_filtrado[df_filtrado["RED"].isin(red_seleccionada)]


aliado_wf_seleccionado = st.sidebar.selectbox(
    "Aliado OFSC:", ["TODOS"] + list(df["ALIADO WF"].unique())
)


if jefe_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["JEFE INTEGRAL"] == jefe_seleccionado]

# Aplicar filtro solo si no es "TODOS"
if tipificacion_seleccionada != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["TIPIFICACION"] == tipificacion_seleccionada]

if owner_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["OWNER"] == owner_seleccionado]

if aliado_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["ALIADO MAX"] == aliado_seleccionado]

# Aplicar filtro de Prioridad si no es "Todos"
if distrito_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["DISTRITO"] == distrito_seleccionado]

# Aplicar filtro de Estado si hay selección
if estado_wf_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["ESTADO"] == estado_wf_seleccionado]

# Aplicar filtro de Estado si hay selección
if estado_sla_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["CUMP SLA"] == estado_sla_seleccionado]

# --- Crear df_visible sin "JEFE_INTEGRAL" para mostrar ---
df_visible = df_filtrado[columnas_visibles].copy()

# Reemplazar valores None o NaN con una cadena vacía
df_visible = df_visible.fillna("")


if aliado_wf_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["ALIADO WF"] == aliado_wf_seleccionado]

# Aplicar estilos condicionales
df_visible_styled = df_visible.style.map(resaltar_sla, subset=["CUMP SLA"])
df_visible_styled = df_visible_styled.map(resaltar_prioridad, subset=["PRIORIDAD"])
df_visible_styled = df_visible_styled.map(
    resaltar_tipificacion, subset=["TIPIFICACION"]
)
df_visible_styled = df_visible_styled.format({"DIAS": "{:.1f}"})

df_visible_styled = df_visible_styled.map(resaltar_agendamiento, subset=["ESTADO"])


# 🔹 **Mostrar la tabla filtrada sin "ESTADO_MAXIMO"**
st.markdown(
    """
<style>
/* Asegurar que el Header esté por encima del Sidebar */
.stAppHeader {
    position: relative !important;
    z-index: 100 !important;
    background-color: #C00000 !important;
}

/* Ajustar el Sidebar para que no se superponga al Header */
.stSidebar {
    z-index: 10 !important;
}

/* Asegurar que el header tenga una posición relativa para insertar el título */
.stAppHeader {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 60px;
}

/* Insertar texto en el header */
.stAppHeader::after {
    content: "Resumen Backlog O&M Fijo CCOT R3";
    font-size: 34px;
    font-weight: bold;
    color: white;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
}

/* Ajustar el tamaño del DataFrame */
[data-testid="stDataFrameResizable"] {
    max-width: auto !important;
    max-height: 600px !important;
    overflow: auto !important;
}
</style>
""",
    unsafe_allow_html=True,
)
# 🔹 Calcular métricas con los datos filtrados
total_ordenes = df_filtrado.shape[0]
ordenes_vencidas = df_filtrado[df_filtrado["CUMP SLA"] == "VENCIDO"].shape[0]
promedio_tiempo_transcurrido = (
    round(df_filtrado["MIN"].mean(), 2) if not df_filtrado.empty else 0
)
promedio_tiempo_restante = (
    round(df_filtrado["TIEMPO_RESTANTE_EN_MINUTOS"].mean(), 2)
    if not df_filtrado.empty
    else 0
)

# 🔹 Calcular valores equivalentes a la medida DAX
cump_valor = df_filtrado[df_filtrado["CUMP SLA"] != "VENCIDO"]["ORDEN"].count()
total_valor = df_filtrado["ORDEN"].count()
trf = round(cump_valor / total_valor, 3) if total_valor > 0 else 0

# 🔹 Calcular 'TIEMPO_INICIO' (diferencia en horas)
df_filtrado["TIEMPO_INICIO"] = (
    df_filtrado["FECHA_INICIO_WF"] - df_filtrado["FECHA_CREACION"]
).dt.total_seconds()
df_filtrado["TIEMPO_INICIO"] = df_filtrado["TIEMPO_INICIO"].div(3600).fillna(0).round(2)

# 🔹 Filtrar solo estados específicos
df_estado_filtrado = df_filtrado[
    df_filtrado["ESTADO"].isin(["COMPLETADO", "INICIADO", "SUSPENDIDO"])
]

# 🔹 Calcular SUM(TIEMPO_INICIO) solo para los estados seleccionados
suma_tiempo_inicio = df_estado_filtrado["TIEMPO_INICIO"].sum()

# 🔹 Calcular SUM(CANTIDAD) solo para los estados seleccionados
suma_cantidad = df_estado_filtrado["ORDEN"].count()

# 🔹 Calcular el promedio y manejar la división por cero
promedio_tiempo_inicio = (
    round(suma_tiempo_inicio / suma_cantidad, 1) if suma_cantidad > 0 else 0
)

# 🔹 Formatear el resultado con "Horas"
promedio_tiempo_inicio_formato = f"{promedio_tiempo_inicio} Horas"

st.markdown(
    """
    <style>
    /* Reducir tamaño del valor principal en st.metric */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
    }

    /* Reducir tamaño del label (titulo) */
    div[data-testid="stMetricLabel"] {
        font-size: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

tipos = df_visible["TIPIFICACION"].unique()
tipos = sorted(tipos)  # Orden alfabético

# Calcular el total general una vez
total_general = df_visible.shape[0]

# Añadir una columna extra para el total
cols = st.columns(len(tipos) + 1)

# Mostrar métricas por tipo con porcentaje
for i, tipo in enumerate(tipos):
    cantidad = df_visible[df_visible["TIPIFICACION"] == tipo].shape[0]
    porcentaje = (cantidad / total_general) * 100 if total_general > 0 else 0
    valor_formateado = f"{cantidad} ({porcentaje:.1f}%)"
    with cols[i]:
        st.metric(label=tipo, value=valor_formateado)

# Mostrar total general al final
with cols[-1]:
    st.metric(label="🧮 TOTAL", value=total_general)


# ==========================
# 📊 VISTA RESUMEN ALIADO
# ==========================

# === 🌡️ Mapa de calor por fila basado en % TOTAL ===

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# === 1. Crear tabla de conteos ===
resumen_aliado = (
    df_visible.groupby(["ALIADO MAX", "TIPIFICACION"])
    .size()
    .unstack(fill_value=0)
    .reset_index()
)
resumen_aliado["TOTAL"] = resumen_aliado.drop(columns=["ALIADO MAX"]).sum(axis=1)
resumen_aliado = resumen_aliado.sort_values(by="TOTAL", ascending=False).reset_index(
    drop=True
)
totales_col = resumen_aliado.drop(columns=["ALIADO MAX", "TOTAL"]).sum()

# === 2. Calcular porcentajes reales ===
porcentajes = resumen_aliado.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    porcentajes[col] = (resumen_aliado[col] / totales_col[col] * 100).round(1)
porcentajes["% TOTAL"] = (
    resumen_aliado["TOTAL"] / resumen_aliado["TOTAL"].sum() * 100
).round(1)
porcentajes = porcentajes.rename(columns={"ALIADO MAX": "ALIADO"})

# === 3. Crear tabla combinada valor + % ===
tabla_combinada = resumen_aliado.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    tabla_combinada[col] = (
        resumen_aliado[col].astype(str) + " (" + porcentajes[col].astype(str) + "%)"
    )
tabla_combinada["TOTAL"] = (
    resumen_aliado["TOTAL"].astype(str)
    + " ("
    + porcentajes["% TOTAL"].astype(str)
    + "%)"
)
tabla_combinada = tabla_combinada.rename(columns={"ALIADO MAX": "ALIADO"})


# === 4. Función de estilo semáforo INVERTIDA por columna ===
def semaforo_columna_invertido(val):
    try:
        pct = float(val.split("(")[1].replace("%)", ""))
    except:
        pct = 0
    if pct >= 66:
        return "background-color: #e74c3c; color: white;"  # rojo fuerte (alto)
    elif pct >= 33:
        return "background-color: #f39c12; color: black;"  # naranja (medio)
    else:
        return "background-color: #2ecc71; color: black;"  # verde (bajo)


# === 5. Aplicar estilo por columna de tipificación ===
columnas_estilo = [
    col for col in tabla_combinada.columns if col not in ["ALIADO", "TOTAL"]
]
styled = tabla_combinada.style

for col in columnas_estilo:
    styled = styled.applymap(semaforo_columna_invertido, subset=[col])

# Puedes también aplicar estilo a la columna "TOTAL" si quieres
styled = styled.applymap(semaforo_columna_invertido, subset=["TOTAL"])

# === 6. Mostrar en Streamlit ===
st.markdown("### 🚦 Resumen Aliado")
st.dataframe(styled, use_container_width=True, hide_index=True)

# ==========================
# 📊 VISTA RESUMEN JEFE
# ==========================

# === 🌡️ Mapa de calor por fila basado en % TOTAL ===

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# === 1. Crear tabla de conteos ===
resumen_jefe = (
    df_visible.groupby(["JEFE INTEGRAL", "TIPIFICACION"])
    .size()
    .unstack(fill_value=0)
    .reset_index()
)
resumen_jefe["TOTAL"] = resumen_jefe.drop(columns=["JEFE INTEGRAL"]).sum(axis=1)
resumen_jefe = resumen_jefe.sort_values(by="TOTAL", ascending=False).reset_index(
    drop=True
)
totales_col = resumen_jefe.drop(columns=["JEFE INTEGRAL", "TOTAL"]).sum()

# === 2. Calcular porcentajes reales ===
porcentajes = resumen_jefe.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    porcentajes[col] = (resumen_jefe[col] / totales_col[col] * 100).round(1)
porcentajes["% TOTAL"] = (
    resumen_jefe["TOTAL"] / resumen_jefe["TOTAL"].sum() * 100
).round(1)
porcentajes = porcentajes.rename(columns={"JEFE INTEGRAL": "JEFE INTEGRAL"})

# === 3. Crear tabla combinada valor + % ===
tabla_combinada = resumen_jefe.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    tabla_combinada[col] = (
        resumen_jefe[col].astype(str) + " (" + porcentajes[col].astype(str) + "%)"
    )
tabla_combinada["TOTAL"] = (
    resumen_jefe["TOTAL"].astype(str) + " (" + porcentajes["% TOTAL"].astype(str) + "%)"
)
tabla_combinada = tabla_combinada.rename(columns={"JEFE INTEGRAL": "JEFE INTEGRAL"})


# === 4. Función de estilo semáforo INVERTIDA por columna ===
def semaforo_columna_invertido(val):
    try:
        pct = float(val.split("(")[1].replace("%)", ""))
    except:
        pct = 0
    if pct >= 40:
        return "background-color: #e74c3c; color: white;"  # rojo fuerte (alto)
    elif pct >= 10:
        return "background-color: #f39c12; color: black;"  # naranja (medio)
    else:
        return "background-color: #2ecc71; color: black;"  # verde (bajo)


# === 5. Aplicar estilo por columna de tipificación ===
columnas_estilo = [
    col for col in tabla_combinada.columns if col not in ["JEFE INTEGRAL", "TOTAL"]
]
styled = tabla_combinada.style

for col in columnas_estilo:
    styled = styled.applymap(semaforo_columna_invertido, subset=[col])

# Puedes también aplicar estilo a la columna "TOTAL" si quieres
styled = styled.applymap(semaforo_columna_invertido, subset=["TOTAL"])

# === 6. Mostrar en Streamlit ===
st.markdown("### 🚦 Resumen Jefe Integral")
st.dataframe(styled, use_container_width=True, hide_index=True)

# ==========================
# 📊 VISTA RESUMEN DISTRITO
# ==========================

# === 🌡️ Mapa de calor por fila basado en % TOTAL ===

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# === 1. Crear tabla de conteos ===
resumen_distrito = (
    df_visible.groupby(["DISTRITO", "TIPIFICACION"])
    .size()
    .unstack(fill_value=0)
    .reset_index()
)
resumen_distrito["TOTAL"] = resumen_distrito.drop(columns=["DISTRITO"]).sum(axis=1)
resumen_distrito = resumen_distrito.sort_values(
    by="TOTAL", ascending=False
).reset_index(drop=True)
totales_col = resumen_distrito.drop(columns=["DISTRITO", "TOTAL"]).sum()

# === 2. Calcular porcentajes reales ===
porcentajes = resumen_distrito.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    porcentajes[col] = (resumen_distrito[col] / totales_col[col] * 100).round(1)
porcentajes["% TOTAL"] = (
    resumen_distrito["TOTAL"] / resumen_distrito["TOTAL"].sum() * 100
).round(1)
porcentajes = porcentajes.rename(columns={"DISTRITO": "DISTRITO"})

# === 3. Crear tabla combinada valor + % ===
tabla_combinada = resumen_distrito.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    tabla_combinada[col] = (
        resumen_distrito[col].astype(str) + " (" + porcentajes[col].astype(str) + "%)"
    )
tabla_combinada["TOTAL"] = (
    resumen_distrito["TOTAL"].astype(str)
    + " ("
    + porcentajes["% TOTAL"].astype(str)
    + "%)"
)
tabla_combinada = tabla_combinada.rename(columns={"DISTRITO": "DISTRITO"})


# === 4. Función de estilo semáforo INVERTIDA por columna ===
def semaforo_columna_invertido(val):
    try:
        pct = float(val.split("(")[1].replace("%)", ""))
    except:
        pct = 0
    if pct >= 40:
        return "background-color: #e74c3c; color: white;"  # rojo fuerte (alto)
    elif pct >= 10:
        return "background-color: #f39c12; color: black;"  # naranja (medio)
    elif pct >= 5:
        return "background-color: #f1c40f; color: black;"  # naranja (medio)
    else:
        return "background-color: #2ecc71; color: black;"  # verde (bajo)


# === 5. Aplicar estilo por columna de tipificación ===
columnas_estilo = [
    col for col in tabla_combinada.columns if col not in ["DISTRITO", "TOTAL"]
]
styled = tabla_combinada.style

for col in columnas_estilo:
    styled = styled.applymap(semaforo_columna_invertido, subset=[col])

# Puedes también aplicar estilo a la columna "TOTAL" si quieres
styled = styled.applymap(semaforo_columna_invertido, subset=["TOTAL"])

# === 6. Mostrar en Streamlit ===
st.markdown("### 🚦 Resumen Distrito")
st.dataframe(styled, use_container_width=True, hide_index=True)

# ==========================
# 📊 VISTA RESUMEN OWNER
# ==========================

# === 🌡️ Mapa de calor por fila basado en % TOTAL ===

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# === 1. Crear tabla de conteos ===
resumen_owner = (
    df_visible.groupby(["OWNER", "TIPIFICACION"])
    .size()
    .unstack(fill_value=0)
    .reset_index()
)
resumen_owner["TOTAL"] = resumen_owner.drop(columns=["OWNER"]).sum(axis=1)
resumen_owner = resumen_owner.sort_values(by="TOTAL", ascending=False).reset_index(
    drop=True
)
totales_col = resumen_owner.drop(columns=["OWNER", "TOTAL"]).sum()

# === 2. Calcular porcentajes reales ===
porcentajes = resumen_owner.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    porcentajes[col] = (resumen_owner[col] / totales_col[col] * 100).round(1)
porcentajes["% TOTAL"] = (
    resumen_owner["TOTAL"] / resumen_owner["TOTAL"].sum() * 100
).round(1)
porcentajes = porcentajes.rename(columns={"OWNER": "OWNER"})

# === 3. Crear tabla combinada valor + % ===
tabla_combinada = resumen_owner.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    tabla_combinada[col] = (
        resumen_owner[col].astype(str) + " (" + porcentajes[col].astype(str) + "%)"
    )
tabla_combinada["TOTAL"] = (
    resumen_owner["TOTAL"].astype(str)
    + " ("
    + porcentajes["% TOTAL"].astype(str)
    + "%)"
)
tabla_combinada = tabla_combinada.rename(columns={"OWNER": "OWNER"})


# === 4. Función de estilo semáforo INVERTIDA por columna ===
def semaforo_columna_invertido(val):
    try:
        pct = float(val.split("(")[1].replace("%)", ""))
    except:
        pct = 0
    if pct >= 40:
        return "background-color: #e74c3c; color: white;"  # rojo fuerte (alto)
    elif pct >= 10:
        return "background-color: #f39c12; color: black;"  # naranja (medio)
    elif pct >= 5:
        return "background-color: #f1c40f; color: black;"  # naranja (medio)
    else:
        return "background-color: #2ecc71; color: black;"  # verde (bajo)


# === 5. Aplicar estilo por columna de tipificación ===
columnas_estilo = [
    col for col in tabla_combinada.columns if col not in ["OWNER", "TOTAL"]
]
styled = tabla_combinada.style

for col in columnas_estilo:
    styled = styled.applymap(semaforo_columna_invertido, subset=[col])

# Puedes también aplicar estilo a la columna "TOTAL" si quieres
styled = styled.applymap(semaforo_columna_invertido, subset=["TOTAL"])

# === 6. Mostrar en Streamlit ===
st.markdown("### 🚦 Resumen Owner's")
st.dataframe(styled, use_container_width=True, hide_index=True)


# ==========================
# 📊 VISTA RESUMEN AGENDA
# ==========================

# === 🌡️ Mapa de calor por fila basado en % TOTAL ===

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# === 1. Crear tabla de conteos ===
resumen_agenda = (
    df_visible.groupby(["ESTADO", "TIPIFICACION"])
    .size()
    .unstack(fill_value=0)
    .reset_index()
)
resumen_agenda["TOTAL"] = resumen_agenda.drop(columns=["ESTADO"]).sum(axis=1)
resumen_agenda = resumen_agenda.sort_values(by="TOTAL", ascending=False).reset_index(
    drop=True
)
totales_col = resumen_agenda.drop(columns=["ESTADO", "TOTAL"]).sum()

# === 2. Calcular porcentajes reales ===
porcentajes = resumen_agenda.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    porcentajes[col] = (resumen_agenda[col] / totales_col[col] * 100).round(1)
porcentajes["% TOTAL"] = (
    resumen_agenda["TOTAL"] / resumen_agenda["TOTAL"].sum() * 100
).round(1)
porcentajes = porcentajes.rename(columns={"ESTADO": "ESTADO"})

# === 3. Crear tabla combinada valor + % ===
tabla_combinada = resumen_agenda.drop(columns=["TOTAL"]).copy()
for col in totales_col.index:
    tabla_combinada[col] = (
        resumen_agenda[col].astype(str) + " (" + porcentajes[col].astype(str) + "%)"
    )
tabla_combinada["TOTAL"] = (
    resumen_agenda["TOTAL"].astype(str)
    + " ("
    + porcentajes["% TOTAL"].astype(str)
    + "%)"
)
tabla_combinada = tabla_combinada.rename(columns={"ESTADO": "ESTADO"})


# === 4. Función de estilo semáforo INVERTIDA por columna ===
def semaforo_columna_invertido(val):
    try:
        pct = float(val.split("(")[1].replace("%)", ""))
    except:
        pct = 0
    if pct <= 60:
        return "background-color: #e74c3c; color: white;"  # rojo fuerte (alto)
    elif pct <= 20:
        return "background-color: #f39c12; color: black;"  # naranja (medio)
    else:
        return "background-color: #2ecc71; color: black;"  # verde (bajo)


# === 5. Aplicar estilo por columna de tipificación ===
columnas_estilo = [
    col for col in tabla_combinada.columns if col not in ["ESTADO", "TOTAL"]
]
styled = tabla_combinada.style

for col in columnas_estilo:
    styled = styled.applymap(semaforo_columna_invertido, subset=[col])

# Puedes también aplicar estilo a la columna "TOTAL" si quieres
styled = styled.applymap(semaforo_columna_invertido, subset=["TOTAL"])

# === 6. Mostrar en Streamlit ===
st.markdown("### 🚦 Resumen Estado Agenda")
st.dataframe(tabla_combinada, use_container_width=True, hide_index=True)
