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
st.set_page_config(page_title="CORRAL OMNI V84 - INDUSTRIAL", layout="wide", page_icon="🚜")

DB_PATH = "corral_maestro_pro.db"

# --- 1. DICCIONARIOS MAESTROS ---
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul", "Negra", "Extremeña", "Pita Pinta", "Ayam Cemani"],
    "Pollo (Carne)": ["Blanco Engorde (Broiler)", "Campero / Rural", "Crecimiento Lento", "Capón"],
    "Codorniz": ["Japónica (Huevo)", "Coreana (Carne)", "Vuelo"],
    "Pavo": ["Blanco Gigante", "Bronceado"],
    "Pato": ["Mulard", "Pekín", "Corredor Indio"]
}

# Curvas Biológicas
CURVA_PUESTA = {"sem": [0,18,20,25,30,40,50,60,70,80,90], "p": [0,0,0.15,0.85,0.94,0.92,0.88,0.80,0.70,0.60,0.40]}
CURVA_PESO = {"sem": [0,1,2,3,4,5,6,7,8,12,16], "kg": [0.05, 0.18, 0.45, 0.9, 1.5, 2.2, 2.9, 3.5, 4.0, 5.5, 7.0]}
# Consumo diario estimado por kg de peso vivo (aprox 10% del peso en pollos jóvenes, bajando al 5% en adultos)
FACTOR_PIENSO_CARNE = 0.08 

# --- 2. MOTOR DE BASE DE DATOS ---
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial_semanas INTEGER, precio_ud REAL, estado TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, unidades INTEGER, kg_vendidos REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- 3. CEREBRO DE CÁLCULO (CARNE & PIENSO) ---
def get_clima(key):
    if not key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

def calcular_estado_actual(lotes, bajas, gastos, temp):
    stock_pienso = gastos['kilos_pienso'].sum() if not gastos.empty else 0
    consumo_total_acumulado = 0
    peso_vivo_total = 0
    
    for _, l in lotes.iterrows():
        f_ini = datetime.strptime(l["fecha"], "%d/%m/%Y" if "/" in l["fecha"] else "%Y-%m-%d")
        dias_vida = (datetime.now() - f_ini).days
        muertes = bajas[bajas['lote_id']==l['id']]['cantidad'].sum() if not bajas.empty else 0
        vivos = max(0, l['cantidad'] - muertes)
        
        # Calcular consumo acumulado desde el primer día
        for d in range(dias_vida + 1):
            edad_sem = l['edad_inicial_semanas'] + (d/7)
            if "Gallina" in l['especie']:
                base = 0.115 # 115g fijos para ponedora
            else:
                peso_d = np.interp(edad_sem, CURVA_PESO["sem"], CURVA_PESO["kg"])
                base = peso_d * FACTOR_PIENSO_CARNE
            
            # Ajuste Clima
            if temp > 30: base *= 1.10
            consumo_total_acumulado += base * vivos
            
        # Peso actual para el Dashboard
        edad_hoy = l['edad_inicial_semanas'] + (dias_vida/7)
        if "Pollo" in l['especie'] or "Pavo" in l['especie']:
            peso_vivo_total += np.interp(edad_hoy, CURVA_PESO["sem"], CURVA_PESO["kg"]) * vivos
            
    return max(0, stock_pienso - consumo_total_acumulado), peso_vivo_total

# =========================================================
# INTERFAZ DE USUARIO
# =========================================================
inicializar_db()
if 'gemini_key' not in st.session_state: st.session_state['gemini_key'] = ""
if 'aemet_key' not in st.session_state: st.session_state['aemet_key'] = ""

lotes, gastos, produccion, bajas, ventas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("bajas"), cargar("ventas")
temp = get_clima(st.session_state['aemet_key'])

st.sidebar.title("🚜 CORRAL OMNI V84")
menu = st.sidebar.radio("MENÚ", ["📊 Dashboard", "🔮 Predicción Pro", "🐣 Alta Lotes", "🥚 Producción", "💰 Ventas/Gastos", "🩺 Salud IA", "📜 Histórico"])

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Panel Industrial")
    pienso_real, peso_total = calcular_estado_actual(lotes, bajas, gastos, temp)
    
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🌡️ Temp (Cartagena)", f"{temp:.1f}°C")
    c2.metric("🔋 Pienso en Silo", f"{pienso_real:.1f} kg")
    c3.metric("⚖️ Carne en Vivo", f"{peso_total:.1f} kg")
    c4.metric("💰 Beneficio", f"{(ventas['cantidad'].sum() - gastos['cantidad'].sum()):.2f} €")

    if pienso_real < 25: st.error(f"🚨 ALERTA: Quedan solo {pienso_real:.1f}kg de pienso.")

    st.divider()
    col_iz, col_de = st.columns(2)
    with col_iz:
        if not produccion.empty:
            st.plotly_chart(px.area(produccion, x='fecha', y='huevos', title="Producción Real de Huevos"), use_container_width=True)
    with col_de:
        if not lotes.empty:
            st.plotly_chart(px.pie(lotes, values='cantidad', names='raza', title="Distribución por Razas"), use_container_width=True)

