import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.43.1", layout="wide")
conn = sqlite3.connect('corral_v43_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_sistema():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
                  tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, 
                  edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, 
                  importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, 
                  cantidad INTEGER, total REAL, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL)''')
    
    # Gasto automático del material de febrero (100€)
    c.execute("SELECT COUNT(*) FROM gastos WHERE concepto LIKE '%Material%'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                  ('21/02/2026', 'Compra Material y Equipamiento Inicial', 100.0, 'Infraestructura', 'General'))
    conn.commit()

inicializar_sistema()

def cargar_tabla(tabla):
    try:
        df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
        if 'raza' in df.columns: df['raza'] = df['raza'].fillna("General")
        return df
    except: return pd.DataFrame()

# --- MENÚ LATERAL ---
menu = st.sidebar.radio("MENÚ PRINCIPAL", 
    ["📊 RESUMEN", "🍗 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🛠️ ADMIN"])

# --- SECCIÓN: ALTA ANIMALES (CON SELECTOR FLEXIBLE) ---
if menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Registro de Lotes")
    st.info("Registra aquí tus animales (Recuerda: 21 Feb con 15 días de edad inicial para los actuales).")
    
    with st.form("f_lote"):
        f = st.date_input("Fecha adquisición")
        esp = st.selectbox("Especie", ["Pollos", "Gallinas"])
        
        # --- SELECTOR DE RAZA DINÁMICO ---
        raza_sel = st.selectbox("Selecciona Raza", ["Blanca", "Roja", "Chocolate", "Campero", "OTRA (Escribir abajo)"])
        raza_nueva = st.text_input("Si elegiste 'OTRA', escribe la raza aquí (Ej: Huevos Azules)")
        
        raza_final = raza_nueva if raza_sel == "OTRA (Escribir abajo)" else raza_sel
        
        tipo = st.selectbox("Tipo de Engorde (Solo Pollos)", ["N/A", "Blanco", "Campero"])
        e_ini = st.number_input("Edad al comprar (días)", value=15)
        can = st.number_input("Cantidad de aves", min_value=1)
        pre = st.number_input("Precio por ave (€)")
        
        if st.form_submit_button("✅ DAR DE ALTA"):
            if raza_sel == "OTRA (Escribir abajo)" and not raza_nueva:
                st.error("Por favor, escribe el nombre de la nueva raza.")
            else:
                f_s = f.strftime('%d/%m/%Y')
                c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", 
                          (f_s, esp, raza_final, tipo, e_ini, can, pre, 'Activo'))
                # Registro automático de gasto de compra
                c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                          (f_s, f"Compra {can} {raza_final}", can*pre, "Animales", raza_final))
                conn.commit()
                st.success(f"Lote de {raza_final} registrado correctamente.")
                st.rerun()

    st.subheader("Lotes Registrados")
    st.dataframe(cargar_tabla('lotes'), use_container_width=True)

# --- SECCIÓN: PRODUCCIÓN HUEVOS (CON COLOR AZUL) ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Diario de Puesta")
    df_l = cargar_tabla('lotes')
    razas_activas = df_l['raza'].unique().tolist() if not df_l.empty else ["Blanca", "Roja"]
    
    with st.form("f_prod", clear_on_submit=True):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza que ha puesto", razas_activas + ["Chocolate", "Huevos Azules"])
        can = st.number_input("Cantidad de Huevos", min_value=1)
        if st.form_submit_button("✅ ANOTAR"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), rz, can))
            conn.commit(); st.rerun()
    
    df_p = cargar_tabla('produccion')
    if not df_p.empty:
        # Mapa de colores ampliado
        cmap = {
            "Chocolate": "#5D4037", 
            "Roja": "#C62828", 
            "Blanca": "#F5F5F5", 
            "Huevos Azules": "#81D4FA", 
            "General": "#FFA000"
        }
        st.plotly_chart(px.bar(df_p, x='fecha', y='cantidad', color='raza', color_discrete_map=cmap))

# (El resto de secciones: GASTOS, VENTAS, CRECIMIENTO y ADMIN mantienen la lógica de la v43.0)
