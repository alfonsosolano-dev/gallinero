import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np
import google.generativeai as genai

# --- IMPORTACIONES PROTEGIDAS PARA GRÁFICOS E IA ---
try:
    from sklearn.linear_model import LinearRegression
    SK_OK = True
except:
    SK_OK = False

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PX_OK = True
except:
    PX_OK = False

# =================================================================
# 1. CONFIGURACIÓN, MEMORIA Y ESTILOS
# =================================================================
st.set_page_config(page_title="CORRAL OMNI V67", layout="wide", page_icon="🚜")

# Estilo para que las métricas resalten
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); border: 1px solid #efefef; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = "corral_maestro_pro.db"

# Persistencia de llaves para evitar que se borren al subir fotos
if 'gemini_key_mem' not in st.session_state:
    st.session_state['gemini_key_mem'] = st.secrets.get("GEMINI_KEY", "")
if 'aemet_key_mem' not in st.session_state:
    st.session_state['aemet_key_mem'] = st.secrets.get("AEMET_KEY", "")

# =================================================================
# 2. MOTOR DE BASE DE DATOS
# =================================================================
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
             lote_id INTEGER, unidades INTEGER, kg_carne REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS bajas 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS fotos 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)""")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# =================================================================
# 3. LÓGICA DE NEGOCIO (PIENSO, CLIMA E IA)
# =================================================================
CONFIG_ESPECIES = {
    "Gallina Roja": 0.110, "Gallina Blanca": 0.105, "Gallina Huevo Verde": 0.115, 
    "Codorniz": 0.025, "Pollo Blanco": 0.180, "Pollo Campero": 0.140
}

def get_clima(api_key):
    if not api_key: return 21.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        return float(requests.get(r["datos"], timeout=5).json()[-1]["ta"])
    except: return 21.0

def calcular_pienso_real(gastos, lotes, temp):
    total_comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo_total = 0
    f_clima = 1.15 if temp > 30 else 1.0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * f_clima
                for d in range(dias + 1):
                    f_edad = 0.3 if (r["edad_inicial"] + d) < 20 else 1.0
                    consumo_total += base * f_edad * r['cantidad']
            except: continue
    return max(0, total_comprado - consumo_total)

def analizar_aves_ia(blob, especie, key):
    if not key: return "⚠️ Falta API Key"
    genai.configure(api_key=key)
    for m in ['gemini-1.5-flash-latest', 'gemini-1.5-flash']:
        try:
            model = genai.GenerativeModel(m)
            res = model.generate_content([f"Analiza aves {especie}. Salud y plumaje.", {"mime_type": "image/jpeg", "data": blob}])
            return res.text
        except: continue
    return "❌ Error: Modelos no disponibles."

# =================================================================
# 4. INTERFAZ Y NAVEGACIÓN (EL MENÚ COMPLETO)
# =================================================================
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V67")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

# Configuración de llaves con persistencia
with st.sidebar.expander("🔑 Configuración de Llaves", expanded=False):
    g_key = st.text_input("Gemini Key", value=st.session_state['gemini_key_mem'], type="password")
    if g_key: st.session_state['gemini_key_mem'] = g_key
    a_key = st.text_input("AEMET Key", value=st.session_state['aemet_key_mem'], type="password")
    if a_key: st.session_state['aemet_key_mem'] = a_key

# Carga masiva de datos
lotes, gastos, produccion, ventas, bajas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("ventas"), cargar("bajas")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("📊 Panel de Control General")
    temp = get_clima(st.session_state['aemet_key_mem'])
    stock = calcular_pienso_real(gastos, lotes, temp)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔋 Pienso", f"{stock:.1f} kg")
    c2.metric("💰 Inversión", f"{gastos['cantidad'].sum():.1f} €")
    c3.metric("🌡️ Temp", f"{temp:.1f} °C")
    c4.metric("🥚 Hoy", f"{produccion[produccion['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()}")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        if PX_OK and not produccion.empty:
            fig_p = px.line(produccion, x='fecha', y='huevos', color='color_huevo', title="Producción de Huevos")
            st.plotly_chart(fig_p, use_container_width=True)
    with col_b:
        if PX_OK and not gastos.empty:
            fig_g = px.pie(gastos, values='cantidad', names='categoria', title="Distribución de Gastos")
            st.plotly_chart(fig_g, use_container_width=True)

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.title("📈 Seguimiento Visual Gemini")
    df_fotos = cargar("fotos")
    if lotes.empty: st.warning("Crea un lote primero.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📸 {r['especie']} {r['raza']} (Lote {r['id']})", expanded=True):
                col_i, col_d = st.columns([2, 1])
                with col_i:
                    f_db = df_fotos[df_fotos['lote_id']==r['id']].tail(1)
                    if not f_db.empty: st.image(f_db.iloc[0]['imagen'])
                    sub = st.file_uploader("Nueva foto", type=['jpg','png','jpeg'], key=f"f{r['id']}")
                    if sub and st.button("Analizar con IA", key=f"b{r['id']}"):
                        blob = sub.read()
                        res = analizar_aves_ia(blob, r['especie'], st.session_state['gemini_key_mem'])
                        with get_conn() as conn:
                            conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                         (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), res))
                        st.success("Análisis guardado"); st.rerun()
                with col_d:
                    if not f_db.empty: st.info(f_db.iloc[0]['nota'])

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Huevos")
    with st.form("f_prod"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color", ["Normal", "Verde", "Azul", "Codorniz"])
        h = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (f.strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    st.title("💰 Salidas del Corral")
    t1, t2 = st.tabs(["Ventas / Consumo", "Bajas (Muertes)"])
    with t1:
        with st.form("f_ven"):
            tp = st.radio("Tipo", ["Venta", "Consumo"])
            l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("€", 0.0); kg = st.number_input("Kg Carne", 0.0)
            if st.form_submit_button("Registrar Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades, kg_carne) VALUES (?,?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), tp, p, l, u, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("f_baj"):
            lb = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            cb = st.number_input("Cantidad", 1); m = st.text_input("Motivo")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), lb, cb, m)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Registro de Gastos")
    with st.form("f_gas"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Infraestructura"])
        dest = st.selectbox("Destino", ["General", "Gallinas", "Pollos", "Codornices"])
        con = st.text_input("Concepto"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Nuevo Lote de Aves")
    with st.form("f_alta"):
        esp = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Huevo Verde", "Campero", "Blanco"])
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad Inicial", 0); pr = st.number_input("Precio ud", 0.0)
        if st.form_submit_button("Crear Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Gestión de Datos")
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar .db", f, "corral_master.db")
    sub = st.file_uploader("Restaurar archivo .db", type="db")
    if sub and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.success("Restaurado"); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar Registro"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Planificación Navidad 2026")
    plan = {"Blanco Engorde": 55, "Campero": 90}
    for rz, d in plan.items():
        f_c = datetime(2026, 12, 20) - timedelta(days=d)
        st.warning(f"🍗 **{rz}**: Comprar el lote el día **{f_c.strftime('%d/%m/%Y')}**")
