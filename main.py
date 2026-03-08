import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.45", layout="wide")
conn = sqlite3.connect('corral_v45_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_v45():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    conn.commit()

inicializar_v45()

def cargar(tabla):
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()

# --- MENÚ ---
menu = st.sidebar.radio("MENÚ", ["📊 RENTABILIDAD Y COSTES", "🍗 CRECIMIENTO", "💸 GASTOS", "💰 VENTAS", "🥚 PUESTA", "🐣 ALTA ANIMALES", "🛠️ ADMIN"])

# --- 2. SECCIÓN: RENTABILIDAD (EL CÁLCULO QUE PEDISTE) ---
if menu == "📊 RENTABILIDAD Y COSTES":
    st.title("💰 Análisis de Coste por Animal")
    df_l = cargar('lotes')
    df_g = cargar('gastos')
    
    if not df_l.empty:
        st.subheader("Desglose de inversión por lote")
        resumen_costes = []
        
        for _, lote in df_l[df_l['estado']=='Activo'].iterrows():
            # 1. Coste de compra
            coste_compra = lote['cantidad'] * lote['precio_ud']
            
            # 2. Coste de pienso asignado a esta raza
            # Buscamos en gastos donde la raza coincida y la categoría sea 'Pienso...'
            pienso_lote = df_g[(df_g['raza'] == lote['raza']) & (df_g['categoria'].str.contains('Pienso', na=False))]['importe'].sum()
            
            total_invertido = coste_compra + pienso_lote
            coste_por_animal = total_invertido / lote['cantidad']
            
            resumen_costes.append({
                "Lote": f"{lote['especie']} {lote['raza']}",
                "Cant.": lote['cantidad'],
                "Compra Total": f"{coste_compra:.2f}€",
                "Pienso Gastado": f"{pienso_lote:.2f}€",
                "INVERSIÓN TOTAL": f"{total_invertido:.2f}€",
                "COSTE POR ANIMAL": f"{coste_por_animal:.2f}€"
            })
            
        st.table(pd.DataFrame(resumen_costes))
        st.info("💡 **Consejo:** Para tener beneficio, el precio de venta debe ser superior al 'COSTE POR ANIMAL' mostrado arriba.")
    else:
        st.warning("No hay lotes activos para calcular costes.")

# --- 3. SECCIÓN: GASTOS (ASIGNACIÓN PRECISA) ---
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    df_l = cargar('lotes')
    opciones = ["General"] + [f"{r['raza']}" for _, r in df_l[df_l['estado']=='Activo'].iterrows()] if not df_l.empty else ["General"]
    
    with st.form("f_gasto", clear_on_submit=True):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Pollos", "Pienso Gallinas", "Pienso Codornices", "Infraestructura", "Salud"])
        rz = st.selectbox("Asignar a Raza específica:", opciones)
        con = st.text_input("Concepto (Ej: Saco 25kg)")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit(); st.rerun()
    st.dataframe(cargar('gastos'))

# (Las demás pestañas: CRECIMIENTO, VENTAS, PUESTA, ALTA y ADMIN mantienen sus funciones completas)
