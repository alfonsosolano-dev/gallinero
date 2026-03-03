import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3

# --- CONFIGURACIÓN ESTILO V.22 ---
st.set_page_config(page_title="CORRAL V.22 - CONTROL TOTAL", layout="wide")

# CONEXIÓN BASE DE DATOS
conn = sqlite3.connect('corral_v22_limpio.db', check_same_thread=False)
c = conn.cursor()

# Tablas idénticas a tus hojas de Excel
c.execute('CREATE TABLE IF NOT EXISTS produccion (fecha TEXT, huevos INTEGER, notas TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS bajas (f_muerte TEXT, f_compra TEXT, tipo TEXT, dias INTEGER, total_baja REAL)')
conn.commit()

# --- LÓGICA DE PRECIOS (Config_Precios.csv) ---
def calcular_precio_v22(producto, fecha_sel):
    if producto == "HUEVOS":
        # Fecha de cambio según tu Excel: 7 de Marzo de 2026
        fecha_cambio = datetime(2026, 3, 7).date()
        return 0.45 if fecha_sel >= fecha_cambio else 0.333333
    return 50.0 # Precio fijo POLLO

# --- NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ V.22", ["📊 RESUMEN GENERAL", "🥚 REGISTRO PRODUCCIÓN", "💰 REGISTRO VENTAS", "💸 GASTOS E INVERSIÓN", "🌈 REGISTRO DE BAJAS"])

# --- 1. RESUMEN GENERAL (Dashboard) ---
if menu == "📊 RESUMEN GENERAL":
    st.title("📊 Resumen Financiero y Stock")
    
    # Cálculos
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
    st.subheader("📋 Últimos movimientos registrados")
    st.table(pd.read_sql("SELECT * FROM ventas ORDER BY fecha DESC LIMIT 5", conn))

# --- 2. REGISTRO VENTAS (Con lógica de clientes) ---
elif menu == "💰 REGISTRO VENTAS":
    st.subheader("💰 Nueva Venta a Cliente")
    with st.form("venta"):
        f = st.date_input("Fecha de venta")
        cli = st.text_input("Cliente (paco, antonio, pedro...)")
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1, step=1)
        
        pre_uni = calcular_precio_v22(prod, f)
        total_v = cant * pre_uni
        
        st.info(f"Precio Unitario: {round(pre_uni, 4)}€ | TOTAL: {round(total_v, 2)}€")
        
        if st.form_submit_button("Guardar Venta"):
            c.execute("INSERT INTO ventas VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), cli, prod, cant, total_v))
            conn.commit()
            st.success("Venta guardada")

# --- 3. REGISTRO BAJAS (Con cálculo de días) ---
elif menu == "🌈 REGISTRO DE BAJAS":
    st.subheader("🌈 Registro de Bajas y Mortalidad")
    with st.form("baja"):
        f_m = st.date_input("Fecha de Muerte")
        f_c = st.date_input("Fecha de Compra")
        tipo = st.selectbox("Tipo de animal", ["gallina", "pollo"])
        inv_ini = st.number_input("Inversión inicial (€)", value=7.42 if tipo=="gallina" else 2.5)
        
        if st.form_submit_button("Registrar Baja"):
            dias = (f_m - f_c).days
            # Coste de pienso acumulado según tu Excel
            pienso_diario = 0.05 if tipo == "gallina" else 0.07
            total_perdida = inv_ini + (dias * pienso_diario)
            
            c.execute("INSERT INTO bajas VALUES (?,?,?,?,?)", (f_m.strftime('%d/%m/%Y'), f_c.strftime('%d/%m/%Y'), tipo, dias, total_perdida))
            conn.commit()
            st.error(f"Baja registrada. Pérdida total: {round(total_perdida, 2)}€")

# --- 4. PRODUCCIÓN Y GASTOS (Similares a los anteriores) ---
elif menu == "🥚 REGISTRO PRODUCCIÓN":
    st.subheader("🥚 Producción Diaria")
    f_p = st.date_input("Fecha")
    cant_p = st.number_input("Huevos recogidos", min_value=0)
    if st.button("Guardar"):
        c.execute("INSERT INTO produccion VALUES (?,?,?)", (f_p.strftime('%d/%m/%Y'), cant_p, ""))
        conn.commit()
        st.success("Guardado")

elif menu == "💸 GASTOS E INVERSIÓN":
    st.subheader("💸 Gastos, Pienso y Veterinaria")
    with st.form("gasto"):
        f_g = st.date_input("Fecha")
        cat_g = st.selectbox("Categoría", ["Inversión", "Pienso", "Veterinaria", "Otros"])
        con_g = st.text_input("Concepto")
        imp_g = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("Anotar Gasto"):
            c.execute("INSERT INTO gastos VALUES (?,?,?,?)", (f_g.strftime('%d/%m/%Y'), con_g, imp_g, cat_g))
            conn.commit()
            st.success("Gasto anotado")
