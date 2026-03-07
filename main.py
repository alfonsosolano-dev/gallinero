import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="CORRAL V.22 - CONTROL ANALÍTICO", layout="wide")

# CONEXIÓN Y ESTRUCTURA DE TABLAS
conn = sqlite3.connect('corral_v22_final.db', check_same_thread=False)
c = conn.cursor()

# Asegurar que las tablas tengan todas las columnas necesarias para la analítica
c.execute('''CREATE TABLE IF NOT EXISTS gastos 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS ventas 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, precio_ud REAL, total REAL, especie TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS produccion 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, cantidad INTEGER, especie TEXT)''')
conn.commit()

# --- LÓGICA DE PRECIOS SUGERIDOS ---
def get_precio_sugerido(prod_input, fecha_sel):
    p = prod_input.upper()
    if "HUEVO" in p and "GALLINA" in p:
        return 0.45 if fecha_sel >= datetime(2026, 3, 7).date() else 0.3333
    elif "HUEVO" in p and "CODORNIZ" in p:
        return 0.15
    elif "POLLO" in p or "CARNE" in p:
        return 50.0
    return 1.0

# --- MENÚ LATERAL ---
st.sidebar.title("🚜 Panel de Control V.22")
menu = st.sidebar.radio("Navegación:", [
    "📊 DASHBOARD ANALÍTICO", 
    "💰 REGISTRAR VENTA", 
    "🥚 PRODUCCIÓN DIARIA", 
    "💸 GASTOS E INVERSIÓN", 
    "📈 HISTÓRICO TOTAL",
    "🛠️ MANTENIMIENTO"
])

# --- 1. DASHBOARD ANALÍTICO (Rendimiento por Especie) ---
if menu == "📊 DASHBOARD ANALÍTICO":
    st.title("📊 Rentabilidad Comparada")
    
    # Datos globales
    ing_t = pd.read_sql("SELECT SUM(total) FROM ventas", conn).iloc[0,0] or 0.0
    gas_t = pd.read_sql("SELECT SUM(importe) FROM gastos", conn).iloc[0,0] or 0.0
    
    col_t1, col_t2 = st.columns(2)
    col_t1.metric("SALDO NETO TOTAL", f"{round(ing_t - gas_t, 2)} €")
    col_t2.metric("TOTAL INGRESOS", f"{round(ing_t, 2)} €")
    
    st.divider()
    
    # Desglose por Especie
    especies = ["Gallinas", "Pollos", "Codornices"]
    cols = st.columns(3)
    
    for i, esp in enumerate(especies):
        with cols[i]:
            st.subheader(f"🏷️ {esp}")
            i_esp = pd.read_sql(f"SELECT SUM(total) FROM ventas WHERE especie='{esp}'", conn).iloc[0,0] or 0.0
            g_esp = pd.read_sql(f"SELECT SUM(importe) FROM gastos WHERE especie='{esp}'", conn).iloc[0,0] or 0.0
            
            # Cálculo de stock de huevos si aplica
            p_esp = pd.read_sql(f"SELECT SUM(cantidad) FROM produccion WHERE especie='{esp}' AND tipo LIKE 'HUEVO%'", conn).iloc[0,0] or 0
            v_esp = pd.read_sql(f"SELECT SUM(cantidad) FROM ventas WHERE especie='{esp}' AND producto LIKE 'HUEVO%'", conn).iloc[0,0] or 0
            
            st.metric("Beneficio", f"{round(i_esp - g_esp, 2)} €")
            st.write(f"**Ingresos:** {round(i_esp, 2)}€")
            st.write(f"**Gastos:** {round(g_esp, 2)}€")
            if esp != "Pollos":
                st.write(f"**Stock Huevos:** {int(p_esp - v_esp)} uds")

