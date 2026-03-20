import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import google.generativeai as genai

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL OMNI V70", layout="wide", page_icon="🧠")

# Estilos CSS Pro
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #f0f2f6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .css-1r6slb0 { background-color: #f8f9fa; border-radius: 15px; padding: 20px; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = "corral_maestro_pro.db"

if 'gemini_key_mem' not in st.session_state: st.session_state['gemini_key_mem'] = ""
if 'aemet_key_mem' not in st.session_state: st.session_state['aemet_key_mem'] = ""

# --- MOTOR DE DATOS ---
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

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
# 🧠 NÚCLEO DE INTELIGENCIA (IA DECISIONAL V70)
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
    f_clima = 1.12 if temp > 30 else (1.08 if temp < 10 else 1.0)
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

# 🔥 1. FUNCIÓN PILOTO AUTOMÁTICO
def piloto_automatico(stock, lotes, temp):
    if lotes.empty or stock <= 0: return None
    consumo_dia = 0
    for _, r in lotes.iterrows():
        base = CONFIG_ESPECIES.get(r['raza'], 0.1)
        consumo_dia += base * r['cantidad']
    
    if temp > 30: consumo_dia *= 1.12
    elif temp < 10: consumo_dia *= 1.08
    
    if consumo_dia == 0: return None
    dias_restantes = stock / consumo_dia
    
    dec = {"dias_restantes": dias_restantes, "consumo_dia": consumo_dia}
    if dias_restantes < 3:
        dec.update({"nivel": "CRITICO", "mensaje": "🚨 STOCK CRÍTICO: Menos de 3 días", "accion": "Comprar inmediatamente", "compra_kg": consumo_dia * 10})
    elif dias_restantes < 7:
        dec.update({"nivel": "ALERTA", "mensaje": "⚠️ STOCK BAJO", "accion": "Comprar esta semana", "compra_kg": consumo_dia * 14})
    else:
        dec.update({"nivel": "OK", "mensaje": "✅ STOCK CORRECTO", "accion": "Sin acción inmediata", "compra_kg": 0})
    return dec

def analizar_con_ia(prompt_or_blob, modo, key):
    if not key: return "⚠️ Falta API Key"
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        if modo == "foto":
            res = model.generate_content(["Analiza estas aves:", {"mime_type": "image/jpeg", "data": prompt_or_blob}])
        else:
            res = model.generate_content(prompt_or_blob)
        return res.text
    except Exception as e: return f"Error: {e}"

# =================================================================
# INTERFAZ
# =================================================================
inicializar_db()
st.sidebar.title("🧠 CORRAL V70")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

with st.sidebar.expander("🔑 Llaves API"):
    g_key = st.text_input("Gemini Key", value=st.session_state['gemini_key_mem'], type="password")
    if g_key: st.session_state['gemini_key_mem'] = g_key
    a_key = st.text_input("AEMET Key", value=st.session_state['aemet_key_mem'], type="password")
    if a_key: st.session_state['aemet_key_mem'] = a_key

lotes, gastos, produccion = cargar("lotes"), cargar("gastos"), cargar("produccion")

# --- 🏠 DASHBOARD (CON PILOTO AUTOMÁTICO) ---
if menu == "🏠 Dashboard":
    st.title("📊 Control Inteligente")
    temp = get_clima(st.session_state['aemet_key_mem'])
    stock = calcular_stock_pienso(gastos, lotes, temp)
    decision = piloto_automatico(stock, lotes, temp)

    # 🔥 Alerta visual superior
    if decision and decision["nivel"] == "CRITICO":
        st.toast("🚨 ¡COMPRA PIENSO YA!", icon="🚨")

    c1, c2, c3 = st.columns(3)
    c1.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c2.metric("🌡️ Temp Cartagena", f"{temp:.1f} °C")
    c3.metric("🥚 Producción Hoy", f"{produccion[produccion['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()} uds")

    # 🔥 2. PANEL PILOTO AUTOMÁTICO
    st.divider()
    st.subheader("🧠 Piloto Automático del Corral")
    if decision:
        col_ia1, col_ia2 = st.columns(2)
        with col_ia1:
            st.metric("⏳ Días restantes", f"{decision['dias_restantes']:.1f} días")
            if decision["nivel"] == "CRITICO": st.error(decision["mensaje"])
            elif decision["nivel"] == "ALERTA": st.warning(decision["mensaje"])
            else: st.success(decision["mensaje"])
        with col_ia2:
            st.metric("🍗 Consumo diario", f"{decision['consumo_dia']:.2f} kg")
            st.info(f"📌 **Acción:** {decision['accion']}\n\n📦 **Compra sugerida:** {decision['compra_kg']:.1f} kg")

        # 🔥 3. CONSEJO INTELIGENTE GEMINI
        if st.button("🤖 Pedir consejo experto a la IA"):
            with st.spinner("IA analizando situación..."):
                prompt = f"Actúa como experto granjero. Stock: {stock}kg, Temp: {temp}C, Días: {decision['dias_restantes']:.1f}. Da 3 consejos breves."
                consejo = analizar_con_ia(prompt, "texto", st.session_state['gemini_key_mem'])
                st.write(consejo)
    else:
        st.info("Registra lotes y compras de pienso para activar el Piloto Automático.")

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.header("📸 Seguimiento Visual")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']}: {r['especie']}"):
            f = st.file_uploader("Foto", type=['jpg','png'], key=f"f{r['id']}")
            if f and st.button("Analizar Salud", key=f"b{r['id']}"):
                blob = f.read()
                res = analizar_con_ia(blob, "foto", st.session_state['gemini_key_mem'])
                st.info(res)

# --- RESTO DE MÓDULOS (Simplificados para V70) ---
elif menu == "🐣 Alta Lotes":
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallina", "Pollo", "Codorniz"])
        rz = st.selectbox("Raza", list(CONFIG_ESPECIES.keys()))
        cant = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, estado) VALUES (?,?,?,?,0,'Activo')", (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant))).connection.commit(); st.rerun()

elif menu == "💸 Gastos":
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Otros"])
        kg = st.number_input("Kg Pienso", 0.0); eur = st.number_input("Euros €", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,'General')", (datetime.now().strftime("%d/%m/%Y"), cat, eur, kg)).connection.commit(); st.rerun()

elif menu == "🥚 Producción":
    with st.form("p"):
        h = st.number_input("Huevos", 1); col = st.selectbox("Color", ["Normal", "Verde"])
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO produccion (fecha, huevos, color_huevo) VALUES (?,?,?)", (datetime.now().strftime("%d/%m/%Y"), h, col)).connection.commit(); st.rerun()

elif menu == "💾 Copias":
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar Datos", f, "corral.db")
