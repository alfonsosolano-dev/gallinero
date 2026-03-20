import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai

# --- CONFIGURACIÓN ESTRATÉGICA ---
st.set_page_config(page_title="CORRAL OMNI V81 - EMPRESA", layout="wide", page_icon="🚜")

DB_PATH = "corral_maestro_pro.db"

# --- LISTADOS DE RAZAS (MODULO CLASES) ---
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul", "Negra", "Extremeña", "Pita Pinta", "Ayam Cemani"],
    "Pollo": ["Blanco Engorde (Broiler)", "Campero / Rural", "Crecimiento Lento"],
    "Codorniz": ["Japónica (Huevo)", "Coreana (Carne)"],
    "Pavo": ["Blanco Gigante", "Bronceado"],
    "Pato": ["Mulard", "Pekín", "Corredor Indio"]
}

# --- CONFIG IA Y MEMORIA ---
if 'gemini_key' not in st.session_state: st.session_state['gemini_key'] = ""
if 'aemet_key' not in st.session_state: st.session_state['aemet_key'] = ""

# =========================================================
# 1. MOTOR DE BASE DE DATOS (PROTEGIDO)
# =========================================================
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial_semanas INTEGER, precio_ud REAL, estado TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, unidades INTEGER, kg_carne REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# =========================================================
# 2. INTELIGENCIA DE NEGOCIO Y CLIMA
# =========================================================
def get_clima(key):
    if not key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

CURVA = {
    "sem": [0,18,20,25,30,40,50,60,70,80,90],
    "p":   [0,0,0.15,0.85,0.94,0.92,0.88,0.80,0.70,0.60,0.40]
}

