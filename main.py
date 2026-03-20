import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import plotly.express as px
import google.generativeai as genai
import io

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="CORRAL OMNI V91 - IA TOTAL", layout="wide", page_icon="🤖")

DB_PATH = "corral_maestro_pro.db"

# --- 2. MOTOR DE DATOS (Fiel a tu V31.0) ---
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        tablas = {
            "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
            "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
            "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL",
            "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
            "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT",
            "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
        }
        for n, e in tablas.items(): c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- 3. CONEXIÓN CLIMA (Cartagena) ---
def get_clima(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

# --- 4. INTERFAZ Y NAVEGACIÓN ---
inicializar_db()
lotes, gastos, ventas, bajas, produccion = cargar("lotes"), cargar("gastos"), cargar("ventas"), cargar("bajas"), cargar("produccion")

# Guardar llaves en la sesión para que no se borren
if 'api_gemini' not in st.session_state: st.session_state.api_gemini = ""
if 'api_aemet' not in st.session_state: st.session_state.api_aemet = ""

st.sidebar.title("🤖 CORRAL IA V91")
with st.sidebar.expander("🔑 Configuración de IA y Clima"):
    st.session_state.api_gemini = st.text_input("Gemini API Key", value=st.session_state.api_gemini, type="password")
    st.session_state.api_aemet = st.text_input("AEMET API Key", value=st.session_state.api_aemet, type="password")

menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "🩺 Salud IA (Cámara)", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "💾 Backup/Copias", "📜 Histórico"])

temp_actual = get_clima(st.session_state.api_aemet)

# --- VISTA DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control Inteligente")
    inv = gastos['cantidad'].sum() if not gastos.empty else 0
    caja = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌡️ Temp (Cartagena)", f"{temp_actual}°C")
    c2.metric("📈 Caja Real", f"{caja:.2f} €")
    c3.metric("🏠 Ahorro Casa", f"{ahorro:.2f} €")
    c4.metric("💰 Inversión", f"{inv:.2f} €")

    if temp_actual > 30:
        st.warning("⚠️ ALERTA CALOR: Las gallinas necesitan más agua y sombra ahora mismo.")

# --- VISTA SALUD IA (Fusión de la cámara con Gemini) ---
elif menu == "🩺 Salud IA (Cámara)":
    st.title("🩺 Diagnóstico Veterinario IA")
    if not st.session_state.api_gemini:
        st.error("Introduce la API Key de Gemini en el menú lateral.")
    else:
        img_file = st.camera_input("Haz una foto a tus aves o al gallinero")
        if img_file:
            if st.button("🔍 Analizar con Gemini"):
                with st.spinner("La IA está analizando la imagen..."):
                    genai.configure(api_key=st.session_state.api_gemini)
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    img_data = img_file.read()
                    response = model.generate_content([
                        "Analiza esta imagen de aves de corral. Busca signos de enfermedad, estrés, picaje o falta de higiene. Dame consejos prácticos de manejo.",
                        {"mime_type": "image/jpeg", "data": img_data}
                    ])
                    st.info(response.text)
                    # Guardar en la DB
                    get_conn().execute("INSERT INTO fotos (fecha, imagen, nota) VALUES (?,?,?)",
                                       (datetime.now().strftime("%d/%m/%Y"), img_data, "Análisis IA")).connection.commit()

# --- VISTA CRECIMIENTO (Lógica de edad y peso) ---
elif menu == "📈 Crecimiento":
    st.title("📈 Seguimiento de Lotes")
    for _, r in lotes.iterrows():
        f_alta = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
        edad = (datetime.now() - f_alta).days + r["edad_inicial"]
        with st.expander(f"Lote {r['id']} - {r['raza']} (Edad: {edad} días)"):
            st.write(f"📊 Cantidad actual: {r['cantidad']} aves")
            if "Pollo" in r['especie']:
                peso_est = (edad * 0.045) # Estimación simple 45g/día
                st.metric("Peso Estimado", f"{peso_est:.2f} kg/ave")

# --- VISTA NAVIDAD (Recuperado de tu V31) ---
elif menu == "🎄 Navidad":
    st.title("🎄 Planificador Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    madurez = {"Broiler": 55, "Campero": 90, "Codorniz": 45}
    for raza, dias in madurez.items():
        f_compra = f_obj - timedelta(days=dias)
        st.success(f"📌 **{raza}**: Comprar el **{f_compra.strftime('%d/%m/%Y')}**")

# --- VISTA BACKUP (Recuperado de tu V31) ---
elif menu == "💾 Backup/Copias":
    st.title("💾 Copias de Seguridad")
    arch = st.file_uploader("Restaurar desde Excel", type=["xlsx"])
    if arch and st.button("🚀 Restaurar"):
        data = pd.read_excel(arch, sheet_name=None)
        conn = get_conn()
        for t, df in data.items():
            if t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
                conn.execute(f"DELETE FROM {t}")
                df.to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.success("Datos restaurados."); st.rerun()

# --- VISTA ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    with st.form("f_a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Mochuela", "Blanco Engorde", "Campero"])
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad", 1); ed = c2.number_input("Edad inicial (Días)", 0); pr = c3.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')",
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- OTRAS VISTAS BÁSICAS (Ventas, Gastos, Producción) ---
elif menu == "💰 Ventas":
    with st.form("f_v"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        u = st.number_input("Unidades", 1); p = st.number_input("Total €", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, unidades) VALUES (?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), tipo, p, u)).connection.commit(); st.rerun()

elif menu == "💸 Gastos":
    with st.form("f_g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Otros"])
        imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kg (ilos_pienso)", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, cantidad, ilos_pienso) VALUES (?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cat, imp, kg)).connection.commit(); st.rerun()

elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        id_del = st.number_input("ID a borrar", int(df['id'].min()))
        if st.button("Borrar"): get_conn().execute(f"DELETE FROM {t} WHERE id={id_del}").connection.commit(); st.rerun()
