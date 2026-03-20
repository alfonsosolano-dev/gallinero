import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np
import base64
import google.generativeai as genai

# --- PROTECCIÓN DE LIBRERÍAS (Evita pantallas rojas) ---
try:
    from sklearn.linear_model import LinearRegression
    SK_OK = True
except:
    SK_OK = False

try:
    import plotly.express as px
    PX_OK = True
except:
    PX_OK = False

# --- CONFIGURACIÓN DE LLAVES (SECRETS) ---
# Se leen de la configuración de Streamlit Cloud si están puestas
GEMINI_KEY = st.secrets.get("GEMINI_KEY", "")
AEMET_KEY = st.secrets.get("AEMET_KEY", "")

# --- INICIALIZACIÓN DE LA APP ---
st.set_page_config(page_title="CORRAL OMNI V61", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS lotes 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
             cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS produccion 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS gastos 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, 
             cantidad REAL, ilos_pienso REAL, destinado_a TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS ventas 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, 
             lote_id INTEGER, unidades INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS bajas 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS fotos 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)""")
    conn.close()

# --- MOTOR DE INTELIGENCIA Y CONSUMO ---
CONFIG_ESPECIES = {
    "Gallina Roja": 0.110, "Gallina Blanca": 0.105, "Gallina Huevo Verde": 0.115, 
    "Codorniz": 0.025, "Pollo Blanco": 0.180, "Pollo Campero": 0.140
}

def get_clima(api_key):
    if not api_key: return 20.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        return float(requests.get(r["datos"], timeout=5).json()[-1]["ta"])
    except: return 20.0

def calcular_pienso_real(gastos, lotes, t_actual):
    comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    f_clima = 1.12 if t_actual > 30 else 1.0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * 0.88 * f_clima
                for d in range(dias + 1):
                    f_edad = 0.4 if (r["edad_inicial"] + d) < 25 else 1.0
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, comprado - consumo)

# --- INTERFAZ LATERAL ---
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V61")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if not GEMINI_KEY: GEMINI_KEY = st.sidebar.text_input("🔑 Gemini Key", type="password")
if not AEMET_KEY: AEMET_KEY = st.sidebar.text_input("🌡️ AEMET Key", type="password")

# Carga de datos
def cargar(t): return pd.read_sql(f"SELECT * FROM {t}", get_conn())
lotes, gastos, produccion, ventas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("ventas")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🏠 Control de Granja")
    temp = get_clima(AEMET_KEY)
    stock = calcular_pienso_real(gastos, lotes, temp)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💸 Inversión Total", f"{gastos['cantidad'].sum() if not gastos.empty else 0:.2f} €")
    c2.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c3.metric("🌡️ Temp (Cartagena)", f"{temp:.1f} °C")

    if SK_OK and not gastos.empty and len(gastos[gastos['ilos_pienso']>0]) > 2:
        st.info("🔮 IA Predictiva activa analizando consumos...")

    if PX_OK and not produccion.empty:
        fig = px.bar(produccion, x='fecha', y='huevos', color='color_huevo', title="Puesta por Color/Especie")
        st.plotly_chart(fig, use_container_width=True)

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.header("📈 Análisis Visual con IA")
    df_f = cargar("fotos")
    if lotes.empty: st.warning("Crea un lote primero.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📸 {r['especie']} {r['raza']} (ID: {r['id']})", expanded=True):
                col_i, col_d = st.columns([2, 1])
                with col_i:
                    f_db = df_f[df_f['lote_id']==r['id']].tail(1)
                    if not f_db.empty: st.image(f_db.iloc[0]['imagen'])
                    sub = st.file_uploader("Nueva foto", type=['jpg','png','jpeg'], key=f"f{r['id']}")
                    if sub and st.button("💾 Analizar", key=f"b{r['id']}"):
                        blob = sub.read()
                        genai.configure(api_key=GEMINI_KEY)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        res = model.generate_content([f"Analiza estas aves {r['especie']}. Evalúa salud y crecimiento.", {"mime_type": "image/jpeg", "data": blob}])
                        conn = get_conn()
                        conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                     (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), res.text))
                        conn.commit(); st.rerun()
                with col_d:
                    if not f_db.empty: st.info(f_db.iloc[0]['nota'])

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Huevos")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color/Tipo", ["Normal", "Verde", "Azul", "Codorniz"])
        h = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (f.strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    st.title("💰 Salidas y Bajas")
    t1, t2 = st.tabs(["Ventas", "Bajas"])
    with t1:
        with st.form("v"):
            tipo = st.radio("Tipo", ["Venta", "Consumo"])
            l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("Euros €", 0.0)
            if st.form_submit_button("Vender"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades) VALUES (?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), tipo, p, l, u)).connection.commit(); st.rerun()
    with t2:
        with st.form("b"):
            l_b = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            c_b = st.number_input("Cantidad", 1); m = st.text_input("Motivo")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), l_b, c_b, m)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Infraestructura"])
        dest = st.selectbox("Destinatario", ["Gallinas", "Pollos", "Codornices", "General"])
        con = st.text_input("Concepto"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (f.strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    m = {"Blanco Engorde": 55, "Campero": 90}
    for rz, d in m.items():
        f_c = datetime(2026, 12, 20) - timedelta(days=d)
        st.warning(f"🍗 **{rz}**: Comprar el lote el **{f_c.strftime('%d/%m/%Y')}**")

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Registrar Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Huevo Verde", "Campero", "Blanco"])
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad (días)", 0); p = st.number_input("Precio ud", 0.0)
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), p)).connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Copias de Seguridad")
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar .db", f, "corral_master.db")
    sub = st.file_uploader("Subir .db", type="db")
    if sub and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.success("Hecho."); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
