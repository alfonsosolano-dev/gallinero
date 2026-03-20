import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import google.generativeai as genai

# --- CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="CORRAL OMNI V69", layout="wide", page_icon="🚜")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f2f6; }
    div[data-testid="stExpander"] { border: 1px solid #f0f2f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = "corral_maestro_pro.db"

# Persistencia de llaves en sesión
if 'gemini_key_mem' not in st.session_state:
    st.session_state['gemini_key_mem'] = ""
if 'aemet_key_mem' not in st.session_state:
    st.session_state['aemet_key_mem'] = ""

# =================================================================
# 1. MOTOR DE BASE DE DATOS
# =================================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        tablas = [
            "lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)",
            "produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT)",
            "gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT)",
            "ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, unidades INTEGER, kg_carne REAL)",
            "bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)",
            "fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)"
        ]
        for t in tablas: c.execute(f"CREATE TABLE IF NOT EXISTS {t}")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# =================================================================
# 2. INTELIGENCIA: CLIMA, PIENSO E IA (PARCHE DEFINITIVO)
# =================================================================
CONFIG_ESPECIES = {"Gallina Roja": 0.110, "Gallina Blanca": 0.105, "Gallina Huevo Verde": 0.115, "Codorniz": 0.025, "Pollo Blanco": 0.180, "Pollo Campero": 0.140}

def get_clima(api_key):
    if not api_key: return 18.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        datos = requests.get(requests.get(url, timeout=5).json()["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 18.0

def calcular_pienso(gastos, lotes, temp):
    total = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    f_clima = 1.12 if temp > 30 else 1.0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * f_clima
                for d in range(dias + 1):
                    f_edad = 0.4 if (r["edad_inicial"] + d) < 25 else 1.0
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, total - consumo)

def analizar_ia_v69(blob, especie, key):
    if not key: return "⚠️ Pega tu API Key en el menú lateral."
    try:
        genai.configure(api_key=key)
        # Probamos el modelo más estable para visión
        model = genai.GenerativeModel('gemini-1.5-flash')
        img_part = {"mime_type": "image/jpeg", "data": blob}
        prompt = f"Actúa como veterinario avícola. Analiza estas aves {especie}. Comenta plumaje, crestas y salud general en 3 frases."
        response = model.generate_content([prompt, img_part])
        return response.text
    except Exception as e:
        if "403" in str(e):
            return "❌ Error 403: Tu API Key no es válida para Gemini AI Studio. Créala gratis en 'aistudio.google.com'."
        return f"❌ Error de conexión: {str(e)}"

# =================================================================
# 3. INTERFAZ DE USUARIO
# =================================================================
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V69")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

with st.sidebar.expander("🔑 Configuración de Llaves", expanded=True):
    g_key = st.text_input("Google Gemini Key", value=st.session_state['gemini_key_mem'], type="password", help="Consíguela en aistudio.google.com")
    if g_key: st.session_state['gemini_key_mem'] = g_key
    a_key = st.text_input("AEMET Key (Cartagena)", value=st.session_state['aemet_key_mem'], type="password")
    if a_key: st.session_state['aemet_key_mem'] = a_key

lotes, gastos, produccion, ventas, bajas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("ventas"), cargar("bajas")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("📊 Panel de Control General")
    temp = get_clima(st.session_state['aemet_key_mem'])
    stock = calcular_pienso(gastos, lotes, temp)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔋 Pienso", f"{stock:.1f} kg")
    c2.metric("💰 Gastos", f"{gastos['cantidad'].sum():.1f} €")
    c3.metric("🌡️ Clima", f"{temp:.1f} °C")
    c4.metric("🥚 Hoy", f"{produccion[produccion['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()} uds")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if not produccion.empty:
            import plotly.express as px
            st.plotly_chart(px.line(produccion, x='fecha', y='huevos', color='color_huevo', title="Historial de Puesta"), use_container_width=True)
    with col2:
        if not gastos.empty:
            import plotly.express as px
            st.plotly_chart(px.pie(gastos, values='cantidad', names='categoria', title="Gastos por Categoría"), use_container_width=True)

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.title("📸 Seguimiento Visual Gemini")
    df_f = cargar("fotos")
    if lotes.empty: st.warning("Crea un lote en 'Alta Lotes' primero.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📷 Lote {r['id']}: {r['especie']} {r['raza']}", expanded=True):
                c_izq, c_der = st.columns([2, 1])
                with c_izq:
                    f_rec = df_f[df_f['lote_id']==r['id']].tail(1)
                    if not f_rec.empty: st.image(f_rec.iloc[0]['imagen'])
                    archivo = st.file_uploader("Nueva foto", type=['jpg','png','jpeg'], key=f"f{r['id']}")
                    if archivo and st.button("🚀 Analizar con IA", key=f"b{r['id']}"):
                        blob = archivo.read()
                        with st.spinner("Consultando a Gemini..."):
                            res = analizar_ia_v69(blob, r['especie'], st.session_state['gemini_key_mem'])
                            with get_conn() as conn:
                                conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                             (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), res))
                            st.rerun()
                with c_der:
                    if not f_rec.empty:
                        st.markdown("### 🤖 Informe IA:")
                        st.info(f_rec.iloc[0]['nota'])

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Puesta")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color", ["Normal", "Verde", "Azul", "Codorniz"])
        h = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (f.strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    st.title("💰 Salidas")
    t1, t2 = st.tabs(["🛒 Ventas", "💀 Bajas"])
    with t1:
        with st.form("v"):
            tp = st.radio("Tipo", ["Venta", "Consumo"])
            l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("€", 0.0); kg = st.number_input("Kg", 0.0)
            if st.form_submit_button("Registrar"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades, kg_carne) VALUES (?,?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), tp, p, l, u, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("b"):
            lb = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            cb = st.number_input("Nº Aves", 1); mot = st.text_input("Motivo")
            if st.form_submit_button("Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), lb, cb, mot)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Obras"])
        dest = st.selectbox("Destino", ["General", "Gallinas", "Pollos", "Codornices"])
        con = st.text_input("Concepto"); i = st.number_input("€", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Nuevo Lote")
    with st.form("a"):
        e = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Huevo Verde", "Campero", "Blanco"])
        c = st.number_input("Nº", 1); ed = st.number_input("Edad", 0); pr = st.number_input("Precio ud", 0.0)
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (datetime.now().strftime("%d/%m/%Y"), e, rz, int(c), int(ed), pr)).connection.commit(); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    m = {"Blanco": 55, "Campero": 90}
    for rz, d in m.items():
        f = datetime(2026, 12, 24) - timedelta(days=d)
        st.warning(f"🍗 **{rz}**: Comprar el **{f.strftime('%d/%m/%Y')}**")

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Gestión de Datos")
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar .db", f, "corral_master.db")
    sub = st.file_uploader("Subir .db", type="db")
    if sub and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar(t); st.dataframe(df, use_container_width=True)
    idx = st.number_input("Borrar ID", 0)
    if st.button("Borrar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