# --- PREDICCIÓN PRO (CARNE + HUEVO) ---
elif menu == "🔮 Predicción Pro":
    st.title("🔮 Futuro del Corral (30 días)")
    fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(30)]
    h_data, c_data = [], []

    for i in range(30):
        h_dia, c_dia = 0, 0
        for _, l in lotes.iterrows():
            f_a = datetime.strptime(l["fecha"], "%d/%m/%Y" if "/" in l["fecha"] else "%Y-%m-%d")
            ed_sem = l["edad_inicial_semanas"] + ((datetime.now() - f_a).days + i) / 7
            vivos = l['cantidad'] - (bajas[bajas['lote_id']==l['id']]['cantidad'].sum() if not bajas.empty else 0)
            
            if "Gallina" in l['especie'] or "Codorniz" in l['especie']:
                h_dia += np.interp(ed_sem, CURVA_PUESTA["sem"], CURVA_PUESTA["p"]) * vivos
            else:
                c_dia += np.interp(ed_sem, CURVA_PESO["sem"], CURVA_PESO["kg"]) * vivos
        h_data.append(h_dia); c_data.append(c_dia)

    tab1, tab2 = st.tabs(["🥚 Predicción Huevos", "⚖️ Predicción Carne"])
    with tab1: st.plotly_chart(px.line(x=fechas, y=h_data, title="Huevos Diarios Previstos"), use_container_width=True)
    with tab2: st.plotly_chart(px.area(x=fechas, y=c_data, title="Evolución de Kilos Totales"), use_container_width=True)

# --- ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Entrada de Animales")
    with st.form("alta"):
        e = st.selectbox("Especie", list(ESPECIES_FULL.keys()))
        rz = st.selectbox("Raza", ESPECIES_FULL[e])
        cant = st.number_input("Cantidad", 1)
        ed = st.number_input("Semanas de vida", 0)
        pr = st.number_input("Precio unidad €", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), e, rz, int(cant), int(ed), pr, "Activo")).connection.commit()
            st.rerun()

# --- VENTAS/GASTOS ---
elif menu == "💰 Ventas/Gastos":
    v_tab, g_tab = st.tabs(["🛒 Ventas", "💸 Gastos"])
    with v_tab:
        with st.form("v"):
            tipo = st.selectbox("Tipo", ["Huevos", "Carne", "Ave Viva"])
            p = st.number_input("Importe €", 0.0); u = st.number_input("Unidades/Huevos", 0); kg = st.number_input("Si es carne, Kg totales", 0.0)
            if st.form_submit_button("Registrar Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, unidades, kg_vendidos) VALUES (?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), tipo, p, u, kg)).connection.commit(); st.rerun()
    with g_tab:
        with st.form("g"):
            cat = st.selectbox("Categoría", ["Pienso", "Aves", "Luz/Agua", "Otros"])
            imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kilos (solo si es pienso)", 0.0)
            if st.form_submit_button("Registrar Gasto"):
                get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), cat, "General", imp, kg)).connection.commit(); st.rerun()

# --- PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro Puesta")
    with st.form("p"):
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (datetime.now().strftime("%d/%m/%Y"), l_id, h)).connection.commit(); st.rerun()

# --- SALUD IA ---
elif menu == "🩺 Salud IA":
    st.title("🩺 Escáner Veterinario")
    f = st.file_uploader("Foto de las aves", type=['jpg','jpeg','png'])
    if f and st.session_state['gemini_key']:
        if st.button("Analizar con Gemini"):
            genai.configure(api_key=st.session_state['gemini_key'])
            model = genai.GenerativeModel("gemini-1.5-flash")
            res = model.generate_content(["Diagnóstico rápido de salud avícola:", {"mime_type": "image/jpeg", "data": f.read()}])
            st.info(res.text)

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "produccion", "gastos", "ventas", "bajas"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("Eliminar ID", 0)
    if st.button("Borrar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
