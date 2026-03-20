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
st.set_page_config(page_title="CORRAL OMNI V76 PRO", layout="wide", page_icon="🚜")

# Estilos Pro
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #f0f2f6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    [data-testid="stExpander"] { border: 1px solid #f0f2f6; border-radius: 10px; background-color: #fcfcfc; margin-bottom: 10px; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = "corral_maestro_pro.db"

# --- DATOS MAESTROS (RAZAS Y ESPECIES) ---
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul", "Negra", "Extremeña", "Pita Pinta", "Ayam Cemani", "Brahma", "Sedosa"],
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

# Consumo de pienso base por especie (kg/día)
CONSUMO_BASE = {
    "Gallina Roja (Lohman)": 0.115, "Gallina Blanca (Leghorn)": 0.110, "Gallina Huevo Verde": 0.120,
    "Pollo Blanco Engorde (Broiler)": 0.180, "Pollo Campero / Rural": 0.150, "Codorniz Japónica (Huevo)": 0.025
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
# 2. CEREBRO IA Y LÓGICA (PILOTO AUTOMÁTICO + CLIMA)
# =================================================================
def get_clima(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

def calcular_pienso_restante(gastos, lotes, temp):
    total_comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo_acumulado = 0
    f_clima = 1.12 if temp > 30 else (1.08 if temp < 10 else 1.0)
    
    if not lotes.empty:
        for _, r in lotes.iterrows():
            f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
            dias_transcurridos = (datetime.now() - f_ini).days
            base = CONSUMO_BASE.get(f"{r['especie']} {r['raza']}", 0.110) * f_clima
            for d in range(dias_transcurridos + 1):
                f_edad = 0.5 if (r["edad_inicial_semanas"] * 7 + d) < 40 else 1.0
                consumo_acumulado += base * f_edad * r['cantidad']
    return max(0, total_comprado - consumo_acumulado)

def piloto_automatico(stock, lotes, temp):
    if lotes.empty or stock <= 0: return None
    consumo_dia = 0
    for _, r in lotes.iterrows():
        base = CONSUMO_BASE.get(f"{r['especie']} {r['raza']}", 0.110)
        consumo_dia += base * r['cantidad']
    
    if temp > 30: consumo_dia *= 1.12
    elif temp < 10: consumo_dia *= 1.08
    
    dias = stock / consumo_dia
    dec = {"dias": dias, "consumo": consumo_dia}
    if dias < 3: dec.update({"nivel": "CRITICO", "msj": "🚨 COMPRA PIENSO YA", "compra": consumo_dia * 15})
    elif dias < 7: dec.update({"nivel": "ALERTA", "msj": "⚠️ Stock bajo", "compra": consumo_dia * 20})
    else: dec.update({"nivel": "OK", "msj": "✅ Todo correcto", "compra": 0})
    return dec

def analizar_ia_robusta(blob_or_txt, modo, key):
    if not key: return "⚠️ Falta API Key."
    try:
        genai.configure(api_key=key)
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        model_name = next((m for m in ['models/gemini-1.5-flash', 'models/gemini-pro'] if m in available), available[0])
        model = genai.GenerativeModel(model_name)
        if modo == "foto":
            res = model.generate_content([f"Veterinario avícola: analiza salud y plumaje.", {"mime_type": "image/jpeg", "data": blob_or_txt}])
        else: res = model.generate_content(blob_or_txt)
        return res.text
    except Exception as e: return f"Error IA: {e}"

# =================================================================
# 3. INTERFAZ DE USUARIO
# =================================================================
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V76")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "🔮 Predicción Puesta", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

with st.sidebar.expander("🔑 Configuración de Llaves"):
    g_key = st.text_input("Gemini Key", value=st.session_state['gemini_key_mem'], type="password")
    if g_key: st.session_state['gemini_key_mem'] = g_key
    a_key = st.text_input("AEMET Key", value=st.session_state['aemet_key_mem'], type="password")
    if a_key: st.session_state['aemet_key_mem'] = a_key

lotes, gastos, produccion, ventas, bajas = cargar("lotes"), cargar("gastos"), cargar("produccion"), cargar("ventas"), cargar("bajas")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("📊 Control de Mando")
    temp = get_clima(st.session_state['aemet_key_mem'])
    stock = calcular_pienso_restante(gastos, lotes, temp)
    decision = piloto_automatico(stock, lotes, temp)

    # Alertas Críticas
    if decision and decision["nivel"] == "CRITICO": st.error(f"🚨 {decision['msj']} - Quedan {decision['dias']:.1f} días")

    c1, c2, c3, c4 = st.columns(4)
    balance = ventas['cantidad'].sum() - gastos['cantidad'].sum()
    c1.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c2.metric("💰 Balance Neto", f"{balance:.2f} €")
    c3.metric("🌡️ Temp (Cartagena)", f"{temp:.1f} °C")
    c4.metric("🥚 Hoy", f"{produccion[produccion['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()}")

    st.divider()
    # Panel Piloto Automático
    if decision:
        with st.expander("🧠 Inteligencia Decisional", expanded=True):
            col_ia1, col_ia2 = st.columns(2)
            col_ia1.write(f"**Estado:** {decision['msj']}")
            col_ia1.write(f"**Consumo Diario:** {decision['consumo']:.2f} kg")
            col_ia2.write(f"**Autonomía:** {decision['dias']:.1f} días")
            if decision['compra'] > 0: col_ia2.info(f"📦 Compra recomendada: {decision['compra']:.1f} kg")
            if st.button("🤖 Pedir Consejo a Gemini"):
                st.write(analizar_ia_robusta(f"Grano: {stock}kg, Aves: {len(lotes)}, Temp: {temp}C. Dame 2 consejos.", "texto", st.session_state['gemini_key_mem']))

    st.divider()
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if not produccion.empty: st.plotly_chart(px.line(produccion, x='fecha', y='huevos', title="Tendencia de Puesta"), use_container_width=True)
    with col_g2:
        if not gastos.empty: st.plotly_chart(px.pie(gastos, values='cantidad', names='categoria', hole=.3, title="Gastos"), use_container_width=True)

# --- 🔮 PREDICCIÓN PUESTA ---
elif menu == "🔮 Predicción Puesta":
    st.title("🔮 Predicción Biológica de Huevos")
    if lotes.empty: st.warning("No hay lotes para predecir.")
    else:
        # Lógica de predicción 30 días
        df_pred = pd.DataFrame([{"Día": (datetime.now() + timedelta(days=i)).strftime("%d/%m"), 
                                 "Huevos": sum([np.interp(l['edad_inicial_semanas'] + (((datetime.now() - datetime.strptime(l['fecha'], "%d/%m/%Y")).days + i)/7), CURVA_PUESTA['semana'], CURVA_PUESTA['porcentaje']) * l['cantidad'] for _, l in lotes.iterrows() if l['especie'] == "Gallina"])} 
                                for i in range(30)])
        st.plotly_chart(px.area(df_pred, x="Día", y="Huevos", title="Capacidad de Producción Teórica"), use_container_width=True)
        st.info("Nota: La predicción se basa en la edad de las gallinas y la curva estándar de puesta.")

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.title("📸 Diagnóstico por Imagen")
    df_f = cargar("fotos")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}", expanded=True):
            subir = st.file_uploader("Foto de hoy", type=['jpg','png','jpeg'], key=f"u{r['id']}")
            if subir and st.button("🚀 Analizar con IA", key=f"b{r['id']}"):
                blob = subir.read()
                res = analizar_ia_robusta(blob, "foto", st.session_state['gemini_key_mem'])
                with get_conn() as conn: conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)", (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), res))
                st.rerun()
            f_rec = df_f[df_f['lote_id']==r['id']].tail(1)
            if not f_rec.empty:
                st.image(f_rec.iloc[0]['imagen'], width=300)
                st.info(f_rec.iloc[0]['nota'])

