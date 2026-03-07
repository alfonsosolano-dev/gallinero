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

# --- 2. REGISTRAR VENTA ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Nueva Venta")
    with st.form("f_venta", clear_on_submit=True):
        f = st.date_input("Fecha", datetime.now())
        cli = st.text_input("Cliente")
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1, step=1)
        p_u = get_precio_v22(prod, f)
        if st.form_submit_button("✅ Guardar Venta"):
            total_v = cant * p_u
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), cli, prod, cant, total_v))
            conn.commit()
            st.success(f"Venta de {round(total_v, 2)}€ registrada.")

# --- 3. PRODUCCIÓN (LÍNEA DEL ERROR CORREGIDA) ---
elif menu == "🥚 PRODUCCIÓN":
    st.title("🥚 Registro de Huevos")
    with st.form("f_prod", clear_on_submit=True):
        f = st.date_input("Fecha")
        h = st.number_input("Huevos recogidos", min_value=0, step=1)
        if st.form_submit_button("Guardar"):
            # Aquí estaba el paréntesis sin cerrar:
            c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f.strftime('%d/%m/%Y'), h))
            conn.commit()
            st.success("Producción anotada")

# --- 4. GASTOS ---
elif menu == "💸 GASTOS":
    st.title("💸 Historial de Gastos")
    df_g = pd.read_sql("SELECT id, fecha, concepto, importe, categoria FROM gastos ORDER BY id ASC", conn)
    st.table(df_g)

# --- 5. MANTENIMIENTO ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Borrar Registros")
    tabla = st.selectbox("Selecciona tabla:", ["ventas", "produccion", "gastos"])
    df_m = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    st.dataframe(df_m, use_container_width=True)
    id_del = st.number_input("ID a borrar:", min_value=0, step=1)
    if st.button("❌ Borrar"):
        c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_del,))
        conn.commit()
        st.rerun()
