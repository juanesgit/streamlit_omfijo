import streamlit as st
import utilidades as util
import pandas as pd
from sqlalchemy import create_engine
import data_utils as du
import os
import time
from datetime import datetime, timedelta

st.set_page_config(
    layout="wide", initial_sidebar_state="collapsed"
)  # Habilitar pantalla ancha

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
    COALESCE(COALESCE(bs1.`SITE Owner`, bs2.`SITE Owner`), '') AS `OWNER`,
    IF(sm.CONVENIENTE="SI","SI",NULL) AS CONV
FROM ccot.incidentes inc
LEFT JOIN tiempo_limite_cte t ON inc.`Orden de trabajo` = t.`Orden de trabajo`
LEFT JOIN ccot.wf_om_back wf ON inc.`Orden de trabajo` = wf.`Orden de trabajo`
LEFT JOIN ccot.familias fa ON inc.`Ruta de clasificación` = fa.`clasificación`
LEFT JOIN ccot.nodos_marca_om mnod ON mnod.NODO_TK = inc.`Articulo de configuración`
LEFT JOIN ccot.nodos_marca_om mnods ON mnods.NODO_TK = inc.`Ubicación` 
LEFT JOIN `o&m`.SR_Baseline bs1 ON bs1.ID COLLATE utf8mb4_unicode_ci = inc.`Articulo de configuración`
LEFT JOIN `o&m`.SR_Baseline bs2 ON bs2.ID COLLATE utf8mb4_unicode_ci = inc.`Ubicación`
LEFT JOIN ccot.simple_om_corp sm ON sm.OT = inc.`Orden de trabajo`
WHERE inc.`Estado Incidente` <> "CANCELADO"
ORDER BY (TIMESTAMPDIFF(DAY, inc.`Fecha de creación`, NOW()) * 1440) +
        (TIMESTAMPDIFF(HOUR, inc.`Fecha de creación`, NOW()) * 60) +
        (TIME_TO_SEC(TIMEDIFF(NOW(), inc.`Fecha de creación`)) DIV 60) ASC;
