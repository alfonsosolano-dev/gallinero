import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL V.24.7 - ANALÍTICA & CASA", layout="wide")

# --- CONEXIÓN Y BASE DE DATOS ---
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL, destino TEXT)''')
    conn.commit()

inicializar_db()

# --- NAVEGACIÓN ---
st.sidebar.title("🚜 Gestión Pro V.24.7")
menu = st.sidebar.radio("Menú:", ["📊 DASHBOARD GENERAL", "🐣 GESTIÓN DE LOTES", "💰 VENTAS", "🥚 PRODUCCIÓN Y CASA", "💸 GASTOS", "🛠️ DATOS"])

# --- 1. DASHBOARD GENERAL & POR ESPECIE ---
if menu == "📊 DASHBOARD GENERAL":
    st.title("📊 Contabilidad y Rendimiento")
    
    # --- CONTABILIDAD GENERAL ---
    ing_t = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas_t = pd.read_sql("SELECT SUM(importe) as i FROM gastos", conn)['i'].iloc[0] or 0.0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("INGRESOS TOTALES", f"{round(ing_t, 2)} €")
    c2.metric("GASTOS TOTALES", f"{round(gas_t, 2)} €")
    c3.metric("BENEFICIO NETO", f"{round(ing_t - gas_t, 2)} €", delta=f"{round(ing_t - gas_t, 2)} €")

    st.divider()

    # --- CONTABILIDAD POR ESPECIE (TABLA DE RENTABILIDAD) ---
    st.subheader("🎯 Rentabilidad por Especie")
    especies = ["Gallinas", "Pollos", "Codornices"]
    data_esp = []
    
    for e in especies:
        v_e = pd.read_sql(f"SELECT SUM(total) as t FROM ventas WHERE especie='{e}'", conn)['t'].iloc[0] or 0.0
        g_e = pd.read_sql(f"SELECT SUM(importe) as i FROM gastos WHERE especie='{e}'", conn)['i'].iloc[0] or 0.0
        ahorro_casa = pd.read_sql(f"SELECT SUM(cantidad) as c FROM produccion WHERE especie='{e}' AND destino='Casa'", conn)['c'].iloc[0] or 0.0
        
        data_esp.append({
            "Especie": e,
            "Ingresos (€)": round(v_e, 2),
            "Gastos (€)": round(g_e, 2),
            "Resultado (€)": round(v_e - g_e, 2),
            "Consumo Casa (Uds)": ahorro_casa
        })
    
    st.table(pd.DataFrame(data_esp))

    # --- GRÁFICOS ---
    st.subheader("📈 Evolución de Producción")
    df_p = pd.read_sql("SELECT fecha, cantidad FROM produccion", conn)
    if not df_p.empty:
        df_p['fecha'] = pd.to_datetime(df_p['fecha'], format='%d/%m/%Y')
        st.line_chart(df_p.set_index('fecha'))

# --- 2. GESTIÓN DE LOTES (AUTOMATIZADO) ---
elif menu == "🐣 GESTIÓN DE LOTES":
    st.title("🐣 Nuevo Lote de Animales")
    with st.form("f_lote", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        esp = col1.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        cant = col2.number_input("Cantidad", min_value=1)
        pre = col2.number_input("Precio por animal (€)", min_value=0.0)
        if st.form_submit_button("✅ REGISTRAR"):
            total_g = cant * pre
            fecha_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (fecha_s, esp, cant, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)", 
                      (fecha_s, f"Compra {cant} {esp}", total_g, "Animales", esp, 0.0))
            conn.commit()
            st.success(f"✅ Registrado: {cant} {esp}. Gasto de {total_g}€ añadido a {esp}.")

# --- 3. VENTAS ---
elif menu == "💰 VENTAS":
    st.title("💰 Registrar Venta")
    with st.form("f_v", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie de origen", ["Gallinas", "Pollos", "Codornices"])
        pro = st.text_input("Producto (ej: Huevos docena)")
        can = st.number_input("Cantidad vendida", min_value=1)
        tot = st.number_input("Total cobrado (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, especie) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), pro, can, tot, esp))
            conn.commit()
            st.success(f"✅ Venta de {esp} guardada correctamente.")

# --- 4. PRODUCCIÓN Y CONSUMO DE CASA ---
elif menu == "🥚 PRODUCCIÓN Y CASA":
    st.title("🥚 Producción Diaria / Autoconsumo")
    st.info("Aquí registras lo que recojas. Si es para casa, no sumará dinero pero sí se contará en estadísticas.")
    with st.form("f_p", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        can = st.number_input("Cantidad (Huevos o Kg)", min_value=0.0)
        dest = st.radio("Destino:", ["Venta / Almacén", "Casa"], horizontal=True)
        if st.form_submit_button("✅ REGISTRAR PRODUCCIÓN"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad, destino) VALUES (?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), esp, can, dest))
            conn.commit()
            st.success(f"✅ {can} unidades de {esp} registradas para {dest}.")

# --- 5. GASTOS ---
elif menu == "💸 GASTOS":
    st.title("💸 Gastos Manuales")
    with st.form("f_g", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Asignar a especie:", ["Gallinas", "Pollos", "Codornices", "General"])
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipamiento", "Luz/Agua"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        kil = st.number_input("Si es pienso, ¿cuántos kilos?", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, esp, kil))
            conn.commit()
            st.success(f"✅ Gasto de {imp}€ asignado a {esp}.")

# --- 6. MANTENIMIENTO ---
elif menu == "🛠️ DATOS":
    st.title("🛠️ Editor de datos")
    t = st.selectbox("Ver tabla:", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}")
        conn.commit()
        st.rerun()