# --- 2. REGISTRAR VENTA ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Registrar Venta")
    with st.form("f_ventas", clear_on_submit=True):
        f_v = st.date_input("Fecha", datetime.now())
        esp_v = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        tipo_v = st.selectbox("Producto", ["HUEVOS", "CARNE / AVE VIVA"])
        cli = st.text_input("Cliente")
        can = st.number_input("Cantidad", min_value=1, step=1)
        
        nombre_prod = f"{tipo_v} {esp_v.upper()}"
        pre_sug = get_precio_sugerido(nombre_prod, f_v)
        pre_final = st.number_input("Precio Unidad (€)", value=float(pre_sug), format="%.4f")
        
        if st.form_submit_button("✅ Guardar Venta"):
            total_v = can * pre_final
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, precio_ud, total, especie) VALUES (?,?,?,?,?,?,?)", 
                      (f_v.strftime('%d/%m/%Y'), cli, nombre_prod, can, pre_final, total_v, esp_v))
            conn.commit()
            st.success(f"Venta de {nombre_prod} anotada.")

# --- 3. PRODUCCIÓN DIARIA ---
elif menu == "🥚 PRODUCCIÓN DIARIA":
    st.title("🥚 Producción Diaria")
    with st.form("f_prod", clear_on_submit=True):
        f_p = st.date_input("Fecha")
        esp_p = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        tipo_p = st.selectbox("Tipo", ["HUEVOS", "PESO CARNE (kg)", "UNIDADES"])
        cant_p = st.number_input("Cantidad", min_value=0, step=1)
        
        if st.form_submit_button("💾 Guardar"):
            nombre_p = f"{tipo_p} {esp_p.upper()}"
            c.execute("INSERT INTO produccion (fecha, tipo, cantidad, especie) VALUES (?,?,?,?)", 
                      (f_p.strftime('%d/%m/%Y'), nombre_p, cant_p, esp_p))
            conn.commit()
            st.success(f"Registrado: {cant_p} {nombre_p}")

# --- 4. GASTOS E INVERSIÓN ---
elif menu == "💸 GASTOS E INVERSIÓN":
    st.title("💸 Control de Gastos")
    with st.form("f_gastos", clear_on_submit=True):
        f_g = st.date_input("Fecha")
        esp_g = st.selectbox("Asignar a:", ["Gallinas", "Pollos", "Codornices", "General"])
        cat_g = st.selectbox("Categoría", ["Pienso", "Compra Animales", "Equipamiento", "Otros"])
        con_g = st.text_input("Concepto")
        imp_g = st.number_input("Importe (€)", min_value=0.0)
        
        if st.form_submit_button("💾 Guardar Gasto"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", 
                      (f_g.strftime('%d/%m/%Y'), con_g, imp_g, cat_g, esp_g))
            conn.commit()
            st.success("Gasto registrado.")
    
    st.subheader("Últimos Movimientos")
    df_g = pd.read_sql("SELECT fecha, especie, concepto, importe FROM gastos ORDER BY id DESC LIMIT 10", conn)
    st.table(df_g)

# --- 5. HISTÓRICO TOTAL ---
elif menu == "📈 HISTÓRICO TOTAL":
    st.title("📈 Listado Maestro")
    tabla = st.radio("Ver tabla de:", ["Ventas", "Gastos", "Producción"], horizontal=True)
    query = f"SELECT * FROM {tabla.lower()}"
    st.dataframe(pd.read_sql(query, conn), use_container_width=True)

# --- 6. MANTENIMIENTO ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Editor")
    t_del = st.selectbox("Tabla:", ["ventas", "produccion", "gastos"])
    df_m = pd.read_sql(f"SELECT * FROM {t_del} ORDER BY id DESC", conn)
    st.dataframe(df_m)
    id_del = st.number_input("ID a borrar:", min_value=0, step=1)
    if st.button("❌ Eliminar Registro"):
        c.execute(f"DELETE FROM {t_del} WHERE id = ?", (id_del,))
        conn.commit()
        st.rerun()
