import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from fpdf import FPDF # Necesitarás añadir 'fpdf' a tu requirements.txt

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - INFORMES PDF", layout="wide")

# CONEXIÓN
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# Tablas (Aseguramos que existan)
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY, fecha TEXT, huevos INTEGER, notas TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY, f_muerte TEXT, f_compra TEXT, tipo TEXT, dias INTEGER, total_baja REAL)')
conn.commit()

# --- FUNCIÓN GENERAR PDF ---
def crear_pdf(mes_nombre, datos_resumen):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"INFORME MENSUAL CORRAL - {mes_nombre}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    for k, v in datos_resumen.items():
        pdf.cell(200, 10, txt=f"{k}: {v}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- MENÚ ---
menu = st.sidebar.radio("MENÚ", ["📊 DASHBOARD", "🥚 PRODUCCIÓN", "💸 GASTOS", "💰 VENTAS", "📄 GENERAR INFORME PDF"])

# --- SECCIÓN NUEVA: GENERAR INFORME PDF ---
if menu == "📄 GENERAR INFORME PDF":
    st.title("📄 Exportar Informe Mensual")
    mes_sel = st.selectbox("Selecciona el mes para el informe", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    
    # Recopilación de datos para el PDF
    prod_mes = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    ventas_mes = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gastos_mes = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    
    resumen = {
        "Total Huevos Recogidos": f"{prod_mes} unidades",
        "Ingresos por Ventas": f"{round(ventas_mes, 2)} euros",
        "Gastos Totales": f"{round(gastos_mes, 2)} euros",
        "Beneficio Neto Estimado": f"{round(ventas_mes - gastos_mes, 2)} euros"
    }
    
    if st.button("Generar Informe PDF"):
        pdf_bytes = crear_pdf(mes_sel.upper(), resumen)
        st.download_button(label="⬇️ Descargar PDF", data=pdf_bytes, file_name=f"Informe_{mes_sel}.pdf", mime="application/pdf")

# --- SECCIÓN GASTOS (Para que no la veas vacía) ---
elif menu == "💸 GASTOS":
    st.subheader("💸 Registro de Gastos")
    with st.form("gasto_nuevo"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Veterinaria", "Inversión", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("Guardar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat))
            conn.commit()
            st.success("Gasto anotado correctamente")
    
    st.write("### Histórico de Gastos")
    df_g = pd.read_sql("SELECT * FROM gastos ORDER BY id DESC", conn)
    st.dataframe(df_g, use_container_width=True)

# (El resto de secciones se mantienen igual que en la versión anterior)
