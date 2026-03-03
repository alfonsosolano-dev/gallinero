import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from io import BytesIO

# --- CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="Corral Pro v5.0", layout="wide")
conn = sqlite3.connect('corral_final.db', check_same_thread=False)
c = conn.cursor()

# Tablas necesarias
c.execute('CREATE TABLE IF NOT EXISTS produccion (fecha TEXT, cantidad INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
conn.commit()

# --- LÓGICA DE PRECIOS AUTOMÁTICA ---
def calcular_precio(producto, fecha_str):
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
    if producto == "HUEVOS":
        return 0.45 if fecha >= datetime(2026, 3, 7) else 0.3333
    return 50.0 if producto == "POLLO" else 0.0

# --- MENÚ LATERAL ---
menu = st.sidebar.radio("Navegación", ["💰 Resumen Económico", "🚜 Registro Diario", "🛒 Ventas y Clientes", "💾 Exportar Datos"])

# --- 1. RESUMEN ECONÓMICO (EL "EXCEL" MEJORADO) ---
if menu == "💰 Resumen Económico":
    st.title("Control Financiero y Stock")
    
    # Cálculos de Ventas
    total_ventas = pd.read_sql('SELECT SUM(total) FROM ventas', conn).iloc[0,0] or 0.0
    
    # Cálculos de Gastos (Desglosado)
    gastos_pienso = pd.read_sql("SELECT SUM(importe) FROM gastos WHERE categoria='Pienso'", conn).iloc[0,0] or 0.0
    gastos_inv = pd.read_sql("SELECT SUM(importe) FROM gastos WHERE categoria='Inversión'", conn).iloc[0,0] or 0.0
    gastos_vet = pd.read_sql("SELECT SUM(importe) FROM gastos WHERE categoria='Veterinaria'", conn).iloc[0,0] or 0.0
    total_gastos = gastos_pienso + gastos_inv + gastos_vet

    # Control de Stock
    prod_total = pd.read_sql('SELECT SUM(cantidad) FROM produccion', conn).iloc[0,0] or 0
    vendidos_total = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    stock_real = prod_total - vendidos_total

    # DISEÑO DE TARJETAS
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Saldo Neto", f"{round(total_ventas - total_gastos, 2)} €")
    col2.metric("Stock Huevos", f"{int(stock_real)} uds")
    col3.metric("Total Ventas", f"{round(total_ventas, 2)} €")
    col4.metric("Inversión Total", f"{round(total_gastos, 2)} €")

    st.divider()
    
    # TABLA DE GASTOS (Como en tu Excel)
    st.subheader("Detalle de Gastos e Inversión")
    with st.expander("Añadir Gasto (Pienso, Gallinas, Equipo...)"):
        f_g = st.date_input("Fecha Gasto")
        con_g = st.text_input("Concepto (ej: Saco Pienso 25kg)")
        cat_g = st.selectbox("Categoría", ["Inversión", "Pienso", "Veterinaria", "Otros"])
        imp_g = st.number_input("Importe (€)", min_value=0.0)
        if st.button("Guardar Gasto"):
            c.execute("INSERT INTO gastos VALUES (?,?,?,?)", (f_g.strftime('%Y-%m-%d'), con_g, imp_g, cat_g))
            conn.commit()
            st.rerun()

    df_gastos = pd.read_sql("SELECT * FROM gastos ORDER BY fecha DESC", conn)
    st.table(df_gastos)

# --- 2. REGISTRO DIARIO (PRODUCCIÓN) ---
elif menu == "🚜 Registro Diario":
    st.subheader("Recogida de Huevos")
    f_p = st.date_input("Fecha")
    c_p = st.number_input("Cantidad recogida", min_value=0, step=1)
    if st.button("Registrar"):
        c.execute("INSERT INTO produccion VALUES (?,?)", (f_p.strftime('%Y-%m-%d'), c_p))
        conn.commit()
        st.success("Producción anotada")

# --- 3. VENTAS Y CLIENTES ---
elif menu == "🛒 Ventas y Clientes":
    st.subheader("Nueva Venta")
    f_v = st.date_input("Fecha Venta")
    cli_v = st.text_input("Cliente")
    prod_v = st.selectbox("Producto", ["HUEVOS", "POLLO"])
    cant_v = st.number_input("Cantidad", min_value=1)
    
    # Cálculo automático igual que en el Excel
    p_unitario = calcular_precio(prod_v, f_v.strftime('%Y-%m-%d'))
    total_v = round(cant_v * p_unitario, 2)
    
    st.write(f"**Importe Automático:** {total_v} €")
    
    if st.button("Confirmar Venta"):
        c.execute("INSERT INTO ventas VALUES (?,?,?,?,?)", (f_v.strftime('%Y-%m-%d'), cli_v, prod_v, cant_v, total_v))
        conn.commit()
        st.balloons()

# --- 4. EXPORTAR ---
elif menu == "💾 Exportar Datos":
    st.subheader("Copia de seguridad")
    # Función para convertir a Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pd.read_sql('SELECT * FROM produccion', conn).to_excel(writer, sheet_name='Produccion')
        pd.read_sql('SELECT * FROM ventas', conn).to_excel(writer, sheet_name='Ventas')
        pd.read_sql('SELECT * FROM gastos', conn).to_excel(writer, sheet_name='Economia')
    st.download_button("Descargar Excel", output.getvalue(), "mi_corral.xlsx")
