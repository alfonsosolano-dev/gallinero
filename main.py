import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - REVISIÓN", layout="wide")

# CONEXIÓN SEGURA
def get_db_connection():
    conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
    # Esto ayuda a que los datos se guarden al instante
    conn.isolation_level = None 
    return conn

conn = get_db_connection()
c = conn.cursor()

# CREAR TABLAS SI NO EXISTEN
c.execute('''CREATE TABLE IF NOT EXISTS produccion 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS ventas 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)''')
c.execute('''CREATE TABLE IF NOT EXISTS gastos 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS bajas 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, f_muerte TEXT, f_compra TEXT, tipo TEXT, total_baja REAL)''')

# --- LÓGICA DE PRECIOS ---
def calcular_precio(producto, fecha_sel):
    if producto == "HUEVOS":
        # Fecha de cambio: 7 de marzo de 2026
        limite = datetime(2026, 3, 7).date()
        return 0.45 if fecha_sel >= limite else 0.333333
    return 50.0

# --- INTERFAZ ---
menu = st.sidebar.radio("MENÚ", ["DASHBOARD", "REGISTROS", "MANTENIMIENTO"])

if menu == "DASHBOARD":
    st.title("📊 Resumen V.22")
    
    # Lectura de datos protegida
    try:
        df_p = pd.read_sql("SELECT SUM(huevos) as tot FROM produccion", conn)
        total_huevos = df_p['tot'].iloc[0] or 0
        
        df_v = pd.read_sql("SELECT SUM(cantidad) as cant, SUM(total) as rev FROM ventas WHERE producto='HUEVOS'", conn)
        huevos_vendidos = df_v['cant'].iloc[0] or 0
        ingresos = df_v['rev'].iloc[0] or 0.0
        
        df_g = pd.read_sql("SELECT SUM(importe) as gast FROM gastos", conn)
        total_gastos = df_g['gast'].iloc[0] or 0.0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("STOCK", f"{int(total_huevos - huevos_vendidos)} uds")
        col2.metric("SALDO", f"{round(ingresos - total_gastos, 2)} €")
        col3.metric("EFICACIA", "---" if total_huevos == 0 else "OK")
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")

elif menu == "REGISTROS":
    st.subheader("📝 Añadir Datos")
    tipo = st.selectbox("¿Qué quieres registrar?", ["Producción", "Venta", "Gasto"])
    
    with st.form("nuevo_dato"):
        f = st.date_input("Fecha")
        if tipo == "Producción":
            h = st.number_input("Huevos", min_value=0)
            if st.form_submit_button("Guardar"):
                c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f.strftime('%Y-%m-%d'), h))
                st.success("Guardado")
                
        elif tipo == "Venta":
            cli = st.text_input("Cliente")
            prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
            can = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Guardar"):
                p = calcular_precio(prod, f)
                c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)",
                          (f.strftime('%Y-%m-%d'), cli, prod, can, can*p))
                st.success("Venta registrada")

elif menu == "MANTENIMIENTO":
    st.subheader("🛠 Borrar registros")
    tabla = st.selectbox("Tabla", ["produccion", "ventas", "gastos"])
    df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    st.dataframe(df)
    
    id_del = st.number_input("ID a borrar", min_value=0)
    if st.button("Eliminar"):
        c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_del,))
        st.warning("Borrado. Recarga la página.")



