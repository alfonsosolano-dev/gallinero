import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import google.generativeai as genai
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL OMNI V74", layout="wide", page_icon="🚜")

# Estilos Pro
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e1e4e8; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stExpander"] { border: 1px solid #e1e4e8; border-radius: 10px; background-color: #fcfcfc; }
    .stButton>button { width: 100%; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = "corral_maestro_pro.db"

# --- DATOS MAESTROS ---
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul", "Negra", "Extremeña", "Pita Pinta", "Ayam Cemani"],
    "Pollo": ["Blanco Engorde (Broiler)", "Campero / Rural", "Crecimiento Lento", "Capón"],
    "Codorniz": ["Japónica (Huevo)", "Coreana (Carne)", "Vuelo"],
    "Pavo": ["Blanco Gigante", "Bronceado"],
    "Pato": ["Mulard", "Pekín", "Corredor Indio"],
    "Oca/Ganso": ["Común", "Tolosa"]
}

# Curva de puesta (Huevo por ave/día según edad en semanas)
CURVA_PUESTA = {
    "semana": [0, 18, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100],
    "porcentaje": [0.0, 0.0, 0.15, 0.85, 0.94, 0.92, 0.88, 0.82, 0.75, 0.65, 0.50, 0.30]
}

if 'gemini_key_mem' not in st.session_state: st.session_state['gemini_key_mem'] = ""
if 'aemet_key_mem' not in st.session_state: st.session_state['aemet_key_mem'] = ""

# =================================================================
# 1. MOTOR DE BASE DE DATOS
# =================================================================
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