"""


# 🔹 Configuración de la actualización automática
HORA_INICIO = "00:00"  # Hora de inicio en formato HH:MM (24h)
INTERVALO_MINUTOS = 2  # Cada cuántos minutos debe actualizarse

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
            "ORDEN","TIPO","SEGMENTO","DIAS","JEFE INTEGRAL","CIUDAD","TIEMPO SLA","TIEMPO",
            "RESTANTE SLA","CONV","CUMP SLA","PRIORIDAD","TIPIFICACION","ESTADO","TECNICO","OWNER",
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
    "CIUDAD",
    "TIEMPO SLA",
    "TIEMPO",
    "RESTANTE SLA",
    "CONV",
    "CUMP SLA",
    "PRIORIDAD",
    "TIPIFICACION",
    "ESTADO",
    "TECNICO",
    "OWNER",
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
def resaltar_sla_fila(row):
    sla = row.get("CUMP SLA", "")
    conveniencia = row.get("CONV", "")
    if conveniencia == "🟢":
        return "background-color: #f1c40f; color: white; text-align: center;"
    elif sla == "VENCIDO":
        return "background-color: #cb4335; color: white; text-align: center;"
    elif sla == "PRÓXIMO A VENCER":
        return "background-color: #e67e22; color: white; text-align: center;"
    elif sla == "EN TIEMPO":
        return "background-color: #2ecc71; color: white; text-align: center;"
    elif sla == "NO APLICA":
        return "background-color: #808b96; color: white; text-align: center;"
    return ""


# Aplicar el formato condicional solo a la columna "PRIORIDAD"
def resaltar_prioridad_fila(row):
    prioridad = row.get("PRIORIDAD", "")
    conveniencia = row.get("CONV", "")
    if conveniencia == "🟢":
        return "background-color: #f1c40f; color: white; text-align: center;"
    elif prioridad == "P1":
        return "background-color: #cb4335; color: white; text-align: center;"
    elif prioridad == "P2":
        return "background-color: #e67e22; color: white; text-align: center;"
    elif prioridad == "P3":
        return "background-color: #f1c40f; color: white; text-align: center;"
    return ""


def resaltar_tipificacion_fila(row):
    tip = row["TIPIFICACION"]
    prioridad = row.get("PRIORIDAD", "")
    conveniencia = row.get("CONV", "")

    if tip == "AFECTACION":
        if conveniencia == "🟢":
            return "background-color: #f1c40f; color: white; text-align: center;"
        elif prioridad == "P1":
            return "background-color: #cb4335; color: white; text-align: center;"
        elif prioridad == "P2":
            return "background-color: #e67e22; color: white; text-align: center;"
        elif prioridad == "P3":
            return "background-color: #f1c40f; color: white; text-align: center;"
        else:
            return "background-color: #f1c40f; color: white; text-align: center;"
    elif tip == "DEGRADACION":
        return "background-color: #e67e22; color: white; text-align: center;"
    elif tip == "RECLAMACION":
        return "background-color: #f1c40f; color: white; text-align: center;"
    elif tip == "RUIDO":
        return "background-color: #8e44ad; color: white; text-align: center;"
    elif tip == "NOTIFICACION":
        return "background-color: #2980b9; color: white; text-align: center;"
    elif tip == "SIN TIPIFICACION":
        return "background-color: #808b96; color: white; text-align: center;"
    elif tip == "QOE":
        return "background-color: #e84393; color: white; text-align: center;"
    elif tip == "RECLAMACION RECURRENTE":
        return "background-color: #00cec9; color: white; text-align: center;"
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

valor_defecto = "AFECTACION"
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

# Filtro por distrito
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

if aliado_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["ALIADO MAX"] == aliado_seleccionado]

if owner_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["OWNER"] == owner_seleccionado]

# Aplicar filtro de Prioridad si no es "Todos"
if distrito_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["DISTRITO"] == distrito_seleccionado]

# Aplicar filtro de Estado si hay selección
if estado_wf_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["ESTADO"] == estado_wf_seleccionado]

if aliado_wf_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["ALIADO WF"] == aliado_wf_seleccionado]

# Aplicar filtro de Estado si hay selección
if estado_sla_seleccionado != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["CUMP SLA"] == estado_sla_seleccionado]

# --- Crear df_visible sin "JEFE_INTEGRAL" para mostrar ---
df_visible = df_filtrado[columnas_visibles].copy()

# Reemplazar valores None o NaN con una cadena vacía
df_visible = df_visible.fillna("")

# Aplicar estilos condicionales
df_visible_styled = df_visible.style

df_visible_styled = df_visible_styled.apply(
    lambda row: [
        resaltar_sla_fila(row) if col == "CUMP SLA" else ""
        for col in df_visible.columns
    ],
    axis=1,
)
df_visible_styled = df_visible_styled.apply(
    lambda row: [
        resaltar_prioridad_fila(row) if col == "PRIORIDAD" else ""
        for col in df_visible.columns
    ],
    axis=1,
)
df_visible_styled = df_visible_styled.apply(
    lambda row: [
        resaltar_tipificacion_fila(row) if col == "TIPIFICACION" else ""
        for col in df_visible.columns
    ],
    axis=1,
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
    content: "Seguimiento Backlog O&M Fijo CCOT R3";
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

# 🔹 Calcular 'TIEMPO_INICIO' (diferencia en horas) de forma segura
if "FECHA_INICIO_WF" in df_filtrado.columns and "FECHA_CREACION" in df_filtrado.columns:
    dt_ini = pd.to_datetime(df_filtrado["FECHA_INICIO_WF"], errors="coerce")
    dt_cre = pd.to_datetime(df_filtrado["FECHA_CREACION"], errors="coerce")
    segundos = (dt_ini - dt_cre).dt.total_seconds()
else:
    segundos = pd.Series([], dtype="float64")
df_filtrado["TIEMPO_INICIO"] = (
    pd.to_numeric(segundos, errors="coerce").div(3600).fillna(0).round(2)
)

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

# 🔹 Calcular la columna 'GESTION_BACK'
df_filtrado["GESTION_BACK"] = df_filtrado.apply(
    lambda row: (
        1
        if (row["TIPIFICACION"] == "AFECTACION" and row["DIAS"] <= 2)
        or (row["TIPIFICACION"] != "AFECTACION" and row["DIAS"] <= 30)
        else 0
    ),
    axis=1,
)

# 🔹 Sumar los valores de 'GESTION_BACK'
gestion_back_total = df_filtrado["GESTION_BACK"].sum()

# 🔹 Sumar las órdenes de trabajo (equivalente a SUM(CANTIDAD))
total_cantidad = df_filtrado["ORDEN"].count()

# 🔹 Calcular GESTION_BACK_% evitando división por cero
gestion_back_pct = (
    round((gestion_back_total / total_cantidad) * 100, 2) if total_cantidad > 0 else 0
)

# 🔹 Calcular la columna 'PRIMER_AGENDA' usando lógica condicional
df_filtrado["PRIMER_AGENDA"] = df_filtrado.apply(
    lambda row: (
        1
        if (
            (
                row["ESTADO"] == "COMPLETADO"
                and (
                    (row["INICIADO"] == 0 or row["PENDIENTE"] == 0)
                    and (row["SUSPENDIDO"] + row["CANCELADO"] == 0)
                )
            )
            or (
                row["ESTADO"] != "SIN AGENDA"
                and (
                    (row["INICIADO"] == 1 or row["PENDIENTE"] == 1)
                    and (row["SUSPENDIDO"] + row["CANCELADO"] == 0)
                )
            )
        )
        else 0
    ),
    axis=1,
)

# 🔹 Sumar los valores de 'PRIMER_AGENDA'
primer_agenda_total = df_filtrado["PRIMER_AGENDA"].sum()

# 🔹 Contar el total de datos en el DataFrame
cantidad_total = len(df_filtrado)  # Equivalente a SUM(CANTIDAD)

# 🔹 Calcular %_PRIMER_AGENDA evitando división por cero
primer_agenda_pct = (
    round((primer_agenda_total / cantidad_total) * 100, 1) if cantidad_total > 0 else 0
)

# 🔹 Calcular porcentaje de incidentes con agenda
total_con_agenda = df_filtrado[df_filtrado["ESTADO"] != "SIN AGENDA"]["ORDEN"].count()
total_incidentes = df_filtrado["ORDEN"].count()

# Evitar división por cero
agenda_pct = (
    round((total_con_agenda / total_incidentes) * 100, 1) if total_incidentes > 0 else 0
)

col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric(label="📅 Agenda", value=f"{agenda_pct} %")

with col2:
    st.metric(label="📊 Total Back", value=f"{len(df_visible)} Inc.")

with col3:
    st.metric(label="📊 En Tiempo", value=f"{round(trf * 100,3)} %")

with col4:
    st.metric(
        label="⏳ Promedio Tiempo de Inicio", value=promedio_tiempo_inicio_formato
    )
with col5:
    st.metric(label="📊 Gestion Back", value=f"{round(gestion_back_pct,1)} %")

with col6:
    # 🔹 Mostrar la métrica en Streamlit
    st.metric(label="📊 Primer Agenda", value=f"{primer_agenda_pct} %")

df_visible["CONV"] = df_visible["CONV"].apply(lambda x: "🟢" if x == "SI" else "🔴")

st.write(f"### Backlog O&M Fijo ({len(df_visible)}  incidentes)")
st.dataframe(
    df_visible_styled,
    hide_index=True,
    height=altura,
    width=ancho,
    use_container_width=True,
)
