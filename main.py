import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import plotly.express as px
import google.generativeai as genai

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL OMNI V85", layout="wide", page_icon="🚜")

DB_PATH = "corral_maestro_pro.db"

# --- 1. DICCIONARIO MAESTRO AMPLIADO ---
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul", "Negra", "Extremeña", "Pita Pinta", "Ayam Cemani"],
    "Pollo (Carne)": ["Blanco Engorde (Broiler)", "Campero / Rural", "Crecimiento Lento", "Capón"],
    "Codorniz": ["Japónica (Huevo)", "Coreana (Carne)", "Vuelo"],
    "Pavo": ["Blanco Gigante", "Bronceado"],
    "Pato": ["Mulard", "Pekín", "Corredor Indio"]
}

CURVA_PUESTA = {"sem": [0,18,20,25,30,40,50,60,70,80], "p": [0,0,0.15,0.85,0.94,0.92,0.88,0.80,0.70,0.60]}
CURVA_PESO = {"sem": [0,1,2,3,4,5,6,7,8,12,16], "kg": [0.05, 0.18, 0.45, 0.9, 1.5, 2.2, 2.9, 3.5, 4.0, 5.5, 7.0]}

# --- 2. MOTOR DE BASE DE DATOS CON AUTO-REPARACIÓN ---
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        # Crear tablas si no existen
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial_semanas INTEGER, precio_ud REAL, estado TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, unidades INTEGER, kg_vendidos REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)")
        
        # SCRIPT DE REPARACIÓN: Añadir columnas faltantes si la DB es vieja
        columnas_lotes = [info[1] for info in c.execute("PRAGMA table_info(lotes)").fetchall()]
        if 'edad_inicial_semanas' not in columnas_lotes:
            c.execute("ALTER TABLE lotes ADD COLUMN edad_inicial_semanas INTEGER DEFAULT 0")
        if 'especie' not in columnas_lotes:
            c.execute("ALTER TABLE lotes ADD COLUMN especie TEXT DEFAULT 'Gallina'")
            
        columnas_ventas = [info[1] for info in c.execute("PRAGMA table_info(ventas)").fetchall()]
        if 'kg_vendidos' not in columnas_ventas:
            c.execute("ALTER TABLE ventas ADD COLUMN kg_vendidos REAL DEFAULT 0.0")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- 3. FUNCIONES DE CÁLCULO ---
def get_clima(key):
    if not key: return 20.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={key}"
        r = requests.get(url, timeout=5).json()
        return float(requests.get(r["datos"], timeout=5).json()[-1]["ta"])
    except: return 20.0

def predecir_lote(lote, bajas, dias_plus):
    try:
        f_alta = datetime.strptime(lote["fecha"], "%d/%m/%Y" if "/" in lote["fecha"] else "%Y-%m-%d")
        edad_hoy_dias = (datetime.now() - f_alta).days + (lote["edad_inicial_semanas"] * 7)
        edad_futura_sem = (edad_hoy_dias + dias_plus) / 7
        muertes = bajas[bajas['lote_id']==lote['id']]['cantidad'].sum() if not bajas.empty else 0
        vivos = max(0, lote['cantidad'] - muertes)
        
        if "Gallina" in lote["especie"] or ("Codorniz" in lote["especie"] and "Huevo" in lote["raza"]):
            return ("H", np.interp(edad_futura_sem, CURVA_PUESTA["sem"], CURVA_PUESTA["p"]) * vivos)
        else:
            return ("C", np.interp(edad_futura_sem, CURVA_PESO["sem"], CURVA_PESO["kg"]) * vivos)
    except: return (None, 0)

# --- 4. INTERFAZ ---
inicializar_db()
lotes, gastos, produccion, bajas, ventas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("bajas"), cargar("ventas")

# Gestión de Keys en session_state para que no se borren al cambiar de pestaña
if 'g_key' not in st.session_state: st.session_state.g_key = ""
if 'a_key' not in st.session_state: st.session_state.a_key = ""

st.sidebar.title("🚜 CORRAL OMNI V85")
menu = st.sidebar.radio("MENÚ", ["📊 Dashboard", "🔮 Predicción Pro", "🐣 Alta Lotes", "🥚 Producción", "💰 Ventas/Gastos", "🩺 Salud IA", "📜 Histórico"])

