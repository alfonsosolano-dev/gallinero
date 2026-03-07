import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.22 - DATOS CARGADOS", layout="wide")

# CONEXIÓN
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# ASEGURAR TABLAS
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
conn.commit()

# --- CARGA AUTOMÁTICA DE TUS DATOS V.22 ---
# (Solo se graban si la tabla está vacía para no duplicar)
c.execute("SELECT count(*) FROM gastos")
if c.fetchone()[0] == 0:
    gastos_iniciales = [
        ('02/02/2026', 'Equipo Total (Inversión Inicial)', 62.0, 'Inversión'),
        ('21/02/2026', '7 Gallinas', 52.0, 'Inversión'),
        ('21/02/2026', '4 Pollos', 10.0, 'Inversión'),
        ('10/03/2026', 'Gallina Parda', 8.5, 'Inversión'),
        ('15/03/2026', 'Pienso y Nutrición', 33.25, 'Pienso') # Incluye los 15€ que comentamos
    ]
    c.executemany("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", gastos_iniciales)
    conn.commit()

# --- MENÚ ---
menu = st.sidebar.radio("MENÚ", ["📊 RESUMEN FINANCIERO", "💸 LISTADO GASTOS", "➕ NUEVO GASTO"])

if menu == "📊 RESUMEN FINANCIERO":
    st.title("📊 Balance de Gastos V.22")
    
    # Resumen por categoría
    df_cat = pd.read_sql("SELECT categoria, SUM(importe) as total FROM gastos GROUP BY categoria", conn)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Totales por tipo")
        st.table(df_cat)
    
    with col2:
        total_g = df_cat['total'].sum()
        st.metric("GASTO TOTAL ACUMULADO", f"{round(total_g, 2)} €")
        st.info("Este balance coincide con los 165.75€ de tu base V.22.")

elif menu == "💸 LISTADO GASTOS":
    st.title("💸 Histórico Detallado")
    df_lista = pd.read_sql("SELECT id, fecha, concepto, importe, categoria FROM gastos ORDER BY id ASC", conn)
    st.dataframe(df_lista, use_container_width=True)
    
    # Opción de borrado por si quieres limpiar los datos de prueba
    st.divider()
    id_borrar = st.number_input("Si quieres borrar un gasto, pon su ID aquí:", min_value=0, step=1)
    if st.button("❌ Borrar Registro"):
        c.execute(f"DELETE FROM gastos WHERE id = ?", (id_borrar,))
        conn.commit()
        st.rerun()

elif menu == "➕ NUEVO GASTO":
    st.title("➕ Añadir Gasto Real")
    with st.form("nuevo_gasto"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Inversión", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("Guardar"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), con, imp, cat))
            conn.commit()
            st.success("Gasto guardado correctamente")
