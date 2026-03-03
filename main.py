import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
from fpdf import FPDF
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - CONTROL TOTAL", layout="wide")

# CONEXIÓN BASE DE DATOS
def get_connection():
    return sqlite3.connect('corral_v22_final.db', check_same_thread=False)

conn = get_connection()
c = conn.cursor()

# CREACIÓN DE TABLAS
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
conn.commit()

# --- LÓGICA DE PRECIOS V.22 ---
def get_precio_v22(producto, fecha_sel):
    if producto == "HUEVOS":
        # Umbral exacto de tu Config_Precios.csv
        fecha_cambio = datetime(2026, 3, 7).date()
        return 0.45 if fecha_sel >= fecha_cambio else 0.333333
    return 50.0

# --- MENÚ LATERAL ---
st.sidebar.title("🚜 Gestión V.22")
menu = st.sidebar.radio("IR A:", ["📊 DASHBOARD", "🥚 REGISTRAR HUEVOS", "💰 REGISTRAR VENTAS", "💸 REGISTRAR GASTOS", "🛠️ MANTENIMIENTO / BORRAR", "📄 GENERAR PDF"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Resumen del Corral")
    p = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    v = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    ing = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gas = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("STOCK ACTUAL", f"{int(p - v)} uds", "Huevos")
    col2.metric("SALDO NETO", f"{round(ing - gas, 2)} €")
    col3.metric("INGRESOS VENTAS", f"{round(ing, 2)} €")

# --- 2. REGISTRAR HUEVOS (Ya no está en blanco) ---
elif menu == "🥚 REGISTRAR HUEVOS":
    st.title("🥚 Entrada de Producción")
    st.info("Introduce aquí los huevos recogidos hoy.")
    with st.form("form_huevos", clear_on_submit=True):
        f_prod = st.date_input("Fecha", datetime.now())
        c_prod = st.number_input("Cantidad de huevos", min_value=0, step=1)
        if st.form_submit_button("💾 Guardar Producción"):
            c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f_prod.strftime('%d/%m/%Y'), c_prod))
            conn.commit()
            st.success(f"Registrados {c_prod} huevos el día {f_prod.strftime('%d/%m/%Y')}")

# --- 3. REGISTRAR VENTAS ---
elif menu == "💰 REGISTRAR VENTAS":
    st.title("💰 Nueva Venta")
    with st.form("form_ventas", clear_on_submit=True):
        f_v = st.date_input("Fecha Venta", datetime.now())
        cli = st.text_input("Cliente (paco, antonio, pedro...)")
        prod = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        cant = st.number_input("Cantidad", min_value=1, step=1)
        
        # Cálculo en tiempo real
        p_u = get_precio_v22(prod, f_v)
        total_v = cant * p_u
        st.write(f"**Precio Unitario:** {round(p_u, 3)}€ | **TOTAL:** {round(total_v, 2)}€")
        
        if st.form_submit_button("✅ Confirmar Venta"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total) VALUES (?,?,?,?,?)", 
                      (f_v.strftime('%d/%m/%Y'), cli, prod, cant, total_v))
            conn.commit()
            st.balloons()
            st.success("Venta anotada correctamente")

# --- 4. REGISTRAR GASTOS ---
elif menu == "💸 REGISTRAR GASTOS":
    st.title("💸 Gastos y Pienso")
    with st.form("form_gastos", clear_on_submit=True):
        f_g = st.date_input("Fecha Gasto")
        cat = st.selectbox("Categoría", ["Pienso", "Veterinaria", "Inversión", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("💾 Guardar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", 
                      (f_g.strftime('%d/%m/%Y'), con, imp, cat))
            conn.commit()
            st.success("Gasto guardado")

# --- 5. MANTENIMIENTO / BORRAR ---
elif menu == "🛠️ MANTENIMIENTO / BORRAR":
    st.title("🛠️ Gestión de Datos")
    t_name = st.selectbox("Selecciona tabla para editar:", ["ventas", "produccion", "gastos"])
    df = pd.read_sql(f"SELECT * FROM {t_name} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    
    id_del = st.number_input("Escribe el ID que quieres borrar:", min_value=0, step=1)
    if st.button("❌ Borrar Registro"):
        c.execute(f"DELETE FROM {t_name} WHERE id = ?", (id_del,))
        conn.commit()
        st.warning(f"Registro {id_del} eliminado.")
        st.rerun()

# --- 6. GENERAR PDF ---
elif menu == "📄 GENERAR PDF":
    st.title("📄 Informe Mensual V.22")
    mes_sel = st.selectbox("Selecciona el mes:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    
    if st.button("🚀 Crear PDF de Resumen"):
        # Cálculos para el PDF
        p_tot = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
        v_tot = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
        g_tot = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt=f"INFORME CORRAL - {mes_sel.upper()}", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Huevos Recogidos: {p_tot} uds", ln=True)
        pdf.cell(200, 10, txt=f"Ingresos por Ventas: {round(v_tot, 2)} euros", ln=True)
        pdf.cell(200, 10, txt=f"Gastos Totales: {round(g_tot, 2)} euros", ln=True)
        pdf.cell(200, 10, txt=f"SALDO NETO: {round(v_tot - g_tot, 2)} euros", ln=True)
        
        # Generar salida
        pdf_output = pdf.output(dest='S').encode('latin-1')
        st.download_button(label="⬇️ Descargar Informe PDF", data=pdf_output, file_name=f"Informe_{mes_sel}.pdf", mime="application/pdf")

# (Las secciones de REGISTROS y PDF se mantienen iguales a las versiones anteriores)





