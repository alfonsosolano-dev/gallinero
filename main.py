import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - DEMO", layout="wide")
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# ASEGURAR TABLAS
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
conn.commit()

# --- FUNCIÓN: CARGA DE DATOS FICTICIOS ---
def cargar_datos_demo():
    # Limpiar lo que haya para no duplicar
    c.execute("DELETE FROM produccion"); c.execute("DELETE FROM ventas"); c.execute("DELETE FROM gastos")
    
    # 1. Producción de los últimos 10 días (aprox 6-8 huevos/día)
    for i in range(10):
        fecha = (datetime.now() - timedelta(days=i)).strftime('%d/%m/%Y')
        c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (fecha, 7))
    
    # 2. Ventas Ficticias (Paco, Antonio, Pedro)
    c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
              ((datetime.now() - timedelta(days=2)).strftime('%d/%m/%Y'), 'antonio', 'HUEVOS', 12, 5.40))
    c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
              ((datetime.now() - timedelta(days=5)).strftime('%d/%m/%Y'), 'paco', 'HUEVOS', 12, 4.00))
    c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
              ((datetime.now() - timedelta(days=8)).strftime('%d/%m/%Y'), 'pedro', 'POLLO', 1, 50.00))
    
    # 3. Gastos Iniciales
    c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", 
              ('02/02/2026', 'Saco Pienso 25kg', 18.50, 'Pienso'))
    c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", 
              ('21/02/2026', 'Compra 7 Gallinas', 52.00, 'Inversión'))
    conn.commit()

# --- INTERFAZ ---
menu = st.sidebar.radio("MENÚ", ["📊 DASHBOARD", "🥚 REGISTROS", "🛠️ MANTENIMIENTO", "📄 PDF"])

if menu == "📊 DASHBOARD":
    st.title("📊 Análisis de Situación (Demo)")
    
    p = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    v = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    ing = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gas = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("HUEVOS EN STOCK", f"{int(p - v)} uds")
    col2.metric("SALDO NETO", f"{round(ing - gas, 2)} €")
    col3.metric("INGRESOS TOTALES", f"{round(ing, 2)} €")
    
    st.divider()
    st.subheader("📈 Producción Reciente")
    df_p = pd.read_sql("SELECT fecha, huevos FROM produccion ORDER BY id DESC LIMIT 7", conn)
    if not df_p.empty:
        st.line_chart(df_p.set_index('fecha'))

elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Centro de Control")
    
    st.subheader("🚀 Datos de Prueba")
    if st.button("CARGAR DATOS FICTICIOS"):
        cargar_datos_demo()
        st.success("Datos cargados. Ve al Dashboard para ver la magia.")
        st.rerun()
    
    st.divider()
    st.subheader("🗑️ Borrado Manual")
    tabla = st.selectbox("Tabla:", ["ventas", "produccion", "gastos"])
    df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    
    id_del = st.number_input("ID a eliminar:", min_value=0, step=1)
    if st.button("ELIMINAR"):
        c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_del,))
        conn.commit()
        st.warning(f"ID {id_del} borrado.")
        st.rerun()

# (Las secciones de REGISTROS y PDF se mantienen iguales a las versiones anteriores)




