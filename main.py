import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.express as px
import google.generativeai as genai

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="CORRAL OMNI V88", layout="wide", page_icon="🚜")

DB_PATH = "corral_maestro_pro.db"

# Diccionario Maestro Completo
ESPECIES_FULL = {
    "Gallina": ["Roja (Lohman)", "Blanca (Leghorn)", "Huevo Verde", "Huevo Azul", "Negra", "Extremeña"],
    "Pollo (Carne)": ["Broiler", "Campero / Rural", "Crecimiento Lento", "Capón"],
    "Codorniz": ["Japónica (Huevo)", "Coreana (Carne)", "Vuelo"],
    "Pavo/Pato": ["Pavo Blanco", "Pato Pekín", "Pato Mulard"]
}

# --- 2. MOTOR DE BASE DE DATOS (REPARACIÓN TOTAL) ---
def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        # Creamos las tablas con TODAS las columnas necesarias desde el inicio
        c.execute("""CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, 
            edad_inicial_semanas INTEGER, precio_ud REAL, estado TEXT)""")
        
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, huevos INTEGER)")
        
        c.execute("""CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, 
            concepto TEXT, cantidad REAL, kilos_pienso REAL)""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, 
            cantidad REAL, unidades INTEGER, kg_vendidos REAL)""")
        
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)")
        
        # SCRIPT ANTIFALLOS: Si la tabla ya existía pero le faltan columnas, las añadimos
        columnas_lotes = [info[1] for info in c.execute("PRAGMA table_info(lotes)").fetchall()]
        if 'especie' not in columnas_lotes: c.execute("ALTER TABLE lotes ADD COLUMN especie TEXT DEFAULT 'Gallina'")
        if 'edad_inicial_semanas' not in columnas_lotes: c.execute("ALTER TABLE lotes ADD COLUMN edad_inicial_semanas INTEGER DEFAULT 0")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- 3. CÁLCULOS DE EMPRESA (KPIs) ---
def calcular_kpis(lotes, gastos, ventas, bajas):
    inv = gastos['cantidad'].sum() if not gastos.empty else 0
    rev = ventas['cantidad'].sum() if not ventas.empty else 0
    
    # Cálculo de Pienso y Autonomía
    pienso_comprado = gastos['kilos_pienso'].sum() if not gastos.empty else 0
    consumo_dia = 0
    for _, l in lotes.iterrows():
        muertes = bajas[bajas['lote_id']==l['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas = max(0, l['cantidad'] - muertes)
        # Ratio medio: Gallina 0.115kg, Pollos/Codorniz 0.150kg (crecimiento)
        ratio = 0.115 if "Gallina" in l['especie'] else 0.150
        consumo_dia += vivas * ratio
    
    # Estimamos lo consumido (desde el último gasto de pienso)
    pienso_actual = max(0, pienso_comprado - (consumo_dia * 3)) # Margen de seguridad de 3 días
    autonomia = int(pienso_actual / consumo_dia) if consumo_dia > 0 else 0
    
    return inv, rev, pienso_actual, autonomia

# --- 4. INTERFAZ DE USUARIO ---
inicializar_db()
lotes, gastos, ventas, bajas, produccion = cargar("lotes"), cargar("gastos"), cargar("ventas"), cargar("bajas"), cargar("produccion")

st.sidebar.title("🚜 CORRAL OMNI V88")
menu = st.sidebar.radio("MENÚ PRINCIPAL", ["📊 Dashboard", "🔮 Predicción Pro", "🐣 Registro de Lotes", "🥚 Producción", "💰 Finanzas", "📜 Histórico"])

# --- PANTALLA DASHBOARD ---
if menu == "📊 Dashboard":
    st.title("📊 Panel de Control Industrial")
    inv, rev, p_stock, dias = calcular_kpis(lotes, gastos, ventas, bajas)
    
    # Los 4 Contadores que pedías (Inversión, Beneficio, Pienso, Autonomía)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Inversión Total", f"{inv:.2f} €")
    c2.metric("📈 Beneficio Real", f"{(rev - inv):.2f} €", delta=f"{rev:.2f} Ingresos")
    c3.metric("⚖️ Pienso en Stock", f"{p_stock:.1f} kg")
    c4.metric("⏳ Autonomía", f"{dias} días", delta_color="inverse")

    if p_stock < 20: st.error("🚨 ¡ATENCIÓN! Queda poco pienso en el almacén.")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if not produccion.empty:
            st.plotly_chart(px.line(produccion, x='fecha', y='huevos', title="Evolución Puesta"), use_container_width=True)
    with col2:
        if not lotes.empty:
            st.plotly_chart(px.pie(lotes, values='cantidad', names='especie', title="Censo por Especie"), use_container_width=True)

# --- PANTALLA ALTA DE LOTES ---
elif menu == "🐣 Registro de Lotes":
    st.title("🐣 Entrada de Aves")
    with st.form("alta"):
        esp = st.selectbox("Selecciona Especie", list(ESPECIES_FULL.keys()))
        rz = st.selectbox("Raza / Clase", ESPECIES_FULL[esp])
        cant = st.number_input("Cantidad de aves", 1)
        sem = st.number_input("Edad al entrar (Semanas)", 0)
        coste = st.number_input("Precio por unidad €", 0.0)
        if st.form_submit_button("Registrar Lote"):
            with get_conn() as conn:
                conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?,?)",
                             (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(sem), coste, "Activo"))
            st.success("Lote registrado correctamente."); st.rerun()

