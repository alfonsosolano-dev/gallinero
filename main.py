import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL INTELIGENTE V.50", layout="wide")
conn = sqlite3.connect('corral_v50_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    conn.commit()

inicializar_db()

def cargar(tabla):
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()

# --- MENÚ ---
menu = st.sidebar.radio("MENÚ", ["📊 RENTABILIDAD", "🍗 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🛠️ ADMIN"])

# --- SECCIÓN: PUESTA (CON ALERTA DE MADUREZ) ---
if menu == "🥚 PUESTA":
    st.title("🥚 Diario de Puesta")
    
    # Lógica de Alerta de Madurez
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, lote in df_l[(df_l['especie'] == 'Gallinas') & (df_l['estado'] == 'Activo')].iterrows():
            f_ent = datetime.strptime(lote['fecha'], '%d/%m/%Y')
            edad_actual = (datetime.now() - f_ent).days + int(lote['edad_inicial'])
            if edad_actual >= 130:
                st.error(f"🔥 **¡ALERTA DE MADUREZ!** El lote {lote['raza']} tiene {edad_actual} días. ¡Revisa los nidos hoy!")
    
    with st.form("f_puesta", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Azules", "Codorniz"])
        can = st.number_input("Cantidad de Huevos", min_value=1)
        if st.form_submit_button("✅ ANOTAR HUEVOS"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); st.rerun()
    
    df_p = cargar('produccion')
    if not df_p.empty:
        st.plotly_chart(px.bar(df_p, x='fecha', y='cantidad', color='raza', title="Producción Histórica"))

# --- SECCIÓN: CRECIMIENTO (CÁLCULO EXACTO) ---
elif menu == "🍗 CRECIMIENTO":
    st.title("📈 Estado de Madurez de las Aves")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            
            # Metas: Codorniz 45d, Pollo 60/110d, Gallina 145d
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "Blanco" in (row['tipo_engorde'] or "") else 110
            else: meta = 145
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"{row['especie']} {row['raza']} - Edad: {edad_t} días", expanded=True):
                st.progress(prog)
                if edad_t >= meta: st.warning(f"🎯 El lote ya superó los {meta} días. ¡Listo para producción/salida!")

# (Mantener el resto de secciones: RENTABILIDAD, GASTOS, VENTAS, ALTA, ADMIN del código v48)
