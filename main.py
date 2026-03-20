import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL OMNI V83", layout="wide", page_icon="🚜")

DB_PATH = "corral_maestro_pro.db"

# --- 1. DICCIONARIOS MAESTROS (RAZAS Y CURVAS) ---
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul", "Negra", "Extremeña", "Pita Pinta", "Ayam Cemani"],
    "Pollo (Carne)": ["Blanco Engorde (Broiler)", "Campero / Rural", "Crecimiento Lento", "Capón"],
    "Codorniz": ["Japónica (Huevo)", "Coreana (Carne)", "Vuelo"],
    "Pavo": ["Blanco Gigante", "Bronceado"],
    "Pato": ["Mulard", "Pekín", "Corredor Indio"]
}

CURVA_PUESTA = {"sem": [0,18,20,25,30,40,50,60,70,80,90], "p": [0,0,0.15,0.85,0.94,0.92,0.88,0.80,0.70,0.60,0.40]}
CURVA_CRECIMIENTO = {"sem": [0,1,2,3,4,5,6,7,8,12,16], "kg": [0.05, 0.18, 0.45, 0.9, 1.5, 2.2, 2.9, 3.5, 4.0, 5.5, 7.0]}

# --- 2. MOTOR DE BASE DE DATOS ---
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial_semanas INTEGER, precio_ud REAL, estado TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, unidades INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- 3. LÓGICA DE CLIMA Y PREDICCIÓN ---
def get_clima(key):
    if not key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

def predecir_rendimiento(lote, bajas, dias_plus):
    try:
        f_alta = datetime.strptime(lote["fecha"], "%d/%m/%Y" if "/" in lote["fecha"] else "%Y-%m-%d")
        edad_total_sem = lote["edad_inicial_semanas"] + ((datetime.now() - f_alta).days + dias_plus) / 7
        muertes = bajas[bajas['lote_id']==lote['id']]['cantidad'].sum() if not bajas.empty else 0
        vivos = max(0, lote['cantidad'] - muertes)
        
        if "Gallina" in lote["especie"] or "Codorniz" in lote["especie"]:
            val = np.interp(edad_total_sem, CURVA_PUESTA["sem"], CURVA_PUESTA["p"]) * vivos
            return ("H", val)
        else:
            val = np.interp(edad_total_sem, CURVA_CRECIMIENTO["sem"], CURVA_CRECIMIENTO["kg"]) * vivos
            return ("C", val)
    except: return (None, 0)

# =========================================================
# INTERFAZ DE USUARIO
# =========================================================
inicializar_db()
if 'gemini_key' not in st.session_state: st.session_state['gemini_key'] = ""
if 'aemet_key' not in st.session_state: st.session_state['aemet_key'] = ""

lotes, gastos, produccion, bajas, ventas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("bajas"), cargar("ventas")
temp = get_clima(st.session_state['aemet_key'])

st.sidebar.title("🚜 CORRAL OMNI V83")
menu = st.sidebar.radio("MENÚ", ["📊 Dashboard", "🔮 Predicción & Crecimiento", "🐣 Alta de Lotes", "🥚 Producción", "💰 Ventas/Gastos", "🩺 Salud IA", "📜 Histórico"])

with st.sidebar.expander("🔑 API Keys"):
    st.session_state['gemini_key'] = st.text_input("Gemini Key", type="password", value=st.session_state['gemini_key'])
    st.session_state['aemet_key'] = st.text_input("AEMET Key", type="password", value=st.session_state['aemet_key'])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Control de Mando")
    c1,c2,c3,c4 = st.columns(4)
    balance = ventas['cantidad'].sum() - gastos['cantidad'].sum()
    c1.metric("🌡️ Cartagena", f"{temp:.1f}°C")
    c2.metric("💰 Balance Neto", f"{balance:.2f} €")
    c3.metric("🐔 Aves Activas", int(lotes['cantidad'].sum() - bajas['cantidad'].sum() if not lotes.empty else 0))
    c4.metric("🥚 Producción Hoy", int(produccion.tail(1)['huevos'].sum() if not produccion.empty else 0))

    if not produccion.empty:
        st.plotly_chart(px.line(produccion, x='fecha', y='huevos', title="Tendencia Real de Puesta"), use_container_width=True)

# --- PREDICCIÓN & CRECIMIENTO ---
elif menu == "🔮 Predicción & Crecimiento":
    st.title("🔮 Análisis Predictivo Cruzado")
    dias = 30
    fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(dias)]
    h_data, c_data = [], []

    for i in range(dias):
        h_sum, c_sum = 0, 0
        for _, l in lotes.iterrows():
            tipo, val = predecir_rendimiento(l, bajas, i)
            if tipo == "H": h_sum += val
            if tipo == "C": c_sum += val
        h_data.append(h_sum); c_data.append(c_sum)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🥚 Puesta Estimada (Huevos)")
        st.plotly_chart(px.line(x=fechas, y=h_data, color_discrete_sequence=['orange']), use_container_width=True)
    with col2:
        st.subheader("⚖️ Crecimiento Carne (Kg)")
        st.plotly_chart(px.area(x=fechas, y=c_data, color_discrete_sequence=['red']), use_container_width=True)

# --- ALTA DE LOTES ---
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Compra de Animales por Clase")
    with st.form("alta"):
        e = st.selectbox("Especie", list(ESPECIES_FULL.keys()))
        rz = st.selectbox("Raza/Clase", ESPECIES_FULL[e])
        cant = st.number_input("Nº Aves", 1); ed = st.number_input("Edad al comprar (Semanas)", 0)
        pr = st.number_input("Precio/ud €", 0.0)
        if st.form_submit_button("Registrar Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), e, rz, int(cant), int(ed), pr, "Activo")).connection.commit()
            st.rerun()

# --- SALUD IA ---
elif menu == "🩺 Salud IA":
    st.title("🩺 Análisis Veterinario IA")
    foto = st.file_uploader("Subir foto", type=['jpg','png','jpeg'])
    if foto and st.session_state['gemini_key']:
        if st.button("Analizar Salud"):
            genai.configure(api_key=st.session_state['gemini_key'])
            model = genai.GenerativeModel("gemini-1.5-flash")
            res = model.generate_content(["Detecta enfermedades, parásitos o estrés en estas aves", {"mime_type": "image/jpeg", "data": foto.read()}])
            st.info(res.text)

# --- VENTAS/GASTOS ---
elif menu == "💰 Ventas/Gastos":
    t1, t2 = st.tabs(["🛒 Ventas", "💸 Gastos"])
    with t1:
        with st.form("v"):
            p = st.number_input("Total Recibido €", 0.0); u = st.number_input("Unidades", 1)
            if st.form_submit_button("Registrar Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, unidades) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), "Venta", p, u)).connection.commit(); st.rerun()
    with t2:
        with st.form("g"):
            cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Obras"])
            imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
            if st.form_submit_button("Registrar Gasto"):
                get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), cat, "Gasto Gral", imp, kg)).connection.commit(); st.rerun()

# --- PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Recogida Diaria")
    with st.form("pr"):
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (datetime.now().strftime("%d/%m/%Y"), l_id, h)).connection.commit(); st.rerun()

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "produccion", "gastos", "bajas", "ventas"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("Borrar ID", 0)
    if st.button("Eliminar"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
