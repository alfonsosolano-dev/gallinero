import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import google.generativeai as genai

# --- IMPORTACIONES PARA GRÁFICOS E IA ---
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
st.set_page_config(page_title="CORRAL OMNI V68", layout="wide", page_icon="🚜")

# Estilo para métricas profesionales
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f2f6; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = "corral_maestro_pro.db"

# Sistema de persistencia para que no se borren las llaves
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
        tablas = [
            "lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)",
            "produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT)",
            "gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT)",
            "ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, unidades INTEGER, kg_carne REAL)",
            "bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)",
            "fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)"
        ]
        for t in tablas:
            c.execute(f"CREATE TABLE IF NOT EXISTS {t}")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# =================================================================
# 3. LÓGICA: CLIMA, INVENTARIO E IA "ANTIERRORES"
# =================================================================
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

def calcular_pienso_pro(gastos, lotes, temp):
    total_comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    f_clima = 1.12 if temp > 30 else 1.0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * f_clima
                for d in range(dias + 1):
                    edad = r["edad_inicial"] + d
                    f_edad = 0.4 if edad < 25 else (0.8 if edad < 50 else 1.0)
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, total_comprado - consumo)

def analizar_con_gemini_pro(blob, especie, key):
    if not key: return "⚠️ Falta API Key en el menú lateral."
    genai.configure(api_key=key)
    # Intentamos con varios nombres de modelos porque Google los cambia según la cuenta
    modelos_candidatos = ['gemini-1.5-flash', 'gemini-1.5-flash-8b', 'gemini-pro-vision']
    for m_name in modelos_candidatos:
        try:
            model = genai.GenerativeModel(m_name)
            res = model.generate_content([f"Como experto avicultor, analiza la salud de estas aves {especie}. Sé breve.", {"mime_type": "image/jpeg", "data": blob}])
            return res.text
        except: continue
    return "❌ Error: Google no responde con estos modelos. Revisa si tu API Key es 'Generative AI' y no de otra plataforma."

# =================================================================
# 4. INTERFAZ Y MÓDULOS (LA CATEDRAL DE 330 LÍNEAS)
# =================================================================
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V68")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

with st.sidebar.expander("🔑 Configuración de Llaves", expanded=False):
    g_key = st.text_input("Gemini Key", value=st.session_state['gemini_key_mem'], type="password")
    if g_key: st.session_state['gemini_key_mem'] = g_key
    a_key = st.text_input("AEMET Key", value=st.session_state['aemet_key_mem'], type="password")
    if a_key: st.session_state['aemet_key_mem'] = a_key

# Carga de datos global
lotes, gastos, produccion, ventas, bajas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("ventas"), cargar("bajas")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("📊 Panel de Gestión Integral")
    temp = get_clima(st.session_state['aemet_key_mem'])
    stock = calcular_pienso_pro(gastos, lotes, temp)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔋 Pienso Disponible", f"{stock:.1f} kg")
    c2.metric("💰 Inversión Total", f"{gastos['cantidad'].sum():.2f} €")
    c3.metric("🌡️ Temp (Cartagena)", f"{temp:.1f} °C")
    c4.metric("🥚 Huevos Hoy", f"{produccion[produccion['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()} uds")

    st.divider()
    col_izq, col_der = st.columns(2)
    with col_izq:
        if PX_OK and not produccion.empty:
            st.subheader("📈 Curva de Puesta")
            fig_p = px.line(produccion, x='fecha', y='huevos', color='color_huevo', markers=True, template="plotly_white")
            st.plotly_chart(fig_p, use_container_width=True)
    with col_der:
        if PX_OK and not gastos.empty:
            st.subheader("💸 Distribución de Costes")
            fig_g = px.pie(gastos, values='cantidad', names='categoria', hole=.4)
            st.plotly_chart(fig_g, use_container_width=True)

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.title("📸 Análisis Visual con IA")
    df_f = cargar("fotos")
    if lotes.empty: st.warning("Por favor, registra un lote de aves primero.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📷 Lote {r['id']}: {r['especie']} {r['raza']}", expanded=True):
                c_i, c_d = st.columns([2, 1])
                with c_i:
                    f_actual = df_f[df_f['lote_id']==r['id']].tail(1)
                    if not f_actual.empty: st.image(f_actual.iloc[0]['imagen'], use_container_width=True)
                    archivo = st.file_uploader("Subir nueva foto", type=['jpg','png','jpeg'], key=f"f{r['id']}")
                    if archivo and st.button("🚀 Analizar Salud", key=f"b{r['id']}"):
                        blob = archivo.read()
                        with st.spinner("Conectando con Gemini..."):
                            informe = analizar_con_gemini_pro(blob, r['especie'], st.session_state['gemini_key_mem'])
                            with get_conn() as conn:
                                conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                             (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), informe))
                            st.success("Análisis completado"); st.rerun()
                with c_d:
                    if not f_actual.empty:
                        st.markdown("### 🤖 Informe IA:")
                        st.info(f_actual.iloc[0]['nota'])

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Producción")
    with st.form("form_p"):
        f = st.date_input("Fecha de recogida")
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color del Huevo", ["Normal", "Verde", "Azul", "Codorniz"])
        cant = st.number_input("Cantidad de huevos", 1)
        if st.form_submit_button("Guardar Registro"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (f.strftime("%d/%m/%Y"), l, cant, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    st.title("💰 Salidas y Gestión de Bajas")
    t1, t2 = st.tabs(["🛒 Ventas / Consumo", "💀 Registro de Bajas"])
    with t1:
        with st.form("form_v"):
            tp = st.radio("Tipo de salida", ["Venta Directa", "Autoconsumo"])
            l = st.selectbox("De qué lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("Precio Total €", 0.0); kg = st.number_input("Kg de Carne (si aplica)", 0.0)
            if st.form_submit_button("Registrar Salida"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades, kg_carne) VALUES (?,?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), tp, p, l, u, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("form_b"):
            lb = st.selectbox("Lote afectado", lotes['id'].tolist() if not lotes.empty else [])
            cb = st.number_input("Nº de aves perdidas", 1); mot = st.text_input("Motivo (Enfermedad, Depredador...)")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), lb, cb, mot)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Control de Costes")
    with st.form("form_g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Compra Aves", "Instalaciones"])
        dest = st.selectbox("Para quién", ["General", "Gallinas", "Pollos", "Codornices"])
        con = st.text_input("Concepto (Ej: Saco 25kg Puesta)"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Añadir Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Entrada de Nuevos Lotes")
    with st.form("form_alta"):
        e = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza/Línea", ["Roja", "Blanca", "Huevo Verde", "Campero", "Broiler"])
        c = st.number_input("Nº aves", 1); ed = st.number_input("Edad (días)", 0); pr = st.number_input("Precio unidad €", 0.0)
        if st.form_submit_button("Activar Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (datetime.now().strftime("%d/%m/%Y"), e, rz, int(c), int(ed), pr)).connection.commit(); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    st.info("Fechas límite para comprar pollos y que lleguen perfectos a la cena del 24/12/2026.")
    tiempos = {"Blanco Engorde": 55, "Campero": 90}
    for rz, d in tiempos.items():
        f_limite = datetime(2026, 12, 24) - timedelta(days=d)
        st.warning(f"🍗 **{rz}**: Compra el lote el día **{f_limite.strftime('%d/%m/%Y')}**")

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Copias de Seguridad")
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar Base de Datos", f, "corral_master.db")
    sub = st.file_uploader("Subir copia para restaurar", type="db")
    if sub and st.button("🚀 Restaurar Ahora"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.success("Base de datos restaurada con éxito."); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Ver tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar(t); st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
