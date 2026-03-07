import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL V.22 - LÓGICA BIOLÓGICA", layout="wide")

# --- CONEXIÓN Y MANTENIMIENTO DE BASE DE DATOS ---
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_sistema():
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, precio_ud REAL, total REAL, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, cantidad REAL, especie TEXT)''')
    
    # Parche por si las moscas
    for t in ['gastos', 'ventas', 'produccion']:
        try:
            c.execute(f"ALTER TABLE {t} ADD COLUMN especie TEXT DEFAULT 'General'")
        except:
            pass
    conn.commit()

inicializar_sistema()

# --- LÓGICA DE PRECIOS ---
def sugerir_precio(producto, especie, fecha_sel):
    if especie == "Gallinas" and "HUEVO" in producto.upper():
        limite = datetime(2026, 3, 7).date()
        return 0.45 if fecha_sel >= limite else 0.3333
    elif especie == "Codornices":
        return 0.15
    elif especie == "Pollos":
        return 50.0 # Precio por pollo vendido
    return 1.0

# --- MENÚ LATERAL ---
st.sidebar.title("🚜 Gestión V.22")
menu = st.sidebar.radio("Menú Principal:", [
    "📊 DASHBOARD ANALÍTICO", 
    "💰 REGISTRAR VENTA", 
    "🥚 PRODUCCIÓN DIARIA", 
    "💸 GASTOS E INVERSIÓN", 
    "📈 HISTÓRICO DETALLADO",
    "🛠️ MANTENIMIENTO"
])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD ANALÍTICO":
    st.title("📊 Análisis de Rentabilidad")
    ing_t = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas_t = pd.read_sql("SELECT SUM(importe) as t FROM gastos", conn)['t'].iloc[0] or 0.0
    
    col_g1, col_g2 = st.columns(2)
    col_g1.metric("SALDO NETO TOTAL", f"{round(ing_t - gas_t, 2)} €")
    col_g2.metric("INGRESOS ACUMULADOS", f"{round(ing_t, 2)} €")
    
    st.divider()
    especies = ["Gallinas", "Pollos", "Codornices"]
    cols = st.columns(3)
    
    for i, esp in enumerate(especies):
        with cols[i]:
            st.subheader(f"🏷️ {esp}")
            i_esp = pd.read_sql(f"SELECT SUM(total) as t FROM ventas WHERE especie='{esp}'", conn)['t'].iloc[0] or 0.0
            g_esp = pd.read_sql(f"SELECT SUM(importe) as t FROM gastos WHERE especie='{esp}'", conn)['t'].iloc[0] or 0.0
            st.metric("Beneficio", f"{round(i_esp - g_esp, 2)} €")
            
            if esp != "Pollos":
                p_h = pd.read_sql(f"SELECT SUM(cantidad) as t FROM produccion WHERE especie='{esp}'", conn)['t'].iloc[0] or 0
                v_h = pd.read_sql(f"SELECT SUM(cantidad) as t FROM ventas WHERE especie='{esp}' AND producto LIKE 'HUEVO%'", conn)['t'].iloc[0] or 0
                st.info(f"Stock: {int(p_h - v_h)} huevos")
            else:
                st.write("Sección de engorde")

# --- 2. VENTAS ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Nueva Venta")
    with st.form("form_ventas", clear_on_submit=True):
        f_v = st.date_input("Fecha", datetime.now())
        esp_v = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        # Productos adaptados a la especie
        opciones_prod = ["HUEVOS", "AVE VIVA", "CARNE"] if esp_v != "Pollos" else ["POLLO ENTERO", "CANAL (kg)"]
        pro = st.selectbox("Producto", opciones_prod)
        can = st.number_input("Cantidad", min_value=1, step=1)
        p_sug = sugerir_precio(pro, esp_v, f_v)
        pre = st.number_input("Precio Unidad (€)", value=float(p_sug), format="%.4f")
        
        if st.form_submit_button("✅ Guardar Venta"):
            total_v = can * pre
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, precio_ud, total, especie) VALUES (?,?,?,?,?,?,?)", 
                      (f_v.strftime('%d/%m/%Y'), "Cliente", f"{pro} {esp_v}", can, pre, total_v, esp_v))
            conn.commit()
            st.success("Venta guardada.")

# --- 3. PRODUCCIÓN (CORREGIDA) ---
elif menu == "🥚 PRODUCCIÓN DIARIA":
    st.title("🥚 Registro de Producción")
    with st.form("form_prod", clear_on_submit=True):
        f_p = st.date_input("Fecha")
        esp_p = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        
        if esp_p == "Pollos":
            st.write("📊 **Registro de Engorde de Pollos**")
            tipo_p = "CRECIMIENTO/CARNE"
            label_cant = "Peso ganado total del lote (kg) o Unidades listas"
        else:
            st.write("🥚 **Registro de Puesta**")
            tipo_p = "HUEVOS"
            label_cant = "Cantidad de huevos recogidos"
            
        can_p = st.number_input(label_cant, min_value=0.0, step=1.0)
        
        if st.form_submit_button("💾 Guardar Datos"):
            c.execute("INSERT INTO produccion (fecha, tipo, cantidad, especie) VALUES (?,?,?,?)", 
                      (f_p.strftime('%d/%m/%Y'), f"{tipo_p} {esp_p.upper()}", can_p, esp_p))
            conn.commit()
            st.success(f"Datos de {esp_p} guardados correctamente.")

# --- 4. GASTOS ---
elif menu == "💸 GASTOS E INVERSIÓN":
    st.title("💸 Control de Gastos")
    with st.form("form_gastos", clear_on_submit=True):
        f_g = st.date_input("Fecha")
        esp_g = st.selectbox("Asignar a:", ["Gallinas", "Pollos", "Codornices", "General"])
        cat_g = st.selectbox("Categoría", ["Pienso", "Compra Animales", "Equipamiento", "Otros"])
        con_g = st.text_input("Concepto")
        imp_g = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("💾 Guardar"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", 
                      (f_g.strftime('%d/%m/%Y'), con_g, imp_g, cat_g, esp_g))
            conn.commit()
            st.rerun()
    st.table(pd.read_sql("SELECT fecha, especie, concepto, importe FROM gastos ORDER BY id DESC LIMIT 10", conn))

# --- 5. HISTÓRICO ---
elif menu == "📈 HISTÓRICO DETALLADO":
    st.title("📈 Listados")
    tab1, tab2, tab3 = st.tabs(["Ventas", "Gastos", "Producción"])
    with tab1: st.dataframe(pd.read_sql("SELECT * FROM ventas", conn))
    with tab2: st.dataframe(pd.read_sql("SELECT * FROM gastos", conn))
    with tab3: st.dataframe(pd.read_sql("SELECT * FROM produccion", conn))

# --- 6. MANTENIMIENTO ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Editor")
    tabla = st.selectbox("Tabla:", ["ventas", "produccion", "gastos"])
    df_m = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    st.dataframe(df_m)
    id_del = st.number_input("ID a borrar:", min_value=0, step=1)
    if st.button("❌ Eliminar"):
        c.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_del,))
        conn.commit()
        st.rerun()
