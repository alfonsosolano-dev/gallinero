import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.8 - ANALÍTICA", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_y_reparar_db():
    # 1. Crear tablas si no existen
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL)')
    
    # 2. REPARACIÓN ACTIVA: Añadir columnas que faltan por evolución del código
    columnas_necesarias = {
        'lotes': [('precio_ud', 'REAL DEFAULT 0.0'), ('estado', 'TEXT DEFAULT "Activo"')],
        'ventas': [('cliente', 'TEXT DEFAULT "Particular"'), ('tipo_venta', 'TEXT DEFAULT "Externa"')],
        'gastos': [('especie', 'TEXT DEFAULT "General"')]
    }
    
    for tabla, cols in columnas_necesarias.items():
        for col_nombre, col_tipo in cols:
            try:
                c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col_nombre} {col_tipo}")
            except sqlite3.OperationalError:
                pass # La columna ya existe
    conn.commit()

inicializar_y_reparar_db()

# --- MENÚ ---
menu = st.sidebar.radio("SECCIONES:", [
    "📈 HOJA DE CONTABILIDAD", 
    "💰 VENTAS Y CLIENTES", 
    "🥚 PRODUCCIÓN POR ESPECIE", 
    "💸 GASTOS (ESPECÍFICOS/GENERALES)", 
    "🐣 LOTES", 
    "🛠️ DATOS"
])

# --- 1. HOJA DE CONTABILIDAD (ANÁLISIS REAL) ---
if menu == "📈 HOJA DE CONTABILIDAD":
    st.title("📈 Hoja de Contabilidad Real")
    
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    df_g = pd.read_sql("SELECT * FROM gastos", conn)
    df_p = pd.read_sql("SELECT * FROM produccion", conn)
    
    # Métricas de Salud Financiera
    ing_ext = df_v[df_v['tipo_venta'] == 'Externa']['total'].sum()
    gas_total = df_g['importe'].sum()
    gas_especifico = df_g[df_g['especie'] != 'General']['importe'].sum()
    gas_comun = df_g[df_g['especie'] == 'General']['importe'].sum()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("INGRESOS CAJA", f"{round(ing_ext, 2)} €")
    c2.metric("GASTO ESPECÍFICO", f"{round(gas_especifico, 2)} €", help="Pienso, medicinas, animales")
    c3.metric("GASTO GENERAL", f"{round(gas_comun, 2)} €", help="Comederos, bebederos, infraestructura")
    c4.metric("BALANCE NETO", f"{round(ing_ext - gas_total, 2)} €")

    st.divider()

    # Histórico de Producción
    st.subheader("📊 Evolución de Producción por Especie")
    if not df_p.empty:
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha'], format='%d/%m/%Y', errors='coerce')
        fig_p = px.line(df_p.sort_values('fecha_dt'), x='fecha_dt', y='cantidad', color='especie', markers=True)
        st.plotly_chart(fig_p, use_container_width=True)
    
    # Análisis de Gastos
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("💸 Gastos por Categoría")
        fig_g = px.bar(df_g, x='categoria', y='importe', color='especie')
        st.plotly_chart(fig_g)
    with col_b:
        st.subheader("👥 Ventas por Cliente")
        if not df_v.empty:
            df_cli = df_v[df_v['tipo_venta'] == 'Externa'].groupby('cliente')['total'].sum().reset_index()
            fig_v = px.pie(df_cli, values='total', names='cliente', hole=0.4)
            st.plotly_chart(fig_v)

# --- 2. VENTAS Y CLIENTES ---
elif menu == "💰 VENTAS Y CLIENTES":
    st.title("💰 Salidas y Ventas")
    with st.form("v", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        tipo = col1.selectbox("Tipo", ["Externa", "Consumo Propio"])
        esp = col2.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        
        prod_auto = "Huevos" if esp in ["Gallinas", "Codornices"] else "Carne"
        pro = col2.text_input("Producto", value=prod_auto)
        cli = col1.text_input("Cliente", value="Particular" if tipo == "Externa" else "Casa")
        
        can = col2.number_input("Cantidad", min_value=1)
        tot = col1.number_input("Dinero Cobrado (€)", min_value=0.0)
        
        if st.form_submit_button("✅ REGISTRAR"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total, especie, tipo_venta) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), cli, pro, can, tot, esp, tipo))
            conn.commit()
            st.success(f"Venta de {pro} registrada correctamente.")

# --- 4. GASTOS ---
elif menu == "💸 GASTOS (ESPECÍFICOS/GENERALES)":
    st.title("💸 Registro de Gastos")
    with st.form("g", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("¿A quién asignar?", ["General (Común)", "Gallinas", "Pollos", "Codornices"])
        esp_val = "General" if "General" in esp else esp
        
        cat = st.selectbox("Categoría", ["Infraestructura (Bebederos/Comederos)", "Pienso", "Animales", "Salud", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, esp_val))
            conn.commit()
            st.success("Gasto guardado.")

# --- RESTO DE PESTAÑAS (IGUALES PARA ESTABILIDAD) ---
elif menu == "🥚 PRODUCCIÓN POR ESPECIE":
    st.title("🥚 Producción Diaria")
    with st.form("p"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        can = st.number_input("Cantidad", min_value=0)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), esp, can))
            conn.commit(); st.success("OK")

elif menu == "🐣 LOTES":
    st.title("🐣 Gestión de Lotes")
    with st.form("l"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1); pre = st.number_input("Precio/ud")
        if st.form_submit_button("✅"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,'Animales',?)", (f_s, f"Lote {esp}", can*pre, esp))
            conn.commit(); st.success("Lote registrado.")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["ventas", "gastos", "produccion", "lotes"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
