import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import google.generativeai as genai
import io

# --- 1. CONFIGURACIÓN MAESTRA ---
st.set_page_config(page_title="CORRAL OMNI V92.5", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        # Estructura V31.0 + Campos IA
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, cantidad REAL, ilos_pienso REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota_ia TEXT)")
    conn.commit()

# --- 2. LÓGICA DE FUSIÓN (CLIMA + IA) ---
def get_clima_cartagena(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        return float(requests.get(r["datos"], timeout=5).json()[-1]["ta"])
    except: return 22.0

def analizar_salud_ia(api_key, image_bytes):
    if not api_key: return "API Key no configurada."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        res = model.generate_content(["Analiza la salud de estas aves y detecta problemas: ", {"mime_type": "image/jpeg", "data": image_bytes}])
        return res.text
    except Exception as e: return f"Error IA: {str(e)}"

# --- 3. INTERFAZ ---
inicializar_db()
if 'api_g' not in st.session_state: st.session_state.api_g = ""
if 'api_a' not in st.session_state: st.session_state.api_a = ""

st.sidebar.title("🚜 CORRAL OMNI V92.5")
with st.sidebar.expander("🔑 LLAVES API"):
    st.session_state.api_g = st.text_input("Gemini API", value=st.session_state.api_g, type="password")
    st.session_state.api_a = st.text_input("AEMET API", value=st.session_state.api_a, type="password")

menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "🩺 IA & Crecimiento", "🥚 Producción", "💰 Ventas/Ahorro", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "💾 Backup", "📜 Histórico"])

lotes, gastos, ventas, prod, bajas = [pd.read_sql(f"SELECT * FROM {t}", get_conn()) if not pd.read_sql(f"SELECT * FROM {t}", get_conn()).empty else pd.DataFrame() for t in ["lotes", "gastos", "ventas", "produccion", "bajas"]]

temp = get_clima_cartagena(st.session_state.api_a)

# --- DASHBOARD TOTAL ---
if menu == "🏠 Dashboard":
    st.title(f"🏠 Panel Maestro (Cartagena: {temp}°C)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Inversión", f"{gastos['cantidad'].sum() if not gastos.empty else 0:.2f} €")
    c2.metric("📈 Caja Real", f"{ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0:.2f} €")
    c3.metric("🏠 Ahorro Casa", f"{ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0:.2f} €")
    
    # Cálculo Autonomía afectado por Clima
    pienso = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    aves_totales = lotes['cantidad'].sum() - (bajas['cantidad'].sum() if not bajas.empty else 0)
    consumo_base = aves_totales * 0.120 
    if temp > 30: consumo_base *= 1.15 # El calor sube el desperdicio/consumo
    autonomia = int(pienso / consumo_base) if consumo_base > 0 else 0
    c4.metric("⏳ Autonomía", f"{autonomia} días", delta="-15% por calor" if temp > 30 else None)

# --- IA & CRECIMIENTO (LO NUEVO FUSIONADO) ---
elif menu == "🩺 IA & Crecimiento":
    st.title("🩺 Análisis por IA y Madurez")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}", expanded=True):
            f_alta = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
            edad = (datetime.now() - f_alta).days + r["edad_inicial"]
            st.write(f"📅 Edad: {edad} días.")
            
            img = st.camera_input(f"Cámara Lote {r['id']}", key=f"cam_{r['id']}")
            if img:
                if st.button(f"Analizar Salud Lote {r['id']}"):
                    img_bytes = img.read()
                    analisis = analizar_salud_ia(st.session_state.api_g, img_bytes)
                    st.info(analisis)
                    get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen, nota_ia) VALUES (?,?,?,?)",
                                       (r['id'], datetime.now().strftime("%d/%m/%Y"), img_bytes, analisis)).connection.commit()

# --- VENTAS Y AHORRO CASA ---
elif menu == "💰 Ventas/Ahorro":
    st.title("💰 Salidas (Venta vs Consumo)")
    with st.form("v"):
        tipo = st.radio("Destino", ["Venta Cliente", "Consumo Propio"])
        u = st.number_input("Unidades", 1); p = st.number_input("Valor/Precio €", 0.0); k = st.number_input("Kg (ilos_finale)", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, ilos_finale, unidades) VALUES (?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), tipo, p, k, u)).connection.commit(); st.rerun()

# --- ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Mochuela", "Broiler", "Campero"])
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad Inicial (Días)", 0)
        if st.form_submit_button("Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, estado) VALUES (?,?,?,?,?,'Activo')",
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed))).connection.commit(); st.rerun()

# --- BACKUP ---
elif menu == "💾 Backup":
    st.title("💾 Copias Excel")
    arch = st.file_uploader("Subir Backup", type=["xlsx"])
    if arch and st.button("Restaurar"):
        data = pd.read_excel(arch, sheet_name=None)
        conn = get_conn()
        for t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
            if t in data:
                conn.execute(f"DELETE FROM {t}"); data[t].to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.success("OK"); st.rerun()
