import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.express as px
import google.generativeai as genai

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL OMNI V87", layout="wide", page_icon="🐔")

DB_PATH = "corral_maestro_pro.db"

# --- DICCIONARIO MAESTRO ---
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul"],
    "Pollo (Carne)": ["Broiler", "Campero", "Capón"],
    "Codorniz": ["Japónica (Huevo)", "Coreana (Carne)"]
}

# --- MOTOR DB CON REPARACIÓN AUTOMÁTICA ---
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial_semanas INTEGER, precio_ud REAL, estado TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, cantidad REAL, kilos_pienso REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, kg_vendidos REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER)")
        
        # REPARACIÓN DE COLUMNAS (Para evitar el KeyError de tus fotos)
        cols = [i[1] for i in c.execute("PRAGMA table_info(lotes)").fetchall()]
        if 'edad_inicial_semanas' not in cols: c.execute("ALTER TABLE lotes ADD COLUMN edad_inicial_semanas INTEGER DEFAULT 0")
        if 'especie' not in cols: c.execute("ALTER TABLE lotes ADD COLUMN especie TEXT DEFAULT 'Gallina'")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- LÓGICA DE CONSUMO Y AUTONOMÍA (Lo que faltaba) ---
def calcular_autonomia(lotes, gastos, bajas):
    pienso_comprado = gastos['kilos_pienso'].sum() if not gastos.empty else 0
    if lotes.empty: return pienso_comprado, 0, 0
    
    consumo_diario_total = 0
    for _, l in lotes.iterrows():
        muertes = bajas[bajas['lote_id']==l['id']]['cantidad'].sum() if not bajas.empty else 0
        vivos = max(0, l['cantidad'] - muertes)
        # Estimación: Gallina 115g, Pollo/Codorniz proporcional a peso
        consumo_diario_total += (0.120 * vivos) if "Gallina" in l['especie'] else (0.150 * vivos)
    
    # Aquí calculamos lo consumido hasta hoy (simplificado)
    pienso_actual = max(0, pienso_comprado - (consumo_diario_total * 7)) # Ejemplo: resta última semana
    dias_autonomia = int(pienso_actual / consumo_diario_total) if consumo_diario_total > 0 else 0
    return pienso_actual, dias_autonomia, consumo_diario_total

# --- INTERFAZ ---
inicializar_db()
lotes, gastos, ventas, bajas, produccion = cargar("lotes"), cargar("gastos"), cargar("ventas"), cargar("bajas"), cargar("produccion")

st.sidebar.title("🐔 CORRAL V87")
menu = st.sidebar.radio("MENÚ", ["📊 Dashboard", "🔮 Predicción Pro", "🐣 Alta Lotes", "💰 Gastos/Ventas", "🩺 Salud IA", "📜 Histórico"])

# --- DASHBOARD (COMO EN TU IMAGEN) ---
if menu == "📊 Dashboard":
    st.title("📊 Control de Gestión")
    p_real, dias, cons_dia = calcular_autonomia(lotes, gastos, bajas)
    inv = gastos['cantidad'].sum() if not gastos.empty else 0
    rev = ventas['cantidad'].sum() if not ventas.empty else 0
    
    # LOS 4 CONTADORES DE TU IMAGEN
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Inversión Total", f"{inv:.2f} €")
    c2.metric("📈 Beneficio Real", f"{(rev - inv):.2f} €", f"+{rev} Rev")
    c3.metric("⚖️ Pienso Real", f"{p_real:.1f} kg")
    c4.metric("⏳ Autonomía", f"{dias} días")

    if p_real <= 0:
        st.error("🚨 ALERTA: Sin existencias de pienso. Registra una compra en 'Gastos'.")
    
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📦 Distribución de Gastos")
        if not gastos.empty: st.plotly_chart(px.bar(gastos, x='categoria', y='cantidad'), use_container_width=True)
    with col_b:
        st.subheader("🥚 Producción de Huevos")
        if not produccion.empty: st.plotly_chart(px.line(produccion, x='fecha', y='huevos'), use_container_width=True)

# --- ALTA LOTES (CORREGIDO) ---
elif menu == "🐣 Alta Lotes":
    st.header("🐣 Registro de Aves")
    with st.form("alta_f"):
        esp = st.selectbox("Especie", list(ESPECIES_FULL.keys()))
        rz = st.selectbox("Raza", ESPECIES_FULL[esp])
        cant = st.number_input("Cantidad", 1)
        sem = st.number_input("Semanas de vida", 0)
        pr = st.number_input("Precio/ud €", 0.0)
        if st.form_submit_button("Añadir Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(sem), pr, "Activo")).connection.commit()
            st.success("Lote registrado"); st.rerun()

# --- PREDICCIÓN PRO (SIN KEYERROR) ---
elif menu == "🔮 Predicción Pro":
    st.header("🔮 Futuro (30 días)")
    if lotes.empty: st.info("Registra aves primero.")
    else:
        fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(30)]
        h_vals, c_vals = [], []
        for i in range(30):
            h_d, c_d = 0, 0
            for _, l in lotes.iterrows():
                # Lógica de edad
                f_a = datetime.strptime(l["fecha"], "%d/%m/%Y" if "/" in l["fecha"] else "%Y-%m-%d")
                ed_sem = l["edad_inicial_semanas"] + ((datetime.now() - f_a).days + i) / 7
                vivos = l['cantidad'] - (bajas[bajas['lote_id']==l['id']]['cantidad'].sum() if not bajas.empty else 0)
                
                if "Gallina" in l['especie']: h_d += 0.8 * vivos if ed_sem > 18 else 0
                else: c_d += (0.5 * ed_sem) * vivos # Crecimiento simple carne
            h_vals.append(h_d); c_vals.append(c_d)
        
        st.plotly_chart(px.line(x=fechas, y=h_vals, title="Huevos Previstos"), use_container_width=True)
        st.plotly_chart(px.area(x=fechas, y=c_vals, title="Kg Carne Estimados", color_discrete_sequence=['red']), use_container_width=True)

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "bajas", "produccion"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        idx = st.number_input("ID a borrar", int(df['id'].min()))
        if st.button("Eliminar"): 
            get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

# --- GASTOS / VENTAS ---
elif menu == "💰 Gastos/Ventas":
    t1, t2 = st.tabs(["💸 Gastos", "🛒 Ventas"])
    with t1:
        with st.form("g"):
            cat = st.selectbox("Categoría", ["Pienso", "Aves", "Medicina"])
            imp = st.number_input("Importe €", 0.0)
            kg = st.number_input("Kg Pienso", 0.0)
            if st.form_submit_button("Añadir Gasto"):
                get_conn().execute("INSERT INTO gastos (fecha, categoria, cantidad, kilos_pienso) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), cat, imp, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("v"):
            imp = st.number_input("Venta €", 0.0)
            if st.form_submit_button("Añadir Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, kg_vendidos) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), "Venta", imp, 0)).connection.commit(); st.rerun()
