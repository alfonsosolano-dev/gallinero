import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL V.22 - SISTEMA TOTAL", layout="wide")

# --- CONEXIÓN Y LIMPIEZA DE BASE DE DATOS ---
# Si el error persiste, cambia el nombre a 'corral_v23_final.db' en la línea de abajo
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    """Asegura que las tablas tengan todas las columnas necesarias para evitar errores."""
    # Crear tablas base
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, precio_ud REAL, total REAL, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, cantidad REAL, especie TEXT)')
    
    # PARCHE DE SEGURIDAD: Añadir columnas si el archivo es de una versión vieja
    tablas_columnas = {
        'produccion': ['tipo', 'especie'],
        'gastos': ['especie'],
        'ventas': ['especie']
    }
    for tabla, columnas in tablas_columnas.items():
        for col in columnas:
            try:
                c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} TEXT DEFAULT 'General'")
            except sqlite3.OperationalError:
                pass # La columna ya existe
    conn.commit()

inicializar_db()

# --- LÓGICA DE NEGOCIO ---
def obtener_precio_sugerido(prod, esp, fecha_v):
    if esp == "Gallinas" and "HUEVO" in prod.upper():
        # Lógica de precio V.22 (Cambio el 7 de Marzo)
        limite = datetime(2026, 3, 7).date()
        return 0.45 if fecha_v >= limite else 0.3333
    elif esp == "Codornices":
        return 0.15
    return 50.0 # Precio base para pollos o aves vivas

# --- MENÚ LATERAL ---
st.sidebar.title("🚜 Gestión Corral V.22")
menu = st.sidebar.radio("Navegación:", [
    "📊 DASHBOARD ANALÍTICO", 
    "💰 REGISTRAR VENTA", 
    "🥚 PRODUCCIÓN DIARIA", 
    "💸 GASTOS E INVERSIÓN", 
    "📈 HISTÓRICO TOTAL",
    "🛠️ MANTENIMIENTO"
])

# --- 1. DASHBOARD ANALÍTICO ---
if menu == "📊 DASHBOARD ANALÍTICO":
    st.title("📊 Rentabilidad por Especie")
    ing_t = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas_t = pd.read_sql("SELECT SUM(importe) as t FROM gastos", conn)['t'].iloc[0] or 0.0
    
    col_t1, col_t2 = st.columns(2)
    col_t1.metric("SALDO NETO TOTAL", f"{round(ing_t - gas_t, 2)} €")
    col_t2.metric("INGRESOS TOTALES", f"{round(ing_t, 2)} €")
    st.divider()

    especies = ["Gallinas", "Pollos", "Codornices"]
    cols = st.columns(3)
    for i, esp in enumerate(especies):
        with cols[i]:
            st.subheader(f"🏷️ {esp}")
            i_e = pd.read_sql(f"SELECT SUM(total) as t FROM ventas WHERE especie='{esp}'", conn)['t'].iloc[0] or 0.0
            g_e = pd.read_sql(f"SELECT SUM(importe) as t FROM gastos WHERE especie='{esp}'", conn)['t'].iloc[0] or 0.0
            st.metric(f"Beneficio {esp}", f"{round(i_e - g_e, 2)} €")
            
            # Stock de huevos (si no son pollos)
            if esp != "Pollos":
                prod_h = pd.read_sql(f"SELECT SUM(cantidad) as t FROM produccion WHERE especie='{esp}'", conn)['t'].iloc[0] or 0
                vent_h = pd.read_sql(f"SELECT SUM(cantidad) as t FROM ventas WHERE especie='{esp}' AND producto LIKE 'HUEVO%'", conn)['t'].iloc[0] or 0
                st.info(f"Stock actual: {int(prod_h - vent_h)} huevos")

# --- 2. REGISTRAR VENTA ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Nueva Venta")
    with st.form("f_ventas", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            f_v = st.date_input("Fecha", datetime.now())
            esp_v = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
            cli = st.text_input("Cliente")
        with col2:
            pro = st.selectbox("Producto", ["HUEVOS", "AVE VIVA", "CARNE / CANAL"])
            can = st.number_input("Cantidad", min_value=1, step=1)
            p_sug = obtener_precio_sugerido(pro, esp_v, f_v)
            pre = st.number_input("Precio Unidad (€)", value=float(p_sug), format="%.4f")
        
        if st.form_submit_button("✅ Guardar Venta"):
            total_v = can * pre
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, precio_ud, total, especie) VALUES (?,?,?,?,?,?,?)",
                      (f_v.strftime('%d/%m/%Y'), cli, f"{pro} {esp_v}", can, pre, total_v, esp_v))
            conn.commit()
            st.success("Venta guardada correctamente.")

# --- 3. PRODUCCIÓN DIARIA ---
elif menu == "🥚 PRODUCCIÓN DIARIA":
    st.title("🥚 Registro de Producción")
    with st.form("f_prod", clear_on_submit=True):
        f_p = st.date_input("Fecha")
        esp_p = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        
        # Lógica visual para pollos
        if esp_p == "Pollos":
            tipo_p = "ENGORDE/CARNE"
            label = "Peso ganado (kg) o unidades listas"
        else:
            tipo_p = "HUEVOS"
            label = "Cantidad de huevos recogidos"
            
        can_p = st.number_input(label, min_value=0.0, step=1.0)
        
        if st.form_submit_button("💾 Guardar Producción"):
            c.execute("INSERT INTO produccion (fecha, tipo, cantidad, especie) VALUES (?,?,?,?)",
                      (f_p.strftime('%d/%m/%Y'), f"{tipo_p} {esp_p.upper()}", can_p, esp_p))
            conn.commit()
            st.success(f"Datos de {esp_p} registrados.")

# --- 4. GASTOS E INVERSIÓN ---
elif menu == "💸 GASTOS E INVERSIÓN":
    st.title("💸 Registro de Gastos")
    with st.form("f_gastos", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            f_g = st.date_input("Fecha")
            esp_g = st.selectbox("Especie asignada", ["Gallinas", "Pollos", "Codornices", "General"])
            cat_g = st.selectbox("Categoría", ["Pienso", "Animales", "Equipamiento", "Otros"])
        with col2:
            con_g = st.text_input("Concepto")
            imp_g = st.number_input("Importe (€)", min_value=0.0)
            
        if st.form_submit_button("💾 Guardar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)",
                      (f_g.strftime('%d/%m/%Y'), con_g, imp_g, cat_g, esp_g))
            conn.commit()
            st.rerun()
            
    st.subheader("Historial de Gastos")
    st.table(pd.read_sql("SELECT fecha, especie, concepto, importe FROM gastos ORDER BY id DESC LIMIT 10", conn))

# --- 5. HISTÓRICO TOTAL ---
elif menu == "📈 HISTÓRICO TOTAL":
    st.title("📈 Listados Maestros")
    tab1, tab2, tab3 = st.tabs(["Ventas", "Gastos", "Producción"])
    with tab1: st.dataframe(pd.read_sql("SELECT * FROM ventas", conn), use_container_width=True)
    with tab2: st.dataframe(pd.read_sql("SELECT * FROM gastos", conn), use_container_width=True)
    with tab3: st.dataframe(pd.read_sql("SELECT * FROM produccion", conn), use_container_width=True)

# --- 6. MANTENIMIENTO ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Editor de Registros")
    tabla = st.selectbox("Tabla:", ["ventas", "produccion", "gastos"])
    df_m = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    st.dataframe(df_m)
    id_del = st.number_input("ID a borrar:", min_value=0, step=1)
    if st.button("❌ Eliminar Registro"):
        c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_del,))
        conn.commit()
        st.rerun()
