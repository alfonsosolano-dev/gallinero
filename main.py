import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import requests
import numpy as np
import plotly.express as px
import google.generativeai as genai

st.set_page_config(page_title="CORRAL OMNI V80 - EMPRESA", layout="wide", page_icon="🚜")

DB_PATH = "corral_maestro_pro.db"

# =========================================================
# CONFIG IA Y MEMORIA
# =========================================================
if 'gemini_key' not in st.session_state:
    st.session_state['gemini_key'] = ""
if 'aemet_key' not in st.session_state:
    st.session_state['aemet_key'] = ""

# =========================================================
# BASE DE DATOS (NO ROMPE NADA)
# =========================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def cargar(t):
    try:
        return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except:
        return pd.DataFrame()

# =========================================================
# CLIMA CARTAGENA (AEMET)
# =========================================================
def get_clima(key):
    if not key:
        return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except:
        return 22.0

# =========================================================
# MODELO DE PUESTA (EMPRESA)
# =========================================================
CURVA = {
    "sem": [0,18,20,25,30,40,50,60,70,80,90],
    "p":   [0,0,0.15,0.85,0.94,0.92,0.88,0.80,0.70,0.60,0.40]
}

def puesta_modelo(lote, bajas, dias):
    try:
        f = datetime.strptime(lote["fecha"], "%d/%m/%Y")
        edad_dias = (datetime.now() - f).days + dias
        semanas = lote["edad_inicial_semanas"] + edad_dias/7
        
        prob = np.interp(semanas, CURVA["sem"], CURVA["p"])
        
        muertes = bajas[bajas['lote_id']==lote['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas = max(0, lote['cantidad'] - muertes)
        
        return prob * vivas
    except:
        return 0

# =========================================================
# IA DECISIONAL (CEREBRO CENTRAL)
# =========================================================
def cerebro_corral(lotes, produccion, gastos, bajas, temp):
    res = {}
    
    total_aves = lotes['cantidad'].sum() if not lotes.empty else 0
    huevos_hoy = produccion.tail(1)['huevos'].sum() if not produccion.empty else 0
    
    productividad = huevos_hoy / max(total_aves,1)
    
    # Diagnóstico producción
    if productividad < 0.4:
        res["estado"] = "CRITICO"
        res["msg"] = "🚨 Producción muy baja"
    elif productividad < 0.7:
        res["estado"] = "ALERTA"
        res["msg"] = "⚠️ Producción mejorable"
    else:
        res["estado"] = "OK"
        res["msg"] = "✅ Producción óptima"
    
    # Clima
    if temp > 30:
        res["clima"] = "🌡️ Estrés térmico"
    elif temp < 5:
        res["clima"] = "❄️ Frío extremo"
    else:
        res["clima"] = "🌤️ Condiciones normales"
    
    # Economía
    ingresos = produccion['huevos'].sum() * 0.20
    gastos_total = gastos['cantidad'].sum() if not gastos.empty else 0
    
    res["beneficio"] = ingresos - gastos_total
    
    return res

# =========================================================
# IA GEMINI
# =========================================================
def usar_ia(prompt, key):
    if not key:
        return "⚠️ Falta API Key"
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        return model.generate_content(prompt).text
    except Exception as e:
        return str(e)

# =========================================================
# APP
# =========================================================
st.sidebar.title("🚜 CORRAL OMNI V80")
menu = st.sidebar.radio("MENÚ", ["Dashboard","Predicción","IA Consejo","Histórico"])

with st.sidebar.expander("🔑 Configuración"):
    k1 = st.text_input("Gemini Key", type="password")
    if k1: st.session_state['gemini_key'] = k1
    k2 = st.text_input("AEMET Key", type="password")
    if k2: st.session_state['aemet_key'] = k2

lotes = cargar("lotes")
gastos = cargar("gastos")
produccion = cargar("produccion")
bajas = cargar("bajas")

temp = get_clima(st.session_state['aemet_key'])

# =========================================================
# DASHBOARD EMPRESA
# =========================================================
if menu == "Dashboard":
    st.title("📊 Panel Empresa Corral")
    
    analisis = cerebro_corral(lotes, produccion, gastos, bajas, temp)
    
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🌡️ Temp", f"{temp:.1f}°C")
    c2.metric("🥚 Hoy", int(produccion.tail(1)['huevos'].sum() if not produccion.empty else 0))
    c3.metric("🐔 Aves", int(lotes['cantidad'].sum() if not lotes.empty else 0))
    c4.metric("💰 Beneficio", f"{analisis['beneficio']:.2f} €")
    
    if analisis["estado"] == "CRITICO":
        st.error(analisis["msg"])
    elif analisis["estado"] == "ALERTA":
        st.warning(analisis["msg"])
    else:
        st.success(analisis["msg"])
    
    st.info(analisis["clima"])
    
    # gráficos
    if not produccion.empty:
        st.plotly_chart(px.line(produccion, x='fecha', y='huevos'), use_container_width=True)

# =========================================================
# PREDICCIÓN
# =========================================================
elif menu == "Predicción":
    st.title("🔮 Predicción Inteligente")
    
    dias = 30
    fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(dias)]
    
    valores = []
    for i in range(dias):
        total = sum([puesta_modelo(l, bajas, i) for _,l in lotes.iterrows()])
        real = produccion['huevos'].mean() if not produccion.empty else 0
        valores.append((total + real)/2)
    
    st.plotly_chart(px.line(x=fechas, y=valores, labels={'x':'Día','y':'Huevos'}), use_container_width=True)

# =========================================================
# IA CONSEJERA
# =========================================================
elif menu == "IA Consejo":
    st.title("🤖 IA Experta del Corral")
    
    q = st.text_area("Pregunta")
    
    if st.button("Consultar IA"):
        contexto = f"""
        Temp:{temp}
        Lotes:{len(lotes)}
        Producción:{produccion['huevos'].sum()}
        """
        r = usar_ia(contexto + q, st.session_state['gemini_key'])
        st.success(r)

# =========================================================
# HISTÓRICO
# =========================================================
elif menu == "Histórico":
    t = st.selectbox("Tabla", ["lotes","gastos","produccion","bajas"])
    df = cargar(t)
    st.dataframe(df)
