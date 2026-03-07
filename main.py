import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL V.22 - SISTEMA INTEGRAL", layout="wide")

# CONEXIÓN SEGURO A BASE DE DATOS
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# 1. ASEGURAR TODAS LAS TABLAS (Estructura Completa)
c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, precio_ud REAL, total REAL)')
c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, huevos INTEGER)')
conn.commit()

# --- CARGA AUTOMÁTICA DE GASTOS INICIALES (Solo si está vacío) ---
c.execute("SELECT count(*) FROM gastos")
if c.fetchone()[0] == 0:
    gastos_base = [
        ('02/02/2026', 'Equipo Total (Inversión Inicial)', 62.0, 'Inversión'),
        ('21/02/2026', '7 Gallinas', 52.0, 'Inversión'),
        ('21/02/2026', '4 Pollos', 10.0, 'Inversión'),
        ('10/03/2026', 'Gallina Parda', 8.5, 'Inversión'),
        ('15/03/2026', 'Pienso y Nutrición', 33.25, 'Pienso')
    ]
    c.executemany("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", gastos_base)
    conn.commit()

# --- FUNCIONES DE LÓGICA ---
def get_precio_sugerido(producto, fecha_sel):
    if producto == "HUEVOS":
        limite = datetime(2026, 3, 7).date()
        return 0.45 if fecha_sel >= limite else 0.3333
    return 50.0

def calcular_coste_pollo_estimado():
    # Inversión (2.50) + Pienso diario (0.07 * 90 días aprox)
    return 2.50 + (90 * 0.07)

# --- MENÚ LATERAL ---
st.sidebar.title("🚜 Gestión Corral V.22")
menu = st.sidebar.radio("Ir a:", [
    "📊 DASHBOARD", 
    "💰 REGISTRAR VENTA", 
    "🥚 PRODUCCIÓN DIARIA", 
    "💸 GASTOS E INVERSIÓN", 
    "📈 HISTÓRICO Y EVOLUCIÓN",
    "🛠️ MANTENIMIENTO"
])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Resumen General de Situación")
    ing = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gas = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    prod = pd.read_sql("SELECT SUM(huevos) FROM produccion", conn).iloc[0,0] or 0
    vend = pd.read_sql("SELECT SUM(cantidad) FROM ventas WHERE producto='HUEVOS'", conn).iloc[0,0] or 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("SALDO NETO REAL", f"{round(ing - gas, 2)} €")
    col2.metric("HUEVOS EN STOCK", f"{int(prod - vend)} uds")
    col3.metric("INGRESOS TOTALES", f"{round(ing, 2)} €")
    
    st.divider()
    st.subheader("Distribución de Gastos")
    df_gastos_pie = pd.read_sql("SELECT categoria, SUM(importe) as total FROM gastos GROUP BY categoria", conn)
    if not df_gastos_pie.empty:
        st.bar_chart(df_gastos_pie.set_index('categoria'))

# --- 2. REGISTRAR VENTA (PRECIO MANUAL) ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Formulario de Ventas")
    with st.form("f_ventas", clear_on_submit=True):
        f_v = st.date_input("Fecha", datetime.now())
        cli = st.text_input("Nombre del Cliente")
        pro = st.selectbox("Producto", ["HUEVOS", "POLLO"])
        can = st.number_input("Cantidad", min_value=1, step=1)
        
        pre_sug = get_precio_sugerido(pro, f_v)
        pre_final = st.number_input("Precio Unitario (€) - Editable", value=float(pre_sug), format="%.4f")
        
        if pro == "POLLO":
            coste_p = calcular_coste_pollo_estimado()
            st.info(f"💡 Coste de crianza estimado: {coste_p}€ | Margen: {round(pre_final - coste_p, 2)}€")
            
        if st.form_submit_button("✅ Registrar Venta"):
            total_v = can * pre_final
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, precio_ud, total) VALUES (?,?,?,?,?,?)", 
                      (f_v.strftime('%d/%m/%Y'), cli, pro, can, pre_final, total_v))
            conn.commit()
            st.success(f"Venta guardada: {total_v}€")

# --- 3. PRODUCCIÓN DIARIA ---
elif menu == "🥚 PRODUCCIÓN DIARIA":
    st.title("🥚 Registro de Puesta")
    with st.form("f_prod", clear_on_submit=True):
        f_p = st.date_input("Fecha")
        h_p = st.number_input("Huevos recogidos", min_value=0, step=1)
        if st.form_submit_button("💾 Guardar"):
            c.execute("INSERT INTO produccion (fecha, huevos) VALUES (?,?)", (f_p.strftime('%d/%m/%Y'), h_p))
            conn.commit()
            st.success("Producción anotada correctamente.")

# --- 4. GASTOS E INVERSIÓN ---
elif menu == "💸 GASTOS E INVERSIÓN":
    st.title("💸 Gestión de Salidas de Dinero")
    with st.form("f_gastos", clear_on_submit=True):
        f_g = st.date_input("Fecha")
        cat_g = st.selectbox("Categoría", ["Pienso", "Inversión", "Otros"])
        con_g = st.text_input("Concepto (Ej: Saco 25kg, 3 Gallinas...)")
        imp_g = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("💾 Registrar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria) VALUES (?,?,?,?)", 
                      (f_g.strftime('%d/%m/%Y'), con_g, imp_g, cat_g))
            conn.commit()
            st.rerun()
    
    st.subheader("Historial de Gastos")
    df_g_list = pd.read_sql("SELECT id, fecha, concepto, importe, categoria FROM gastos ORDER BY id DESC", conn)
    st.table(df_g_list)

# --- 5. HISTÓRICO Y EVOLUCIÓN ---
elif menu == "📈 HISTÓRICO Y EVOLUCIÓN":
    st.title("📈 Análisis de Datos")
    t1, t2 = st.tabs(["Histórico Ventas", "Evolución Producción"])
    with t1:
        df_v_hist = pd.read_sql("SELECT * FROM ventas ORDER BY id ASC", conn)
        st.dataframe(df_v_hist, use_container_width=True)
    with t2:
        df_p_hist = pd.read_sql("SELECT fecha, huevos FROM produccion ORDER BY id ASC", conn)
        if not df_p_hist.empty:
            st.line_chart(df_p_hist.set_index('fecha'))
        st.dataframe(df_p_hist, use_container_width=True)

# --- 6. MANTENIMIENTO (BORRADO) ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Editor de Registros")
    tab_sel = st.selectbox("Tabla a gestionar:", ["ventas", "produccion", "gastos"])
    df_man = pd.read_sql(f"SELECT * FROM {tab_sel} ORDER BY id DESC", conn)
    st.dataframe(df_man, use_container_width=True)
    id_del = st.number_input("ID del registro a borrar:", min_value=0, step=1)
    if st.button("❌ Eliminar Permanentemente"):
        c.execute(f"DELETE FROM {tab_sel} WHERE id = ?", (id_del,))
        conn.commit()
        st.warning(f"ID {id_del} borrado.")
        st.rerun()