with st.sidebar.expander("🔑 Configuración de Llaves"):
    st.session_state.g_key = st.text_input("Gemini API Key", value=st.session_state.g_key, type="password")
    st.session_state.a_key = st.text_input("AEMET API Key", value=st.session_state.a_key, type="password")

temp = get_clima(st.session_state.a_key)

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Resumen Operativo")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🌡️ Temp", f"{temp}°C")
    c2.metric("🐔 Aves", int(lotes['cantidad'].sum() - bajas['cantidad'].sum() if not lotes.empty else 0))
    c3.metric("🥚 Hoy", int(produccion.tail(1)['huevos'].sum() if not produccion.empty else 0))
    c4.metric("💰 Balance", f"{(ventas['cantidad'].sum() - gastos['cantidad'].sum() if not ventas.empty else 0):.2f} €")
    
    if not produccion.empty:
        st.plotly_chart(px.line(produccion, x='fecha', y='huevos', title="Producción Diaria"), use_container_width=True)

# --- PREDICCIÓN PRO (Aquí estaba el error del Key Error) ---
elif menu == "🔮 Predicción Pro":
    st.title("🔮 Futuro del Corral (30 días)")
    if lotes.empty:
        st.warning("Primero registra un lote en 'Alta Lotes'.")
    else:
        fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(30)]
        h_total, c_total = [], []
        for i in range(30):
            h_dia, c_dia = 0, 0
            for _, l in lotes.iterrows():
                tipo, val = predecir_lote(l, bajas, i)
                if tipo == "H": h_dia += val
                elif tipo == "C": c_dia += val
            h_total.append(h_dia); c_total.append(c_dia)
        
        st.subheader("🥚 Predicción de Huevos")
        st.plotly_chart(px.line(x=fechas, y=h_total), use_container_width=True)
        st.subheader("⚖️ Predicción de Kilos de Carne")
        st.plotly_chart(px.area(x=fechas, y=c_total, color_discrete_sequence=['red']), use_container_width=True)

# --- ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Registro de Aves")
    with st.form("alta"):
        col1, col2 = st.columns(2)
        esp = col1.selectbox("Especie", list(ESPECIES_FULL.keys()))
        rz = col2.selectbox("Raza", ESPECIES_FULL[esp])
        cant = st.number_input("Cantidad", 1)
        ed = st.number_input("Edad (Semanas)", 0)
        pr = st.number_input("Precio/ud €", 0.0)
        if st.form_submit_button("Guardar Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr, "Activo")).connection.commit()
            st.success("Lote guardado. Ve a 'Predicción Pro' para ver los resultados."); st.rerun()

# --- SALUD IA ---
elif menu == "🩺 Salud IA":
    st.title("🩺 Diagnóstico IA")
    if not st.session_state.g_key:
        st.error("Introduce la Gemini Key en el menú lateral.")
    else:
        img = st.file_uploader("Sube foto de tus aves", type=['jpg','png','jpeg'])
        if img and st.button("Analizar"):
            genai.configure(api_key=st.session_state.g_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            res = model.generate_content(["Analiza la salud de estas aves:", {"mime_type": "image/jpeg", "data": img.read()}])
            st.write(res.text)

# --- VENTAS/GASTOS ---
elif menu == "💰 Ventas/Gastos":
    t1, t2 = st.tabs(["🛒 Ventas", "💸 Gastos"])
    with t1:
        with st.form("v"):
            tipo = st.selectbox("Tipo", ["Huevos", "Carne", "Aves Vivas"])
            imp = st.number_input("Total €", 0.0); kg = st.number_input("Kg (si es carne)", 0.0)
            if st.form_submit_button("Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, unidades, kg_vendidos) VALUES (?,?,?,?,?)",
                                   (datetime.now().strftime("%d/%m/%Y"), tipo, imp, 0, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("g"):
            cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Luz/Agua"])
            imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
            if st.form_submit_button("Gasto"):
                get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)",
                                   (datetime.now().strftime("%d/%m/%Y"), cat, "Gasto", imp, kg)).connection.commit(); st.rerun()

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    tab = st.selectbox("Tabla", ["lotes", "produccion", "gastos", "ventas", "bajas"])
    df = cargar(tab)
    st.dataframe(df, use_container_width=True)
    borrar = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"):
        get_conn().execute(f"DELETE FROM {tab} WHERE id={borrar}").connection.commit(); st.rerun()
