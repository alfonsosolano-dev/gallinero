import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - CONTROL TOTAL", layout="wide")

# CONEXIÓN (Usamos una base de datos persistente)
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# ASEGURAR QUE TODAS LAS TABLAS EXISTEN DESDE EL INICIO
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY, fecha TEXT, huevos INTEGER, notas TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY, f_muerte TEXT, f_compra TEXT, tipo TEXT, total_baja REAL)')
conn.commit()

# --- MOTOR DE PRECIOS ---
def get_precio(producto, fecha_sel):
    if producto == "HUEVOS":
        return 0.45 if fecha_sel >= datetime(2026, 3, 7).date() else 0.333333
    return 50.0

# --- MENÚ LATERAL ---
menu = st.sidebar.radio("MENÚ DE GESTIÓN", ["📊 DASHBOARD", "🥚 REGISTRO HUEVOS", "💰 REGISTRO VENTAS", "💸 GASTOS", "📄 INFORMES PDF"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Resumen de tu Corral")
    
    # Datos para el resumen
    prod_t = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    vent_t = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    ingresos = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gastos_t = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("HUEVOS EN STOCK", f"{prod_t - vent_t} uds")
    c2.metric("SALDO NETO", f"{round(ingresos - gastos_t, 2)} €")
    c3.metric("INGRESOS TOTALES", f"{round(ingresos, 2)} €")
    
    st.divider()
    st.subheader("📝 Historial de Producción (Últimos 10 días)")
    df_p = pd.read_sql("SELECT fecha, huevos FROM produccion ORDER BY id DESC LIMIT 10", conn)
    st.table(df_p if not df_p.empty else pd.DataFrame(columns=["fecha", "huevos"]))

# --- 2. REGISTRO HUEVOS (AQUÍ ES DONDE LLENAS LA TABLA) ---
elif menu == "🥚 REGISTRO HUEVOS":
    st.title("🥚 Recogida Diaria")
    with st.form("f_prod"):
        f_recogida = st.date_input("Fecha de recogida")
        cant_recogida = st.number_input("¿Cuántos huevos has cogido?", min_value=0, step=1)
        if st.form_submit_button("Guardar Producción"):
            c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f_recogida.strftime('%d/%m/%Y'), cant_recogida))
            conn.commit()
            st.success("¡Guardado! Ahora verás el stock actualizado en el Dashboard.")
            st.rerun()

# --- 3. REGISTRO VENTAS ---
elif menu == "💰 REGISTRO VENTAS":
    st.title("💰 Ventas a Clientes")
    with st.form("f_ventas"):
        fv = st.date_input("Fecha")
        cli = st.text_input("Nombre del Cliente (Ej: Paco)")
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1)
        precio = get_precio(prod, fv)
        total = cant * precio
        st.write(f"Total automático: **{round(total, 2)} €**")
        if st.form_submit_button("Confirmar Venta"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
                      (fv.strftime('%d/%m/%Y'), cli, prod, cant, total))
            conn.commit()
            st.success("Venta registrada con éxito.")

# --- 4. GASTOS ---
elif menu == "💸 GASTOS":
    st.title("💸 Control de Gastos")
    with st.form("f_gastos"):
        fg = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Veterinaria", "Inversión", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("Anotar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", (fg.strftime('%d/%m/%Y'), con, imp, cat))
            conn.commit()
            st.success("Gasto guardado.")
    
    st.write("### Histórico")
    st.dataframe(pd.read_sql("SELECT * FROM gastos ORDER BY id DESC", conn), use_container_width=True)

# --- 5. PDF ---
elif menu == "📄 INFORMES PDF":
    st.title("📄 Generar Informe Mensual")
    # (Aquí va la lógica del PDF que ya tenías)
    st.info("Esta sección genera el PDF basado en los datos que hayas metido en las secciones de arriba.")

# (El resto de secciones se mantienen igual que en la versión anterior)

