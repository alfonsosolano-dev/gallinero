import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - HISTÓRICO", layout="wide")
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# ASEGURAR TABLAS
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)')
conn.commit()

# --- NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ V.22", ["📊 DASHBOARD", "📈 EVOLUCIÓN / HISTÓRICO", "💰 VENTAS", "🥚 PRODUCCIÓN", "💸 GASTOS", "🛠️ MANTENIMIENTO"])

# --- 1. DASHBOARD (RESUMEN RÁPIDO) ---
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

# --- 2. NUEVA SECCIÓN: HISTÓRICO Y EVOLUCIÓN ---
elif menu == "📈 EVOLUCIÓN / HISTÓRICO":
    st.title("📈 Histórico de Producción y Ventas")
    
    tab1, tab2 = st.tabs(["🥚 Histórico Producción", "💰 Histórico Ventas"])
    
    with tab1:
        st.subheader("Evolución de Puesta Diaria")
        df_p = pd.read_sql("SELECT fecha, huevos FROM produccion ORDER BY id ASC", conn)
        if not df_p.empty:
            # Gráfico de línea para ver si la puesta sube o baja
            st.line_chart(df_p.set_index('fecha'))
            st.write("### Datos Detallados")
            st.dataframe(df_p, use_container_width=True)
        else:
            st.info("Aún no hay datos de producción registrados.")

    with tab2:
        st.subheader("Ventas Realizadas")
        df_v = pd.read_sql("SELECT fecha, cliente, producto, cantidad, total FROM ventas ORDER BY id ASC", conn)
        if not df_v.empty:
            # Resumen por cliente
            st.write("### Ventas por Cliente")
            resumen_cli = df_v.groupby('cliente')['total'].sum()
            st.bar_chart(resumen_cli)
            
            st.write("### Registro de Ventas")
            st.dataframe(df_v, use_container_width=True)
        else:
            st.info("Aún no hay ventas registradas.")

# --- 3. VENTAS (REGISTRO) ---
elif menu == "💰 VENTAS":
    st.title("💰 Registrar Nueva Venta")
    with st.form("f_venta", clear_on_submit=True):
        f = st.date_input("Fecha", datetime.now())
        cli = st.text_input("Cliente").lower() # Lo guardamos en minúsculas para que no haya duplicados
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1, step=1)
        if st.form_submit_button("✅ Guardar Venta"):
            if prod == "HUEVOS":
                p_u = 0.45 if f >= datetime(2026, 3, 7).date() else 0.333333
            else: p_u = 50.0
            total_v = cant * p_u
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), cli, prod, cant, total_v))
            conn.commit()
            st.success("Venta guardada.")

# --- 4. PRODUCCIÓN (REGISTRO) ---
elif menu == "🥚 PRODUCCIÓN":
    st.title("🥚 Registro de Huevos")
    with st.form("f_prod", clear_on_submit=True):
        f = st.date_input("Fecha")
        h = st.number_input("Huevos recogidos", min_value=0, step=1)
        if st.form_submit_button("Guardar"):
            c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f.strftime('%d/%m/%Y'), h))
            conn.commit()
            st.success("Producción anotada.")

# --- 5. GASTOS ---
elif menu == "💸 GASTOS":
    st.title("💸 Control de Gastos")
    with st.form("nuevo_gasto_form", clear_on_submit=True):
        f_gasto = st.date_input("Fecha", datetime.now())
        cat_gasto = st.selectbox("Tipo", ["Pienso", "Inversión", "Otros"])
        con_gasto = st.text_input("Concepto")
        imp_gasto = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("💾 Guardar"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", 
                      (f_gasto.strftime('%d/%m/%Y'), con_gasto, imp_gasto, cat_gasto))
            conn.commit()
            st.rerun()
    st.table(pd.read_sql("SELECT id, fecha, concepto, importe, categoria FROM gastos ORDER BY id DESC", conn))

# --- 6. MANTENIMIENTO ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Editor de Datos")
    tabla = st.selectbox("Seleccionar tabla:", ["ventas", "produccion", "gastos"])
    df_m = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    st.dataframe(df_m, use_container_width=True)
    id_del = st.number_input("ID a borrar:", min_value=0, step=1)
    if st.button("❌ Eliminar"):
        c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_del,))
        conn.commit()
        st.rerun()