def puesta_modelo(lote, bajas, dias):
    try:
        f = datetime.strptime(lote["fecha"], "%d/%m/%Y" if "/" in lote["fecha"] else "%Y-%m-%d")
        edad_dias = (datetime.now() - f).days + dias
        semanas = lote["edad_inicial_semanas"] + edad_dias/7
        prob = np.interp(semanas, CURVA["sem"], CURVA["p"])
        muertes = bajas[bajas['lote_id']==lote['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas = max(0, lote['cantidad'] - muertes)
        return prob * vivas
    except: return 0

def cerebro_corral(lotes, produccion, gastos, bajas, temp, ventas):
    res = {}
    total_aves = lotes['cantidad'].sum() if not lotes.empty else 0
    huevos_hoy = produccion.tail(1)['huevos'].sum() if not produccion.empty else 0
    productividad = huevos_hoy / max(total_aves, 1)
    
    if productividad < 0.4: res["estado"], res["msg"] = "CRITICO", "🚨 Producción Crítica"
    elif productividad < 0.7: res["estado"], res["msg"] = "ALERTA", "⚠️ Producción en revisión"
    else: res["estado"], res["msg"] = "OK", "✅ Rendimiento Óptimo"
    
    ingresos = ventas['cantidad'].sum() if not ventas.empty else 0
    gastos_total = gastos['cantidad'].sum() if not gastos.empty else 0
    res["beneficio"] = ingresos - gastos_total
    return res

# =========================================================
# 3. INTERFAZ Y MENÚS
# =========================================================
inicializar_db()
lotes, gastos, produccion, bajas, ventas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("bajas"), cargar("ventas")

st.sidebar.title("🚜 CORRAL OMNI V81")
menu = st.sidebar.radio("MENÚ", ["Dashboard", "🔮 Predicción", "🐣 Alta/Razas", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🩺 IA Salud", "📜 Histórico"])

with st.sidebar.expander("🔑 Configuración"):
    k1 = st.text_input("Gemini Key", type="password", value=st.session_state['gemini_key'])
    if k1: st.session_state['gemini_key'] = k1
    k2 = st.text_input("AEMET Key", type="password", value=st.session_state['aemet_key'])
    if k2: st.session_state['aemet_key'] = k2

temp = get_clima(st.session_state['aemet_key'])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Panel de Control Empresa")
    ana = cerebro_corral(lotes, produccion, gastos, bajas, temp, ventas)
    
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🌡️ Temp", f"{temp:.1f}°C")
    c2.metric("🥚 Hoy", int(produccion.tail(1)['huevos'].sum() if not produccion.empty else 0))
    c3.metric("🐔 Aves", int(lotes['cantidad'].sum() - bajas['cantidad'].sum() if not lotes.empty else 0))
    c4.metric("💰 Beneficio", f"{ana['beneficio']:.2f} €")
    
    if ana["estado"] == "CRITICO": st.error(ana["msg"])
    elif ana["estado"] == "ALERTA": st.warning(ana["msg"])
    else: st.success(ana["msg"])
    
    if not produccion.empty:
        st.plotly_chart(px.area(produccion, x='fecha', y='huevos', title="Evolución de Puesta Real"), use_container_width=True)

# --- ALTA LOTES POR RAZAS ---
elif menu == "🐣 Alta/Razas":
    st.title("🐣 Gestión de Clases y Lotes")
    with st.form("alta"):
        e = st.selectbox("Especie", list(ESPECIES_FULL.keys()))
        rz = st.selectbox("Raza/Clase", ESPECIES_FULL[e])
        cant = st.number_input("Nº Aves", 1); ed = st.number_input("Edad (Semanas)", 0)
        pr = st.number_input("Coste Unidad €", 0.0)
        if st.form_submit_button("Crear Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), e, rz, int(cant), int(ed), pr, "Activo")).connection.commit()
            st.rerun()

# --- PREDICCIÓN ---
elif menu == "🔮 Predicción":
    st.title("🔮 Estimación de Producción a 30 días")
    fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(30)]
    valores = [sum([puesta_modelo(l, bajas, i) for _,l in lotes.iterrows()]) for i in range(30)]
    st.plotly_chart(px.line(x=fechas, y=valores, labels={'x':'Día','y':'Huevos Estimados'}, title="Capacidad Teórica de Puesta"), use_container_width=True)

# --- IA SALUD ---
elif menu == "🩺 IA Salud":
    st.title("🩺 Diagnóstico Visual IA")
    foto = st.file_uploader("Subir foto de aves", type=['jpg','png','jpeg'])
    if foto and st.session_state['gemini_key']:
        st.image(foto)
        if st.button("Analizar"):
            genai.configure(api_key=st.session_state['gemini_key'])
            model = genai.GenerativeModel("gemini-1.5-flash")
            res = model.generate_content(["Analiza la salud de estas aves y detecta posibles problemas de plumaje o decaimiento", {"mime_type": "image/jpeg", "data": foto.read()}])
            st.info(res.text)

# --- VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    t1, t2 = st.tabs(["🛒 Ventas", "💀 Bajas"])
    with t1:
        with st.form("v"):
            l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Uds Vendidas", 1); p = st.number_input("Total €", 0.0)
            if st.form_submit_button("Registrar Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades, kg_carne) VALUES (?,?,?,?,?,?)",
                                   (datetime.now().strftime("%d/%m/%Y"), "Venta", p, l_id, u, 0)).connection.commit(); st.rerun()
    with t2:
        with st.form("b"):
            l_id = st.selectbox("Lote afectado", lotes['id'].tolist() if not lotes.empty else [])
            c = st.number_input("Nº Aves", 1); m = st.text_input("Causa")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)",
                                   (datetime.now().strftime("%d/%m/%Y"), l_id, c, m)).connection.commit(); st.rerun()

# --- GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Registro de Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Compra Aves", "Medicina", "Obras"])
        con = st.text_input("Concepto"); imp = st.number_input("Euros €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Añadir"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, imp, kg, "General")).connection.commit(); st.rerun()

# --- PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Huevos")
    with st.form("pr"):
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), l_id, h)).connection.commit(); st.rerun()

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes","gastos","produccion","bajas","ventas"])
    st.dataframe(cargar(t), use_container_width=True)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Borrar Registro"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
