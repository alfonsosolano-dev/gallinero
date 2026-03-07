import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL V.24 - ELITE CONTROL", layout="wide")

# --- CONEXIÓN Y BASE DE DATOS (v24 con soporte de Kilos y Lotes) ---
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrada TEXT, especie TEXT, cantidad_inicial INTEGER, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, precio_ud REAL, total REAL, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, cantidad REAL, especie TEXT)''')
    conn.commit()

inicializar_db()

# --- FUNCIONES DE CÁLCULO ---
def calcular_dias(fecha_str):
    try:
        f = datetime.strptime(fecha_str, '%d/%m/%Y').date()
        return (datetime.now().date() - f).days
    except: return 0

# --- MENÚ LATERAL ---
st.sidebar.title("🚜 Gestión Pro V.24")
menu = st.sidebar.radio("Navegación:", [
    "📊 DASHBOARD DE RENDIMIENTO", 
    "🐣 GESTIÓN DE LOTES",
    "💰 REGISTRAR VENTA", 
    "🥚 PRODUCCIÓN DIARIA", 
    "💸 GASTOS Y SUMINISTROS", 
    "🛠️ MANTENIMIENTO"
])

# --- 1. DASHBOARD DE RENDIMIENTO ---
if menu == "📊 DASHBOARD DE RENDIMIENTO":
    st.title("📊 Rendimiento y Eficiencia por Lote")
    
    # Balance Rápido
    ing = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas = pd.read_sql("SELECT SUM(importe) as t FROM gastos", conn)['t'].iloc[0] or 0.0
    st.metric("BALANCE NETO TOTAL", f"{round(ing - gas, 2)} €", delta=f"{round(ing,2)}€ Ingresos")
    st.divider()

    # Análisis de Lotes Activos
    df_lotes = pd.read_sql("SELECT * FROM lotes WHERE estado='Activo'", conn)
    if not df_lotes.empty:
        for idx, row in df_lotes.iterrows():
            esp = row['especie']
            dias = calcular_dias(row['fecha_entrada'])
            
            with st.expander(f"📌 Lote {row['id']}: {esp} ({dias} días de vida)", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                
                # Cálculo de Pienso para esta especie
                kilos_t = pd.read_sql(f"SELECT SUM(kilos) as k FROM gastos WHERE especie='{esp}'", conn)['k'].iloc[0] or 0.0
                gasto_t = pd.read_sql(f"SELECT SUM(importe) as i FROM gastos WHERE especie='{esp}'", conn)['i'].iloc[0] or 0.0
                ventas_t = pd.read_sql(f"SELECT SUM(total) as v FROM ventas WHERE especie='{esp}'", conn)['v'].iloc[0] or 0.0
                
                col1.metric("Aves Iniciales", f"{row['cantidad_inicial']} uds")
                col2.metric("Pienso Consumido", f"{round(kilos_t, 2)} kg")
                
                if dias > 0 and row['cantidad_inicial'] > 0:
                    fcr = round(kilos_t / (row['cantidad_inicial'] * dias), 3)
                    col3.metric("Consumo Diario/Ave", f"{fcr} kg")
                
                col4.metric("Rentabilidad Lote", f"{round(ventas_t - gasto_t, 2)} €")
    else:
        st.warning("No hay lotes activos. Inicia uno en la pestaña de GESTIÓN DE LOTES.")

# --- 2. GESTIÓN DE LOTES ---
elif menu == "🐣 GESTIÓN DE LOTES":
    st.title("🐣 Control de Entradas y Bajas")
    with st.form("nuevo_lote"):
        c1, c2 = st.columns(2)
        f_e = c1.date_input("Fecha de Entrada")
        esp_e = c1.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        cant_e = c2.number_input("Cantidad de Aves", min_value=1)
        if st.form_submit_button("✅ Registrar Nuevo Lote"):
            c.execute("INSERT INTO lotes (fecha_entrada, especie, cantidad_inicial, estado) VALUES (?,?,?,?)",
                      (f_e.strftime('%d/%m/%Y'), esp_e, cant_e, 'Activo'))
            conn.commit()
            st.success("Lote activado.")
    
    st.subheader("Historial de Lotes")
    st.dataframe(pd.read_sql("SELECT * FROM lotes", conn), use_container_width=True)

# --- 3. REGISTRAR VENTA ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Terminal de Ventas")
    with st.form("f_v"):
        c1, c2 = st.columns(2)
        f_v = c1.date_input("Fecha")
        esp_v = c1.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro_v = c2.selectbox("Producto", ["HUEVOS", "AVE VIVA", "CARNE / CANAL"])
        can_v = c2.number_input("Cantidad", min_value=1)
        pre_v = c2.number_input("Precio Unidad (€)", value=0.45 if esp_v=="Gallinas" else 0.15)
        if st.form_submit_button("✅ Guardar Venta"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, precio_ud, total, especie) VALUES (?,?,?,?,?,?,?)",
                      (f_v.strftime('%d/%m/%Y'), "Cliente Final", pro_v, can_v, pre_v, can_v*pre_v, esp_v))
            conn.commit()
            st.success("Venta procesada.")

# --- 4. PRODUCCIÓN DIARIA ---
elif menu == "🥚 PRODUCCIÓN DIARIA":
    st.title("🥚 Parte de Producción")
    with st.form("f_p"):
        f_p = st.date_input("Fecha")
        esp_p = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        tipo_p = "HUEVOS" if esp_p != "Pollos" else "ENGORDE"
        can_p = st.number_input("Cantidad (Uds / Kg)", min_value=0.0)
        if st.form_submit_button("💾 Guardar"):
            c.execute("INSERT INTO produccion (fecha, tipo, cantidad, especie) VALUES (?,?,?,?)",
                      (f_p.strftime('%d/%m/%Y'), tipo_p, can_p, esp_p))
            conn.commit()
            st.success("Datos guardados.")

# --- 5. GASTOS Y SUMINISTROS ---
elif menu == "💸 GASTOS Y SUMINISTROS":
    st.title("💸 Registro de Gastos y Pienso")
    with st.form("f_g"):
        c1, c2 = st.columns(2)
        f_g = c1.date_input("Fecha")
        esp_g = c1.selectbox("Especie Beneficiaria", ["Gallinas", "Pollos", "Codornices", "General"])
        cat_g = c2.selectbox("Categoría", ["Pienso", "Compra Animales", "Equipamiento", "Salud"])
        con_g = c2.text_input("Concepto / Marca")
        imp_g = c1.number_input("Importe (€)", min_value=0.0)
        kil_g = c2.number_input("Kilos de Pienso (si aplica)", min_value=0.0)
        if st.form_submit_button("💾 Registrar"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)",
                      (f_g.strftime('%d/%m/%Y'), con_g, imp_g, cat_g, esp_g, kil_g))
            conn.commit()
            st.success("Gasto anotado.")

# --- 6. MANTENIMIENTO ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Gestión de Datos")
    t = st.selectbox("Seleccionar Tabla:", ["lotes", "ventas", "produccion", "gastos"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0, step=1)
    if st.button("❌ Borrar Registro"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}")
        conn.commit()
        st.rerun()
