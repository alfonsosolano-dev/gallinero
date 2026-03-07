import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - CONTROL TOTAL", layout="wide")
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# ASEGURAR TODAS LAS TABLAS
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)')
conn.commit()

# --- CARGA AUTOMÁTICA DE GASTOS (Si la tabla está vacía) ---
c.execute("SELECT count(*) FROM gastos")
if c.fetchone()[0] == 0:
    gastos_v22 = [
        ('02/02/2026', 'Equipo Total (Inversión Inicial)', 62.0, 'Inversión'),
        ('21/02/2026', '7 Gallinas', 52.0, 'Inversión'),
        ('21/02/2026', '4 Pollos', 10.0, 'Inversión'),
        ('10/03/2026', 'Gallina Parda', 8.5, 'Inversión'),
        ('15/03/2026', 'Pienso y Nutrición', 33.25, 'Pienso')
    ]
    c.executemany("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", gastos_v22)
    conn.commit()

# --- MOTOR DE PRECIOS V.22 ---
def get_precio_v22(producto, fecha_sel):
    if producto == "HUEVOS":
        # Umbral 7 de Marzo 2026
        limite = datetime(2026, 3, 7).date()
        return 0.45 if fecha_sel >= limite else 0.333333
    return 50.0

# --- NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ V.22", ["📊 DASHBOARD", "💰 REGISTRAR VENTA", "🥚 PRODUCCIÓN", "💸 GASTOS", "🛠️ MANTENIMIENTO"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Resumen General")
    ing = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gas = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    prod = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    vend = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("SALDO NETO", f"{round(ing - gas, 2)} €")
    col2.metric("STOCK HUEVOS", f"{int(prod - vend)} uds")
    col3.metric("INGRESOS VENTAS", f"{round(ing, 2)} €")

# --- 2. REGISTRAR VENTA (Mantenido) ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Nueva Venta a Cliente")
    with st.form("f_venta", clear_on_submit=True):
        f = st.date_input("Fecha", datetime.now())
        cli = st.text_input("Cliente (paco, antonio, pedro...)")
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1, step=1)
        
        p_u = get_precio_v22(prod, f)
        total_v = cant * p_u
        st.write(f"**Precio Unitario Aplicado:** {round(p_u, 3)}€ | **Total:** {round(total_v, 2)}€")
        
        if st.form_submit_button("✅ Guardar Venta"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), cli, prod, cant, total_v))
            conn.commit()
            st.success(f"Venta registrada para {cli}")

# --- 3. PRODUCCIÓN ---
elif menu == "🥚 PRODUCCIÓN":
    st.title("🥚 Registro de Huevos")
    with st.form("f_prod"):
        f = st.date_input("Fecha")
        h = st.number_input("Huevos recogidos", min_value=0, step=1)
        if st.form_submit_button("Guardar"):
            c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f.
