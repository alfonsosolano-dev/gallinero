import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL V.24.4 - PRECIOS DINÁMICOS", layout="wide")

# --- CONEXIÓN Y BASE DE DATOS ---
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrada TEXT, especie TEXT, cantidad_inicial INTEGER, precio_compra_ud REAL, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, precio_ud REAL, total REAL, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, cantidad REAL, especie TEXT)''')
    
    # Parche por si falta la columna de precio unitario en lotes
    try:
        c.execute("ALTER TABLE lotes ADD COLUMN precio_compra_ud REAL DEFAULT 0.0")
    except: pass
    conn.commit()

inicializar_db()

# --- FUNCIONES ---
def calcular_dias(fecha_str):
    try:
        f = datetime.strptime(fecha_str, '%d/%m/%Y').date()
        return (datetime.now().date() - f).days
    except: return 0

# --- MENÚ LATERAL ---
st.sidebar.title("🚜 Gestión Pro V.24.4")
menu = st.sidebar.radio("Navegación:", [
    "📊 DASHBOARD DE RENDIMIENTO", 
    "🐣 GESTIÓN DE LOTES",
    "💰 REGISTRAR VENTA", 
    "🥚 PRODUCCIÓN DIARIA", 
    "💸 GASTOS Y SUMINISTROS", 
    "🛠️ MANTENIMIENTO"
])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD DE RENDIMIENTO":
    st.title("📊 Análisis de Eficiencia")
    ing = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas = pd.read_sql("SELECT SUM(importe) as i FROM gastos", conn)['i'].iloc[0] or 0.0
    st.metric("BALANCE NETO", f"{round(ing - gas, 2)} €", delta=f"{round(ing,2)}€ Ingresos")
    st.divider()

    df_lotes = pd.read_sql("SELECT * FROM lotes WHERE estado='Activo'", conn)
    if not df_lotes.empty:
        for _, row in df_lotes.iterrows():
            esp = row['especie']
            dias = calcular_dias(row['fecha_entrada'])
            with st.expander(f"📌 Lote {row['id']}: {esp} ({dias} días)", expanded=True):
                kilos_t = pd.read_sql(f"SELECT SUM(kilos) as k FROM gastos WHERE especie='{esp}'", conn)['k'].iloc[0] or 0.0
                gasto_t = pd.read_sql(f"SELECT SUM(importe) as i FROM gastos WHERE especie='{esp}'", conn)['i'].iloc[0] or 0.0
                ventas_t = pd.read_sql(f"SELECT SUM(total) as v FROM ventas WHERE especie='{esp}'", conn)['v'].iloc[0] or 0.0
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Aves", f"{row['cantidad_inicial']} uds")
                c2.metric("Pienso total", f"{round(kilos_t, 2)} kg")
                if dias > 0:
                    c3.metric("Consumo/Ave/Día", f"{round(kilos_t/(row['cantidad_inicial']*dias),3)} kg")
                c4.metric("Rentabilidad", f"{round(ventas_t - gasto_t, 2)} €")
    else:
        st.info("No hay lotes activos.")

# --- 2. GESTIÓN DE LOTES (PRECIOS DINÁMICOS) ---
elif menu == "🐣 GESTIÓN DE LOTES":
    st.title("🐣 Entrada de Animales con Coste Variable")
    with st.form("nuevo_lote"):
        col1, col2 = st.columns(2)
        f_e = col1.date_input("Fecha de Entrada")
        esp_e = col1.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        cant_e = col2.number_input("Cantidad de Aves", min_value=1, step=1)
        pre_ud = col2.number_input("Precio por cada ave (€)", min_value=0.0, format="%.2f")
        
        coste_total = round(cant_e * pre_ud, 2)
        st.write(f"💰 **Inversión total calculada: {coste_total} €**")
        
        if st.form_submit_button("✅ Registrar Lote y Gasto"):
            fecha_f = f_e.strftime('%d/%m/%Y')
            # 1. Registro Biológico
            c.execute("INSERT INTO lotes (fecha_entrada, especie, cantidad_inicial, precio_compra_ud, estado) VALUES (?,?,?,?,?)",
                      (fecha_f, esp_e, cant_e, pre_ud, 'Activo'))
            # 2. Registro Contable Automático
            concepto_auto = f"Compra {cant_e} {esp_e} a {pre_ud}€/ud"
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)",
                      (fecha_f, concepto_auto, coste_total, "Compra Animales", esp_e, 0.0))
            
            conn.commit()
            st.success(f"Lote creado. Se ha cargado un gasto de {coste_total}€ automáticamente.")

# --- 3. VENTAS ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Terminal de Ventas")
    with st.form("f_v"):
        f_v = st.date_input("Fecha")
        esp_v = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro_v = st.selectbox("Producto", ["HUEVOS", "AVE VIVA", "CARNE"])
        can_v = st.number_input("Cantidad", min_value=1)
        pre_v = st.number_input("Precio Ud (€)", value=0.45 if esp_v=="Gallinas" else 0.15)
        if st.form_submit_button("Guardar Venta"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, precio_ud, total, especie) VALUES (?,?,?,?,?,?,?)",
                      (f_v.strftime('%d/%m/%Y'), "Cliente", pro_v, can_v, pre_v, can_v*pre_v, esp_v))
            conn.commit()
            st.success("Venta guardada.")

# --- 4. PRODUCCIÓN ---
elif menu == "🥚 PRODUCCIÓN DIARIA":
    st.title("🥚 Puesta")
    with st.form("f_p"):
        f_p = st.date_input("Fecha")
        esp_p = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        can_p = st.number_input("Cantidad", min_value=0.0)
        if st.form_submit_button("Guardar"):
            tipo = "HUEVOS" if esp_p != "Pollos" else "ENGORDE"
            c.execute("INSERT INTO produccion (fecha, tipo, cantidad, especie) VALUES (?,?,?,?)",
                      (f_p.strftime('%d/%m/%Y'), tipo, can_p, esp_p))
            conn.commit()
            st.success("Producción registrada.")

# --- 5. GASTOS ---
elif menu == "💸 GASTOS Y SUMINISTROS":
    st.title("💸 Contabilidad de Gastos")
    with st.form("f_g"):
        f_g = st.date_input("Fecha")
        esp_g = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices", "General"])
        cat_g = st.selectbox("Categoría", ["Pienso", "Equipamiento", "Salud", "Otros"])
        con_g = st.text_input("Concepto")
        imp_g = st.number_input("Importe (€)", min_value=0.0)
        kil_g = st.number_input("Kilos de Pienso", min_value=0.0)
        if st.form_submit_button("Guardar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)",
                      (f_g.strftime('%d/%m/%Y'), con_g, imp_g, cat_g, esp_g, kil_g))
            conn.commit()
            st.rerun()

# --- 6. MANTENIMIENTO ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Editor")
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("Borrar"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}")
        conn.commit()
        st.rerun()