# --- 🐣 ALTA LOTES (DONDE SE ELIGEN LAS CLASES) ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Compra / Alta de Aves")
    with st.form("alta"):
        c1, c2 = st.columns(2)
        esp = c1.selectbox("Especie", list(ESPECIES_FULL.keys()))
        rz = c2.selectbox("Raza / Clase", ESPECIES_FULL[esp])
        cant = st.number_input("Nº Aves", 1)
        ed = st.number_input("Edad (Semanas)", 0)
        pr = st.number_input("Precio/ud €", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Registrar Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    t1, t2 = st.tabs(["🛒 Ventas", "💀 Bajas"])
    with t1:
        with st.form("v"):
            l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("Total Recibido €", 0.0)
            if st.form_submit_button("Vender"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades, kg_carne) VALUES (?, 'Venta', ?, ?, ?, 0)", (datetime.now().strftime("%d/%m/%Y"), p, l, u)).connection.commit(); st.rerun()
    with t2:
        with st.form("b"):
            l = st.selectbox("Lote afectado", lotes['id'].tolist() if not lotes.empty else [])
            c = st.number_input("Aves perdidas", 1); m = st.text_input("Causa")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), l, c, m)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Obras", "Varios"])
        con = st.text_input("Concepto"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?, 'General')", (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg)).connection.commit(); st.rerun()

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro Diario")
    with st.form("p"):
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos", 1); c = st.selectbox("Color", ["Marrón", "Blanco", "Verde", "Azul"])
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), l, h, c)).connection.commit(); st.rerun()

# --- 📜 HISTÓRICO Y COPIAS ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas"])
    st.dataframe(cargar(t), use_container_width=True)
    idx = st.number_input("Borrar ID", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

elif menu == "💾 Copias":
    with open(DB_PATH, "rb") as f: st.download_button("📥 Bajar Backup .db", f, "corral.db")
    subir = st.file_uploader("Restaurar .db", type="db")
    if subir and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(subir.getbuffer())
        st.rerun()