# =================================================================
# 2. CEREBRO IA Y LÓGICA PREDICTIVA
# =================================================================
def get_clima(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

def predecir_puesta_lote(lote, dias_desde_hoy):
    try:
        f_ini = datetime.strptime(lote["fecha"], "%d/%m/%Y" if "/" in lote["fecha"] else "%Y-%m-%d")
        dias_totales = (datetime.now() - f_ini).days + dias_desde_hoy
        edad_semanas = lote['edad_inicial_semanas'] + (dias_totales / 7)
        prob = np.interp(edad_semanas, CURVA_PUESTA["semana"], CURVA_PUESTA["porcentaje"])
        return prob * lote['cantidad']
    except: return 0

def analizar_ia_v74(blob_or_txt, modo, key):
    if not key: return "⚠️ Falta API Key."
    try:
        genai.configure(api_key=key)
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        model_name = next((m for m in ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest'] if m in available), available[0])
        model = genai.GenerativeModel(model_name)
        if modo == "foto":
            res = model.generate_content([f"Analiza salud, plumaje y posibles enfermedades. Aves: {blob_or_txt[1]}", {"mime_type": "image/jpeg", "data": blob_or_txt[0]}])
        else: res = model.generate_content(blob_or_txt)
        return res.text
    except Exception as e: return f"❌ Error IA: {str(e)}"

# =================================================================
# 3. INTERFAZ DE USUARIO
# =================================================================
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V74")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "🔮 Predicción Puesta", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

with st.sidebar.expander("🔑 Llaves API"):
    g_key = st.text_input("Gemini Key", value=st.session_state['gemini_key_mem'], type="password")
    if g_key: st.session_state['gemini_key_mem'] = g_key
    a_key = st.text_input("AEMET Key", value=st.session_state['aemet_key_mem'], type="password")
    if a_key: st.session_state['aemet_key_mem'] = a_key

lotes, gastos, produccion, ventas, bajas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("ventas"), cargar("bajas")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("📊 Panel de Gestión Inteligente")
    temp = get_clima(st.session_state['aemet_key_mem'])
    
    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    balance = ventas['cantidad'].sum() - gastos['cantidad'].sum()
    c1.metric("💰 Balance", f"{balance:.2f} €", delta=f"{ventas['cantidad'].sum()} ing.")
    c2.metric("🌡️ Clima (Cartagena)", f"{temp:.1f} °C")
    c3.metric("🥚 Producción Total", f"{int(produccion['huevos'].sum())}")
    c4.metric("📉 Bajas", f"{int(bajas['cantidad'].sum())} aves")

    st.divider()
    col_izq, col_der = st.columns(2)
    with col_izq:
        if not produccion.empty:
            st.plotly_chart(px.line(produccion, x='fecha', y='huevos', color='color_huevo', title="Histórico de Puesta"), use_container_width=True)
    with col_der:
        if not gastos.empty:
            st.plotly_chart(px.pie(gastos, values='cantidad', names='categoria', hole=.4, title="Reparto de Gastos"), use_container_width=True)

# --- 🔮 PREDICCIÓN PUESTA ---
elif menu == "🔮 Predicción Puesta":
    st.title("🔮 Predicción IA de Huevos")
    if lotes.empty: st.warning("Registra un lote para ver predicciones.")
    else:
        dias_futuros = 30
        fechas = [(datetime.now() + timedelta(days=i)).strftime("%d/%m") for i in range(dias_futuros)]
        valores = []
        for i in range(dias_futuros):
            total_dia = sum([predecir_puesta_lote(l, i) for _, l in lotes.iterrows() if l['especie'] == "Gallina"])
            valores.append(total_dia)
        
        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(x=fechas, y=valores, mode='lines+markers', name="Huevos Previstos", line=dict(color='#FFA500', width=3)))
        fig_p.update_layout(title="Estimación de recogida (Próximos 30 días)", xaxis_title="Día", yaxis_title="Cant. Huevos")
        st.plotly_chart(fig_p, use_container_width=True)
        st.success(f"📈 Producción estimada para mañana: **{valores[1]:.1f} huevos**")

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.title("📸 Salud y Diagnóstico IA")
    df_f = cargar("fotos")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']}: {r['especie']} ({r['raza']})", expanded=True):
            subir = st.file_uploader("Subir foto de las aves", type=['jpg','png','jpeg'], key=f"u{r['id']}")
            if subir and st.button("🚀 Iniciar Escaneo IA", key=f"b{r['id']}"):
                blob = subir.read()
                res = analizar_ia_v74([blob, r['especie']], "foto", st.session_state['gemini_key_mem'])
                with get_conn() as conn: conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)", (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), res))
                st.rerun()
            f_db = df_f[df_f['lote_id']==r['id']].tail(1)
            if not f_db.empty: 
                c_i, c_d = st.columns([1,2])
                c_i.image(f_db.iloc[0]['imagen'])
                c_d.info(f"🩺 **Informe de Salud:**\n\n{f_db.iloc[0]['nota']}")

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Compra de Animales")
    with st.form("a"):
        c1, c2 = st.columns(2)
        esp = c1.selectbox("Especie", list(ESPECIES_FULL.keys()))
        rz = c2.selectbox("Raza", ESPECIES_FULL[esp])
        cant = st.number_input("Cantidad de aves", 1)
        ed = st.number_input("Edad al comprar (Semanas)", 0, help="Para gallinas ponedoras lo normal son 18-20 semanas")
        pr = st.number_input("Precio pagado por unidad €", 0.0)
        f = st.date_input("Fecha de entrada")
        if st.form_submit_button("Registrar Nuevo Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Recogida")
    with st.form("p"):
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Cantidad de huevos", 1)
        col = st.selectbox("Color", ["Marrón", "Blanco", "Verde", "Azul", "Codorniz"])
        if st.form_submit_button("Guardar Registro"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    t1, t2 = st.tabs(["🛒 Ventas", "💀 Bajas"])
    with t1:
        with st.form("v"):
            l = st.selectbox("De qué lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Uds vendidas", 1); p = st.number_input("Total cobrado €", 0.0)
            if st.form_submit_button("Registrar Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades, kg_carne) VALUES (?, 'Venta', ?, ?, ?, 0)", (datetime.now().strftime("%d/%m/%Y"), p, l, u)).connection.commit(); st.rerun()
    with t2:
        with st.form("b"):
            l = st.selectbox("Lote afectado", lotes['id'].tolist() if not lotes.empty else [])
            c = st.number_input("Nº aves perdidas", 1); m = st.text_input("Causa")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), l, c, m)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Gastos y Compras")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Obras", "Varios"])
        con = st.text_input("Concepto"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Añadir Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?, 'General')", (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg)).connection.commit(); st.rerun()

# --- 📜 HISTÓRICO Y COPIAS ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("Borrar ID", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

elif menu == "💾 Copias":
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar Base de Datos", f, "corral_backup.db")
