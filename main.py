import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - CONTROL TOTAL", layout="wide")
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# ASEGURAR TABLAS
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)')
conn.commit()

# --- CARGA AUTOMÁTICA DE GASTOS INICIALES ---
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

# --- NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ V.22", ["📊 DASHBOARD", "💰 REGISTRAR VENTA", "🥚 PRODUCCIÓN", "💸 GASTOS", "🛠️ MANTENIMIENTO"])

# --- SECCIÓN GASTOS (DONDE AÑADES LAS GALLINAS Y PIENSO) ---
if menu == "💸 GASTOS":
    st.title("💸 Control de Gastos")
    
    # 1. Formulario para añadir nuevos
    st.subheader("➕ Añadir Nuevo Gasto")
    with st.form("nuevo_gasto_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            f_gasto = st.date_input("Fecha del gasto", datetime.now())
            cat_gasto = st.selectbox("Tipo de gasto", ["Pienso", "Inversión", "Otros"])
        with col2:
            con_gasto = st.text_input("Concepto (Ej: Saco 25kg, 3 Pollitos...)")
            imp_gasto = st.number_input("Importe (€)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("💾 Guardar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", 
                      (f_gasto.strftime('%d/%m/%Y'), con_gasto, imp_gasto, cat_gasto))
            conn.commit()
            st.success(f"¡Gasto de {imp_gasto}€ guardado!")
            st.rerun()

    st.divider()

    # 2. Tabla para ver lo que ya hay
    st.subheader("📋 Historial de Gastos")
    df_g = pd.read_sql("SELECT id, fecha, concepto, importe, categoria FROM gastos ORDER BY id DESC", conn)
    st.table(df_g)

# (El resto de secciones: DASHBOARD, VENTAS, PRODUCCIÓN y MANTENIMIENTO se mantienen igual que en la v15.1)
elif menu == "📊 DASHBOARD":
    st.title("📊 Resumen General")
    ing = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gas = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    prod = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    vend = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    col1, col2, col3 = st.columns(3)
    col1.metric("SALDO NETO", f"{round(ing - gas, 2)} €")
    col2.metric("STOCK HUEVOS", f"{int(prod - vend)} uds")
    col3.metric("INGRESOS VENTAS", f"{round(ing, 2)} €")

elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Nueva Venta")
    with st.form("f_venta", clear_on_submit=True):
        f = st.date_input("Fecha", datetime.now())
        cli = st.text_input("Cliente")
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1, step=1)
        if st.form_submit_button("✅ Guardar Venta"):
            if prod == "HUEVOS":
                p_u = 0.45 if f >= datetime(2026, 3, 7).date() else 0.333333
            else: p_u = 50.0
            total_v = cant * p_u
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), cli, prod, cant, total_v))
            conn.commit()
            st.success(f"Venta de {round(total_v, 2)}€ registrada.")

elif menu == "🥚 PRODUCCIÓN":
    st.title("🥚 Registro de Huevos")
    with st.form("f_prod", clear_on_submit=True):
        f = st.date_input("Fecha")
        h = st.number_input("Huevos recogidos", min_value=0, step=1)
        if st.form_submit_button("Guardar"):
            c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f.strftime('%d/%m/%Y'), h))
            conn.commit()
            st.success("Producción anotada")

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
