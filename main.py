import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3

# --- CONFIGURACIÓN TOTAL CONTROL V.22 ---
st.set_page_config(page_title="CORRAL V.22 - CONTROL TOTAL", layout="wide")

# CONEXIÓN BASE DE DATOS
conn = sqlite3.connect('corral_v22_profesional.db', check_same_thread=False)
c = conn.cursor()

# Tablas Espejo del Excel
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY, fecha TEXT, huevos INTEGER, notas TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY, f_muerte TEXT, f_compra TEXT, tipo TEXT, dias INTEGER, total_baja REAL)')
conn.commit()

# --- MOTOR DE PRECIOS V.22 ---
def calcular_precio_v22(producto, fecha_sel):
    if producto == "HUEVOS":
        # Umbral exacto del Excel: 7 de Marzo de 2026
        fecha_cambio = datetime(2026, 3, 7).date()
        return 0.45 if fecha_sel >= fecha_cambio else 0.333333
    return 50.0 # Precio fijo POLLO

# --- NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ V.22", [
    "📊 RESUMEN GENERAL", 
    "🥚 REGISTRO PRODUCCIÓN", 
    "💰 REGISTRO VENTAS", 
    "💸 GASTOS E INVERSIÓN", 
    "🌈 REGISTRO DE BAJAS",
    "🛠️ EDITAR / BORRAR DATOS"
])

# --- 1. RESUMEN GENERAL ---
if menu == "📊 RESUMEN GENERAL":
    st.title("📊 Estado del Corral")
    
    # Cálculos Financieros
    ventas_tot = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gastos_tot = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    bajas_tot = pd.read_sql("SELECT SUM(total_baja) FROM bajas", conn).iloc[0,0] or 0.0
    
    saldo_real = ventas_tot - gastos_tot - bajas_tot
    
    # Stock
    prod_tot = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    vend_tot = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    stock = prod_tot - vend_tot

    col1, col2, col3 = st.columns(3)
    col1.metric("SALDO NETO REAL", f"{round(saldo_real, 2)} €")
    col2.metric("HUEVOS DISPONIBLES", f"{stock} uds")
    col3.metric("INGRESOS VENTAS", f"{round(ventas_tot, 2)} €")

    st.divider()
    st.subheader("📋 Últimos movimientos")
    st.table(pd.read_sql("SELECT fecha, cliente, producto, cantidad, total FROM ventas ORDER BY id DESC LIMIT 5", conn))

# --- 6. SECCIÓN DE EDICIÓN (NUEVA) ---
elif menu == "🛠️ EDITAR / BORRAR DATOS":
    st.title("🛠️ Mantenimiento de Datos")
    st.warning("Desde aquí puedes eliminar registros incorrectos.")
    
    tabla_sel = st.selectbox("¿Qué tabla quieres revisar?", ["Ventas", "Producción", "Gastos", "Bajas"])
    mapa_tablas = {"Ventas": "ventas", "Producción": "produccion", "Gastos": "gastos", "Bajas": "bajas"}
    
    df_edit = pd.read_sql(f"SELECT * FROM {mapa_tablas[tabla_sel]} ORDER BY id DESC", conn)
    st.dataframe(df_edit, use_container_width=True)
    
    id_borrar = st.number_input("Introduce el ID del registro que quieres borrar", min_value=1, step=1)
    if st.button("❌ Eliminar Registro definitivamente"):
        c.execute(f"DELETE FROM {mapa_tablas[tabla_sel]} WHERE id = ?", (id_borrar,))
        conn.commit()
        st.success(f"Registro {id_borrar} eliminado. Actualiza la página.")

# --- (Resto de secciones: Producción, Ventas, Gastos, Bajas mantenidas igual que antes) ---
elif menu == "💰 REGISTRO VENTAS":
    st.subheader("💰 Nueva Venta a Cliente")
    with st.form("venta"):
        f = st.date_input("Fecha de venta")
        cli = st.text_input("Cliente (paco, antonio, pedro...)")
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1, step=1)
        pre_uni = calcular_precio_v22(prod, f)
        total_v = cant * pre_uni
        if st.form_submit_button("Guardar Venta"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), cli, prod, cant, total_v))
            conn.commit()
            st.success("Venta guardada")

# ... (El resto del código de Producción, Gastos y Bajas sigue igual)
