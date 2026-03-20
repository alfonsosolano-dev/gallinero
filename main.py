import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import plotly.express as px
import google.generativeai as genai

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL OMNI V86 - FINAL", layout="wide", page_icon="🚜")

DB_PATH = "corral_maestro_pro.db"

# --- DICCIONARIO MAESTRO (TODO LO QUE HABLAMOS) ---
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul", "Negra", "Extremeña", "Pita Pinta", "Ayam Cemani"],
    "Pollo (Carne)": ["Blanco Engorde (Broiler)", "Campero / Rural", "Crecimiento Lento", "Capón"],
    "Codorniz": ["Japónica (Huevo)", "Coreana (Carne)", "Vuelo"],
    "Pavo": ["Blanco Gigante", "Bronceado"],
    "Pato": ["Mulard", "Pekín", "Corredor Indio"]
}

# Curvas biológicas para el cruce de datos
CURVA_PUESTA = {"sem": [0,18,20,25,30,40,50,60,70,80], "p": [0,0,0.15,0.85,0.94,0.92,0.88,0.80,0.70,0.60]}
CURVA_PESO = {"sem": [0,1,2,3,4,5,6,7,8,12,16], "kg": [0.05, 0.18, 0.45, 0.9, 1.5, 2.2, 2.9, 3.5, 4.0, 5.5, 7.0]}

# --- MOTOR DE BASE DE DATOS (REPARACIÓN FORZOSA) ---
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        # TABLA DE LOTES (Asegurando todas las columnas críticas)
        c.execute("""CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            fecha TEXT, 
            especie TEXT, 
            raza TEXT, 
            cantidad INTEGER, 
            edad_inicial_semanas INTEGER, 
            precio_ud REAL, 
            estado TEXT)""")
        
        # TABLA DE PRODUCCIÓN
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
        
        # TABLA DE GASTOS
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
        
        # TABLA DE VENTAS
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, unidades INTEGER, kg_vendidos REAL)")
        
        # TABLA DE BAJAS
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)")

        # Reparación en caliente si faltan columnas por versiones viejas
        cols = [i[1] for i in c.execute("PRAGMA table_info(lotes)").fetchall()]
        if 'especie' not in cols: c.execute("ALTER TABLE lotes ADD COLUMN especie TEXT DEFAULT 'Gallina'")
        if 'edad_inicial_semanas' not in cols: c.execute("ALTER TABLE lotes ADD COLUMN edad_inicial_semanas INTEGER DEFAULT 0")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- LÓGICA DE PREDICCIÓN Y CLIMA ---
def get_clima(key):
    if not key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={key}"
        r = requests.get(url, timeout=5).json()
        return float(requests.get(r["datos"], timeout=5).json()[-1]["ta"])
    except: return 22.0

def calcular_rendimiento(lote, bajas, dias_futuros):
    try:
        f_alta = datetime.strptime(lote["fecha"], "%d/%m/%Y" if "/" in lote["fecha"] else "%Y-%m-%d")
        edad_sem = lote["edad_inicial_semanas"] + ((datetime.now() - f_alta).days + dias_futuros) / 7
        muertes = bajas[bajas['lote_id']==lote['id']]['cantidad'].sum() if not bajas.empty else 0
        vivos = max(0, lote['cantidad'] - muertes)
        
        if "Gallina" in lote["especie"] or ("Codorniz" in lote["especie"] and "Huevo" in lote["raza"]):
            return "H", np.interp(edad_sem, CURVA_PUESTA["sem"], CURVA_PUESTA["p"]) * vivos
        else:
            return "C", np.interp(edad_sem, CURVA_PESO["sem"], CURVA_PESO["kg"]) * vivos
    except: return None, 0

# --- INTERFAZ STREAMLIT ---
inicializar_db()
lotes, produccion, gastos, ventas, bajas = cargar("lotes"), cargar("produccion"), cargar("gastos"), cargar("ventas"), cargar("bajas")