# --- PANTALLA PREDICCIÓN ---
elif menu == "🔮 Predicción Pro":
    st.title("🔮 Predicción de Rendimiento (30 días)")
    if lotes.empty:
        st.warning("No hay lotes activos para predecir.")
    else:
        fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(30)]
        h_vals, c_vals = [], []
        
        for i in range(30):
            h_dia, c_dia = 0, 0
            for _, l in lotes.iterrows():
                # Calculamos edad futura
                f_a = datetime.strptime(l["fecha"], "%d/%m/%Y" if "/" in l["fecha"] else "%Y-%m-%d")
                edad_f = l['edad_inicial_semanas'] + ((datetime.now() - f_a).days + i) / 7
                vivos = l['cantidad'] - (bajas[bajas['lote_id']==l['id']]['cantidad'].sum() if not bajas.empty else 0)
                
                if "Gallina" in l['especie']:
                    # Curva simple: Pone si tiene +18 semanas
                    h_dia += (0.85 * vivos) if edad_f >= 18 else 0
                else:
                    # Crecimiento carne: +0.4kg por semana
                    c_dia += (0.4 * edad_f) * vivos
            h_vals.append(h_dia); c_vals.append(c_dia)
        
        st.subheader("🥚 Pronóstico de Huevos")
        st.plotly_chart(px.line(x=fechas, y=h_vals), use_container_width=True)
        st.subheader("⚖️ Pronóstico de Carne (Kg)")
        st.plotly_chart(px.area(x=fechas, y=c_vals, color_discrete_sequence=['red']), use_container_width=True)

# --- PANTALLA FINANZAS ---
elif menu == "💰 Finanzas":
    t1, t2 = st.tabs(["💸 Registrar Gasto", "🛒 Registrar Venta"])
    with t1:
        with st.form("g"):
            cat = st.selectbox("Categoría", ["Pienso", "Aves", "Medicina", "Infraestructura"])
            imp = st.number_input("Importe €", 0.0)
            kg = st.number_input("Kilos de Pienso (Si aplica)", 0.0)
            if st.form_submit_button("Guardar Gasto"):
                get_conn().execute("INSERT INTO gastos (fecha, categoria, cantidad, kilos_pienso) VALUES (?,?,?,?)",
                                   (datetime.now().strftime("%d/%m/%Y"), cat, imp, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("v"):
            val = st.number_input("Venta Total €", 0.0)
            if st.form_submit_button("Guardar Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad) VALUES (?,?,?)",
                                   (datetime.now().strftime("%d/%m/%Y"), "Venta", val)).connection.commit(); st.rerun()

# --- PANTALLA HISTÓRICO ---
elif menu == "📜 Histórico":
    tab = st.selectbox("Selecciona tabla", ["lotes", "produccion", "gastos", "ventas", "bajas"])
    df = cargar(tab)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        borrar = st.number_input("ID a borrar", int(df['id'].min()))
        if st.button("Eliminar Registro"):
            get_conn().execute(f"DELETE FROM {tab} WHERE id={borrar}").connection.commit(); st.rerun()
