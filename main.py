import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.9 - ANALÍTICA PRO", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def reparar_db():
    # Asegurar estructura robusta
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL)')
    
    # Columnas críticas para los históricos
    for t, col, tipo in [('ventas','cliente','TEXT'), ('ventas','tipo_venta','TEXT'), ('gastos','especie','TEXT')]:
        try: c.execute(f"ALTER TABLE {t} ADD COLUMN {col} {tipo}")
        except: pass
    conn.commit()

reparar_db()

# --- MENÚ PRINCIPAL ---
menu = st.sidebar.radio("NAVEGACIÓN", ["📈 CONTABILIDAD E HISTÓRICOS", "💰 REGISTRAR VENTA", "🥚 REGISTRAR PRODUCCIÓN", "💸 REGISTRAR GASTO", "🐣 GESTIÓN DE LOTES", "🛠️ BASE DE DATOS"])

# --- 1. SECCIÓN DE CONTABILIDAD E HISTÓRICOS (POR PESTAÑAS) ---
if menu == "📈 CONTABILIDAD E HISTÓRICOS":
    st.title("📈 Centro de Análisis y Contabilidad")
    
    # Carga de datos
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    df_g = pd.read_sql("SELECT * FROM gastos", conn)
    df_p = pd.read_sql("SELECT * FROM produccion", conn)
    
    # CREACIÓN DE PESTAÑAS
    tab_gen, tab_gal, tab_pol, tab_cod = st.tabs(["🌍 GENERAL", "🐔 GALLINAS", "🍗 POLLOS", "🐦 CODORNICES"])

    # --- PESTAÑA GENERAL ---
    with tab_gen:
        st.subheader("💰 Balance Global del Corral")
        ing_tot = df_v[df_v['tipo_venta'] == 'Externa']['total'].sum()
        gas_tot = df_g['importe'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS TOTALES", f"{round(ing_tot, 2)} €")
        c2.metric("GASTOS TOTALES", f"{round(gas_tot, 2)} €")
        c3.metric("BENEFICIO NETO", f"{round(ing_tot - gas_tot, 2)} €")
        
        st.divider()
        st.subheader("🛠️ Gastos Comunes (Infraestructura)")
        df_comun = df_g[df_g['especie'] == 'General']
        if not df_comun.empty:
            st.dataframe(df_comun[['fecha', 'concepto', 'importe', 'categoria']], use_container_width=True)
            st.info(f"Total invertido en equipos comunes: {round(df_comun['importe'].sum(), 2)} €")

    # --- FUNCIÓN PARA RENDERIZAR PESTAÑAS DE ESPECIE ---
    def render_especie(especie, color_grafico):
        st.subheader(f"Análisis de {especie}")
        
        # Filtrar datos
        v_e = df_v[df_v['especie'] == especie]
        g_e = df_g[df_g['especie'] == especie]
        p_e = df_p[df_p['especie'] == especie]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos", f"{round(v_e[v_e['tipo_venta']=='Externa']['total'].sum(), 2)} €")
        col2.metric("Gastos Directos", f"{round(g_e['importe'].sum(), 2)} €")
        col3.metric("Consumo Casa", f"{int(v_e[v_e['tipo_venta']=='Consumo Propio']['cantidad'].sum())} uds")
        
        # Histórico de Producción
        if not p_e.empty:
            st.write("📅 **Evolución de Producción (Histórico)**")
            p_e['fecha_dt'] = pd.to_datetime(p_e['fecha'], format='%d/%m/%Y', errors='coerce')
            fig = px.line(p_e.sort_values('fecha_dt'), x='fecha_dt', y='cantidad', 
                          title=f"Producción Diaria: {especie}", markers=True, color_discrete_sequence=[color_grafico])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No hay datos de producción para {especie}")

    with tab_gal: render_especie("Gallinas", "#FFA500")
    with tab_pol: render_especie("Pollos", "#FF4B4B")
    with tab_cod: render_especie("Codornices", "#4B8BFF")

# --- 2. VENTAS (CON AUTO-PRODUCTO) ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Salidas (Venta/Casa)")
    with st.form("v", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        tipo = col1.selectbox("Tipo", ["Externa", "Consumo Propio"])
        esp = col2.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        
        prod_defecto = "Huevos" if esp in ["Gallinas", "Codornices"] else "Carne"
        pro = col2.text_input("Producto", value=prod_defecto)
        cli = col1.text_input("Cliente", value="Particular" if tipo == "Externa" else "Casa")
        
        can = col2.number_input("Cantidad", min_value=1)
        tot = col1.number_input("Total (€)", min_value=0.0)
        
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total, especie, tipo_venta) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), cli, pro, can, tot, esp, tipo))
            conn.commit(); st.success("Registrado.")

# --- 3. GASTOS (CON OPCIÓN GENERAL) ---
elif menu == "💸 REGISTRAR GASTO":
    st.title("💸 Registro de Gastos")
    with st.form("g", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Asignar a:", ["General", "Gallinas", "Pollos", "Codornices"])
        cat = st.selectbox("Categoría", ["Pienso", "Equipos (Bebederos/Comederos)", "Salud", "Animales", "Otros"])
        con = st.text_input("Concepto (ej: Saco de iniciación)")
        imp = st.number_input("Importe (€)", min_value=0.0)
        
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, esp))
            conn.commit(); st.success("Gasto guardado.")

# --- PESTAÑAS DE APOYO ---
elif menu == "🥚 REGISTRAR PRODUCCIÓN":
    with st.form("p"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        can = st.number_input("Cantidad", min_value=0)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), esp, can))
            conn.commit(); st.rerun()

elif menu == "🐣 GESTIÓN DE LOTES":
    with st.form("l"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1); pre = st.number_input("Precio/ud")
        if st.form_submit_button("✅"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,'Animales',?)", (f_s, f"Lote {esp}", can*pre, esp))
            conn.commit(); st.success("Lote y Gasto registrado.")

elif menu == "🛠️ BASE DE DATOS":
    t = st.selectbox("Tabla", ["ventas", "gastos", "produccion", "lotes"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