st.sidebar.title("🚜 CORRAL OMNI V86")
menu = st.sidebar.radio("MENÚ", ["📊 Dashboard", "🔮 Predicción Multi-Especie", "🐣 Alta de Aves", "🥚 Producción", "💰 Finanzas", "🩺 IA Salud", "📜 Histórico"])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Resumen del Corral")
    t_cartagena = get_clima(st.sidebar.text_input("AEMET Key", type="password"))
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🌡️ Temp Actual", f"{t_cartagena}°C")
    c2.metric("🐔 Total Aves", int(lotes['cantidad'].sum() - bajas['cantidad'].sum() if not lotes.empty else 0))
    c3.metric("💰 Balance", f"{(ventas['cantidad'].sum() - gastos['cantidad'].sum() if not ventas.empty else 0):.2f} €")

    if not produccion.empty:
        st.plotly_chart(px.area(produccion, x='fecha', y='huevos', title="Producción de Huevos"), use_container_width=True)

# --- ALTA DE AVES (EL CORAZÓN DEL SISTEMA) ---
elif menu == "🐣 Alta de Aves":
    st.header("🐣 Entrada de Nuevo Lote")
    with st.form("alta"):
        col1, col2 = st.columns(2)
        esp = col1.selectbox("Especie", list(ESPECIES_FULL.keys()))
        rz = col2.selectbox("Raza/Clase", ESPECIES_FULL[esp])
        cant = st.number_input("Cantidad", 1)
        ed = st.number_input("Semanas de vida actuales", 0)
        pr = st.number_input("Coste Unidad €", 0.0)
        if st.form_submit_button("Registrar Entrada"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr, "Activo")).connection.commit()
            st.success("¡Lote registrado! Los datos ya se cruzan con las predicciones."); st.rerun()

# --- PREDICCIÓN CRUZADA ---
elif menu == "🔮 Predicción Multi-Especie":
    st.header("🔮 Predicción de Producción (30 días)")
    if lotes.empty: st.warning("No hay lotes registrados.")
    else:
        fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(30)]
        h_vals, c_vals = [], []
        for i in range(30):
            h_dia, c_dia = 0, 0
            for _, l in lotes.iterrows():
                tipo, val = calcular_rendimiento(l, bajas, i)
                if tipo == "H": h_dia += val
                elif tipo == "C": c_dia += val
            h_vals.append(h_dia); c_vals.append(c_dia)
        
        st.subheader("🥚 Producción de Huevos Estimada")
        st.plotly_chart(px.line(x=fechas, y=h_vals), use_container_width=True)
        st.subheader("⚖️ Crecimiento de Carne Estimado (Kg)")
        st.plotly_chart(px.area(x=fechas, y=c_vals, color_discrete_sequence=['red']), use_container_width=True)

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "produccion", "gastos", "ventas", "bajas"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        idx = st.number_input("ID a eliminar", int(df['id'].min()), int(df['id'].max()))
        if st.button("Borrar"): 
            get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

# --- OTROS MENÚS ---
elif menu == "🥚 Producción":
    with st.form("p"):
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        cant = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (datetime.now().strftime("%d/%m/%Y"), l_id, cant)).connection.commit(); st.rerun()

elif menu == "💰 Finanzas":
    t1, t2 = st.tabs(["Ventas", "Gastos"])
    with t1:
        with st.form("v"):
            val = st.number_input("Importe €", 0.0); kg = st.number_input("Kg vendidos", 0.0)
            if st.form_submit_button("Vender"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, kg_vendidos) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), "Venta", val, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("g"):
            cat = st.selectbox("Cat", ["Pienso", "Medicina", "Luz"])
            val = st.number_input("€", 0.0); kg = st.number_input("Kg Pienso", 0.0)
            if st.form_submit_button("Gasto"):
                get_conn().execute("INSERT INTO gastos (fecha, categoria, cantidad, kilos_pienso) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), cat, val, kg)).connection.commit(); st.rerun()
