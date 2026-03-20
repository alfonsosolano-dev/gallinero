import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import google.generativeai as genai
import plotly.express as px

# --- CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="CORRAL OMNI V71", layout="wide", page_icon="🧠")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f2f6; }
    div[data-testid="stExpander"] { border: 1px solid #f0f2f6; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = "corral_maestro_pro.db"

if 'gemini_key_mem' not in st.session_state: st.session_state['gemini_key_mem'] = ""
if 'aemet_key_mem' not in st.session_state: st.session_state['aemet_key_mem'] = ""

# =================================================================
# 1. MOTOR DE BASE DE DATOS
# =================================================================
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
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
# 2. INTELIGENCIA Y PILOTO AUTOMÁTICO
# =================================================================
CONFIG_ESPECIES = {"Roja": 0.110, "Blanca": 0.105, "Huevo Verde": 0.115, "Codorniz": 0.025, "Blanco": 0.180, "Campero": 0.140}

def get_clima(api_key):
    if not api_key: return 20.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 20.0

def calcular_stock_pienso(gastos, lotes, temp):
    total = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    f_clima = 1.12 if temp > 30 else 1.0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(r['raza'], 0.100) * f_clima
                for d in range(dias + 1):
                    f_edad = 0.4 if (r["edad_inicial"] + d) < 25 else 1.0
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, total - consumo)

def piloto_automatico(stock, lotes, temp):
    if lotes.empty or stock <= 0: return None
    consumo_dia = 0
    for _, r in lotes.iterrows():
        base = CONFIG_ESPECIES.get(r['raza'], 0.1)
        consumo_dia += base * r['cantidad']
    if temp > 30: consumo_dia *= 1.12
    dias_restantes = stock / consumo_dia
    
    res = {"dias_restantes": dias_restantes, "consumo_dia": consumo_dia}
    if dias_restantes < 3: res.update({"nivel": "CRITICO", "msj": "🚨 COMPRA PIENSO YA", "kg": consumo_dia * 10})
    elif dias_restantes < 7: res.update({"nivel": "ALERTA", "msj": "⚠️ Stock bajo", "kg": consumo_dia * 14})
    else: res.update({"nivel": "OK", "msj": "✅ Todo bajo control", "kg": 0})
    return res

def analizar_ia(blob_or_txt, modo, key):
    if not key: return "⚠️ Falta Key"
    genai.configure(api_key=key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        if modo == "foto":
            res = model.generate_content([f"Analiza salud aves.", {"mime_type": "image/jpeg", "data": blob_or_txt}])
        else:
            res = model.generate_content(blob_or_txt)
        return res.text
    except Exception as e: return f"Error: {e}"

# =================================================================
# 3. INTERFAZ PRINCIPAL
# =================================================================
inicializar_db()
st.sidebar.title("🧠 CORRAL TOTAL V71")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

with st.sidebar.expander("🔑 Configuración"):
    g_key = st.text_input("Gemini Key", value=st.session_state['gemini_key_mem'], type="password")
    if g_key: st.session_state['gemini_key_mem'] = g_key
    a_key = st.text_input("AEMET Key", value=st.session_state['aemet_key_mem'], type="password")
    if a_key: st.session_state['aemet_key_mem'] = a_key

# Carga masiva
lotes, gastos, produccion, ventas, bajas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("ventas"), cargar("bajas")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("📊 Control de Mando")
    temp = get_clima(st.session_state['aemet_key_mem'])
    stock = calcular_stock_pienso(gastos, lotes, temp)
    decision = piloto_automatico(stock, lotes, temp)

    if decision and decision["nivel"] == "CRITICO": st.toast("🚨 ¡SIN PIENSO!", icon="🚨")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔋 Pienso", f"{stock:.1f} kg")
    c2.metric("💰 Gastos", f"{gastos['cantidad'].sum():.1f} €")
    c3.metric("🌡️ Clima", f"{temp:.1f} °C")
    c4.metric("🥚 Hoy", f"{produccion[produccion['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()}")

    st.divider()
    st.subheader("🧠 Piloto Automático")
    if decision:
        col_ia1, col_ia2 = st.columns(2)
        with col_ia1:
            st.metric("⏳ Días restantes", f"{decision['dias_restantes']:.1f}")
            if decision["nivel"] == "CRITICO": st.error(decision["msj"])
            else: st.success(decision["msj"])
        with col_ia2:
            st.info(f"📦 Compra sugerida: {decision['kg']:.1f} kg")
            if st.button("🤖 Consejo IA"):
                st.write(analizar_ia(f"Experto granjero. Stock: {stock}kg, Temp: {temp}C. Dame 2 consejos.", "texto", st.session_state['gemini_key_mem']))

    st.divider()
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if not produccion.empty: st.plotly_chart(px.line(produccion, x='fecha', y='huevos', title="Puesta"), use_container_width=True)
    with col_g2:
        if not gastos.empty: st.plotly_chart(px.pie(gastos, values='cantidad', names='categoria', title="Gastos"), use_container_width=True)

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.title("📸 Análisis Visual")
    df_f = cargar("fotos")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']}: {r['especie']} {r['raza']}"):
            c_iz, c_de = st.columns([2,1])
            with c_iz:
                f_db = df_f[df_f['lote_id']==r['id']].tail(1)
                if not f_db.empty: st.image(f_db.iloc[0]['imagen'])
                subir = st.file_uploader("Subir foto", type=['jpg','png','jpeg'], key=f"u{r['id']}")
                if subir and st.button("Analizar", key=f"b{r['id']}"):
                    blob = subir.read()
                    res = analizar_ia(blob, "foto", st.session_state['gemini_key_mem'])
                    with get_conn() as conn: conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)", (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), res))
                    st.rerun()
            with c_de:
                if not f_db.empty: st.info(f_db.iloc[0]['nota'])

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Huevos")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color", ["Normal", "Verde", "Azul", "Codorniz"])
        h = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (f.strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    t1, t2 = st.tabs(["🛒 Ventas", "💀 Bajas"])
    with t1:
        with st.form("v"):
            tp = st.radio("Tipo", ["Venta", "Consumo"])
            l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("€", 0.0); kg = st.number_input("Kg Carne", 0.0)
            if st.form_submit_button("Vender"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades, kg_carne) VALUES (?,?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), tp, p, l, u, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("b"):
            lb = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            cb = st.number_input("Aves", 1); mot = st.text_input("Motivo")
            if st.form_submit_button("Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), lb, cb, mot)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Obras"])
        con = st.text_input("Concepto"); i = st.number_input("€", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Añadir"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?, 'General')", (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg)).connection.commit(); st.rerun()

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    with st.form("a"):
        e = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Huevo Verde", "Campero", "Blanco"])
        c = st.number_input("Nº", 1); ed = st.number_input("Edad", 0); pr = st.number_input("€/ud", 0.0)
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", (datetime.now().strftime("%d/%m/%Y"), e, rz, int(c), int(ed), pr)).connection.commit(); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Borrar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar Base de Datos", f, "corral.db")
    subir = st.file_uploader("Restaurar .db", type="db")
    if subir and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(subir.getbuffer())
        st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Plan 2026")
    plan = {"Blanco": 55, "Campero": 90}
    for r, d in plan.items():
        f = datetime(2026, 12, 24) - timedelta(days=d)
        st.warning(f"🍗 **{r}**: Comprar el **{f.strftime('%d/%m/%Y')}**")
