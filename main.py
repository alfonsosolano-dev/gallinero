import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from fpdf import FPDF

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - CONTROL TOTAL", layout="wide")

# CONEXIÓN
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# ASEGURAR TABLAS (Añadido ID para poder borrar)
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, f_muerte TEXT, f_compra TEXT, tipo TEXT, total_baja REAL)')
conn.commit()

# --- MOTOR DE PRECIOS ---
def get_precio(producto, fecha_sel):
    if producto == "HUEVOS":
        return 0.45 if fecha_sel >= datetime(2026, 3, 7).date() else 0.333333
    return 50.0

# --- FUNCIÓN PDF ---
def crear_pdf(mes, datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"INFORME CORRAL - {mes.upper()}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    for k, v in datos.items():
        pdf.cell(200, 10, txt=f"{k}: {v}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- MENÚ ---
menu = st.sidebar.radio("GESTIÓN V.22", 
    ["📊 DASHBOARD", "🥚 HUEVOS", "💰 VENTAS", "💸 GASTOS", "🛠️ MANTENIMIENTO", "📄 PDF"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Resumen General")
    prod = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    vent = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    ingr = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gast = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("STOCK HUEVOS", f"{prod - vent} uds")
    c2.metric("SALDO NETO", f"{round(ingr - gast, 2)} €")
    c3.metric("INGRESOS", f"{round(ingr, 2)} €")

# --- 2. REGISTRO HUEVOS ---
elif menu == "🥚 HUEVOS":
    st.title("🥚 Registro de Producción")
    with st.form("f1"):
        f = st.date_input("Fecha")
        n = st.number_input("Cantidad de huevos", min_value=0, step=1)
        if st.form_submit_button("Guardar"):
            c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f.strftime('%d/%m/%Y'), n))
            conn.commit()
            st.success("Registrado")

# --- 3. REGISTRO VENTAS ---
elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    with st.form("f2"):
        f = st.date_input("Fecha")
        cli = st.text_input("Cliente")
        pro = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        can = st.number_input("Cantidad", min_value=1)
        if st.form_submit_button("Guardar Venta"):
            tot = can * get_precio(pro, f)
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), cli, pro, can, tot))
            conn.commit()
            st.success(f"Venta guardada: {round(tot,2)}€")

# --- 4. GASTOS ---
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    with st.form("f3"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Veterinaria", "Inversión", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("Guardar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), con, imp, cat))
            conn.commit()
            st.success("Gasto guardado")

# --- 5. MANTENIMIENTO (BORRADO) ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Editar o Borrar Registros")
    opcion = st.selectbox("Selecciona tabla para revisar:", ["Ventas", "Produccion", "Gastos"])
    tabla = opcion.lower()
    
    df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    st.write(f"Datos actuales en {opcion}:")
    st.dataframe(df, use_container_width=True)
    
    id_borrar = st.number_input("ID a eliminar", min_value=0, step=1)
    if st.button("❌ Eliminar Permanentemente"):
        c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_borrar,))
        conn.commit()
        st.warning(f"Registro {id_borrar} eliminado.")
        st.rerun()

# --- 6. PDF ---
elif menu == "📄 PDF":
    st.title("📄 Informe Mensual")
    mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    if st.button("Descargar PDF"):
        # (Aquí podrías filtrar por fecha para el resumen del mes seleccionado)
        p = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
        v = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0
        res = {"Huevos Recogidos": p, "Total Ventas": f"{v} €"}
        pdf = crear_pdf(mes, res)
        st.download_button("⬇️ Guardar PDF", pdf, f"Informe_{mes}.pdf", "application/pdf")

# (El resto de secciones se mantienen igual que en la versión anterior)


