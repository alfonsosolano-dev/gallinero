import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - REVISIÓN PROFUNDA", layout="wide")

# CONEXIÓN SEGURA
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# ASEGURAR TABLAS
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
conn.commit()

# --- LIMPIADOR DE FECHAS (Para evitar el error de los pantallazos) ---
def limpiar_fecha(fecha_str):
    try:
        # Intenta formato día/mes/año
        return datetime.strptime(fecha_str, '%d/%m/%Y').date()
    except:
        try:
            # Intenta formato año-mes-día
            return datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except:
            return datetime.now().date()

# --- INTERFAZ ---
st.sidebar.title("🛠 Panel de Control")
menu = st.sidebar.radio("Ir a:", ["📊 Dashboard", "🥚 Producción", "💰 Ventas Clientes", "🛠 Mantenimiento"])

if menu == "📊 Dashboard":
    st.title("Estado Real del Corral")
    
    # Carga protegida para evitar que el Dashboard salga en rojo
    try:
        res_p = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
        res_v = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
        res_ing = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("HUEVOS DISPONIBLES", f"{int(res_p - res_v)} uds")
        c2.metric("TOTAL INGRESOS", f"{round(res_ing, 2)} €")
        c3.metric("TOTAL RECOGIDOS", f"{int(res_p)} uds")
    except Exception as e:
        st.warning("Aún no hay datos suficientes para el Dashboard.")

elif menu == "💰 Ventas Clientes":
    st.subheader("Nueva Venta (Lógica V.22)")
    with st.form("f_ventas"):
        f = st.date_input("Fecha")
        cli = st.text_input("Cliente")
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1)
        
        # Lógica de precio automática
        if prod == "HUEVOS":
            p_uni = 0.45 if f >= datetime(2026, 3, 7).date() else 0.333333
        else:
            p_uni = 50.0
            
        total_calc = cant * p_uni
        st.write(f"Total a cobrar: **{round(total_calc, 2)} €**")
        
        if st.form_submit_button("Registrar Venta"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), cli, prod, cant, total_calc))
            conn.commit()
            st.success("Venta guardada")

elif menu == "🛠 Mantenimiento":
    st.subheader("Gestión de la Base de Datos")
    tabla = st.selectbox("Selecciona tabla", ["produccion", "ventas", "gastos"])
    
    df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    
    id_borrar = st.number_input("ID del registro a borrar", min_value=0, step=1)
    if st.button("❌ Borrar Definitivamente"):
        c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_borrar,))
        conn.commit()
        st.rerun()



