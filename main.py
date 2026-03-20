import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np
import base64
import google.generativeai as genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL IA MASTER V56", layout="wide", page_icon="🥚")

DB_PATH = "corral_maestro_pro.db"

# =================================================================
# MOTOR DE DATOS Y TABLAS
# =================================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# INTELIGENCIA: CLIMA, CONSUMO Y GEMINI GRATIS
# =================================================================
CONFIG_ESPECIES = {
    "Gallina Roja": 0.110, "Gallina Blanca": 0.105, "Gallina Huevo Verde": 0.115, 
    "Codorniz Japónica": 0.025, "Pollo Blanco Engorde": 0.180, "Pollo Campero": 0.140
}

def get_clima_cartagena(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

def calcular_pienso_pro(gastos, lotes, t_actual):
    comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    f_clima = 1.15 if t_actual > 30 else (1.10 if t_actual < 10 else 1.0)
    
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * 0.85 * f_clima
                for d in range(dias + 1):
                    edad = r["edad_inicial"] + d
                    f_edad = 0.3 if edad < 20 else (0.7 if edad < 45 else 1.0)
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, comprado - consumo)

def analizar_foto_gratis(blob, especie, api_key):
    if not api_key: return "⚠️ Pega tu Google Key en el lateral."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        contenido = [{"mime_type": "image/jpeg", "data": blob}, 
                     f"Analiza la salud y crecimiento de estas {especie}. Sé muy específico."]
        res = model.generate_content(contenido)
        return res.text
    except Exception as e: return f"Error IA: {str(e)}"

# =================================================================
# INTERFAZ PRINCIPAL (DISEÑO IMAGE_0.PNG)
# =================================================================
inicializar_db()
lotes, gastos, produccion = cargar_tabla("lotes"), cargar_tabla("gastos"), cargar_tabla("produccion")

st.sidebar.title("🚜 CORRAL MASTER V56")
menu = st.sidebar.radio("", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Puesta", "💸 Gastos", "🐣 Alta Aves", "💾 Copias"])
GEMINI_KEY = st.sidebar.text_input("🔑 Google Gemini Key (Gratis)", type="password")
AEMET_KEY = st.sidebar.text_input("🌡️ AEMET Key", type="password")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🚜 Panel General de Control")
    temp = get_clima_cartagena(AEMET_KEY)
    stock = calcular_pienso_pro(gastos, lotes, temp)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c2.metric("🌡️ Temp Cartagena", f"{temp:.1f} °C")
    c3.metric("🥚 Puesta Total", f"{produccion['huevos'].sum() if not produccion.empty else 0} uds")

    if not produccion.empty:
        import plotly.express as px
        fig = px.bar(produccion, x='fecha', y='huevos', color='color_huevo', title="Producción por Tipo/Color")
        st.plotly_chart(fig, use_container_width=True)

# --- 📈 CRECIMIENTO IA (DISEÑO SOLICITADO) ---
elif menu == "📈 Crecimiento IA":
    st.title("📈 Seguimiento Visual (IA Google)")
    df_fotos = cargar_tabla("fotos")
    
    if lotes.empty: st.warning("No hay aves.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📋 LOTE {r['id']}: {r['especie']} {r['raza']}", expanded=True):
                col_izq, col_der = st.columns([2, 1])
                
                with col_izq:
                    # Foto más reciente
                    prev = df_fotos[df_fotos['lote_id']==r['id']].tail(1)
                    if not prev.empty: st.image(prev.iloc[0]['imagen'], use_column_width=True)
                    
                    st.divider()
                    t1, t2 = st.tabs(["🎥 Cámara", "📁 Archivo"])
                    with t1: cam = st.camera_input("Capturar", key=f"c_{r['id']}")
                    with t2: arc = st.file_uploader("Subir", type=['jpg','png','jpeg'], key=f"f_{r['id']}")
                    
                    foto = cam if cam else arc
                    if foto and st.button("💾 Guardar y Analizar Gratis", key=f"b_{r['id']}"):
                        blob = foto.read()
                        nota = analizar_foto_gratis(blob, r['especie'], GEMINI_KEY)
                        conn = get_conn()
                        conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                     (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), nota))
                        conn.commit(); st.rerun()
                
                with col_der:
                    st.metric("Total Aves", f"{r['cantidad']} uds")
                    if not prev.empty:
                        st.write("### 🤖 Informe IA:")
                        st.info(prev.iloc[0]['nota'])

# --- 🥚 PUESTA ---
elif menu == "🥚 Puesta":
    st.title("🥚 Registro de Puesta")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color", ["Normal", "Verde", "Azul", "Codorniz"])
        cant = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", 
                               (f.strftime("%d/%m/%Y"), l, cant, col)).connection.commit(); st.rerun()

# --- 🐣 ALTA AVES ---
elif menu == "🐣 Alta Aves":
    st.title("🐣 Nuevas Aves")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Huevo Verde", "Campero", "Blanco Engorde", "Codorniz Japónica"])
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad (días)", 0)
        f_e = st.date_input("Fecha Entrada")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, estado) VALUES (?,?,?,?,?, 'Activo')", 
                               (f_e.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed))).connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Backup")
    with open(DB_PATH, "rb") as f:
        st.download_button("📥 Descargar Base de Datos (.db)", f, "corral_master.db")
    sub = st.file_uploader("Subir Backup", type="db")
    if sub and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.success("Restaurado."); st.rerun()
