import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.26.0 - FIX TOTAL", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

# --- REPARACIÓN AGRESIVA DE BASE DE DATOS ---
def super_reparacion():
    # 1. Crear tablas base si no existen
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL)')
    
    # 2. Verificar y añadir columnas faltantes una por una (esto evita el OperationalError)
    tablas_columnas = {
        'lotes': [('precio_ud', 'REAL'), ('estado', 'TEXT')],
        'ventas': [('cliente', 'TEXT'), ('tipo_venta', 'TEXT'), ('especie', 'TEXT')],
        'gastos': [('especie', 'TEXT'), ('categoria', 'TEXT')]
    }
    
    for tabla, columnas in tablas_columnas.items():
        # Obtenemos nombres de columnas actuales
        c.execute(f"PRAGMA table_info({tabla})")
        existentes = [info[1] for info in c.fetchall()]
        
        for col_nombre, col_tipo in columnas:
            if col_nombre not in existentes:
                try:
                    c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col_nombre} {col_tipo}")
                except Exception as e:
                    st.error(f"Error actualizando tabla {tabla}: {e}")
    
    # 3. Limpieza de nulos para que no fallen los cálculos
    c.execute("UPDATE lotes SET precio_ud = 0.0 WHERE precio_ud IS NULL")
    c.execute("UPDATE lotes SET estado = 'Activo' WHERE estado IS NULL")
    conn.commit()

super_reparacion()

# --- MENÚ PRINCIPAL ---
st.sidebar.title("🐓 Gestión V.26.0")
menu = st.sidebar.radio("NAVEGACIÓN", ["📈 CONTABILIDAD E HISTÓRICOS", "💰 REGISTRAR VENTA", "🥚 REGISTRAR PRODUCCIÓN", "💸 REGISTRAR GASTO", "🐣 GESTIÓN DE LOTES", "🛠️ BASE DE DATOS"])

# --- 1. CONTABILIDAD E HISTÓRICOS (POR ESPECIE) ---
if menu == "📈 CONTABILIDAD E HISTÓRICOS":
    st.title("📈 Análisis de Resultados")
    
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    df_g = pd.read_sql("SELECT * FROM gastos", conn)
    df_p = pd.read_sql("SELECT * FROM produccion", conn)
    
    tab_gen, tab_gal, tab_pol, tab_cod = st.tabs(["🌍 GENERAL", "🐔 GALLINAS", "🍗 POLLOS", "🐦 CODORNICES"])

    with tab_gen:
        st.subheader("💰 Balance Global")
        ing_tot = df_v[df_v['tipo_venta'] == 'Externa']['total'].sum() if not df_v.empty else 0
        gas_tot = df_g['importe'].sum() if not df_g.empty else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS TOTALES", f"{round(ing_tot, 2)} €")
        c2.metric("GASTOS TOTALES", f"{round(gas_tot, 2)} €")
        c3.metric("BENEFICIO NETO", f"{round(ing_tot - gas_tot, 2)} €")
        
        st.divider()
        st.subheader("🛠️ Gastos de Infraestructura (Comunes)")
        df_comun = df_g[df_g['especie'].str.contains('General', na=False)]
        st.dataframe(df_comun, use_container_width=True)

    def mostrar_especie(nombre, color):
        v = df_v[df_v['especie'] == nombre] if not df_v.empty else pd.DataFrame()
        g = df_g[df_g['especie'] == nombre] if not df_g.empty else pd.DataFrame()
        p = df_p[df_p['especie'] == nombre] if not df_p.empty else pd.DataFrame()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ventas", f"{round(v[v['tipo_venta']=='Externa']['total'].sum(), 2) if not v.empty else 0} €")
        col2.metric("Gastos Directos", f"{round(g['importe'].sum(), 2) if not g.empty else 0} €")
        col3.metric("Consumo Casa", f"{int(v[v['tipo_venta']=='Consumo Propio']['cantidad'].sum()) if not v.empty else 0} uds")
        
        if not p.empty:
            p['fecha_dt'] = pd.to_datetime(p['fecha'], format='%d/%m/%Y', errors='coerce')
            fig = px.line(p.sort_values('fecha_dt'), x='fecha_dt', y='cantidad', title=f"Producción {nombre}", markers=True, color_discrete_sequence=[color])
            st.plotly_chart(fig, use_container_width=True)

    with tab_gal: mostrar_especie("Gallinas", "orange")
    with tab_pol: mostrar_especie("Pollos", "red")
    with tab_cod: mostrar_especie("Codornices", "blue")

# --- 5. GESTIÓN DE LOTES (DONDE DABA ERROR) ---
elif menu == "🐣 GESTIÓN DE LOTES":
    st.title("🐣 Entrada de Nuevos Animales")
    st.info("Al registrar un lote, se creará automáticamente un gasto asociado.")
    with st.form("form_lotes", clear_on_submit=True):
        f = st.date_input("Fecha de Entrada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad de aves", min_value=1)
        pre = st.number_input("Precio por unidad (€)", min_value=0.0)
        
        if st.form_submit_button("✅ REGISTRAR LOTE"):
            f_s = f.strftime('%d/%m/%Y')
            # Inserción con columnas explícitas reparadas
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", 
                      (f_s, esp, can, pre, 'Activo'))
            # Registro automático del gasto
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", 
                      (f_s, f"Compra Lote {esp}", can*pre, "Animales", esp))
            conn.commit()
            st.success(f"✅ Lote de {can} {esp} registrado. Se ha generado un gasto de {can*pre}€.")

# --- RESTO DE FUNCIONES (VENTAS, PROD, GASTOS) ---
elif menu == "💰 REGISTRAR VENTA":
    st.title("💰 Ventas y Clientes")
    with st.form("v"):
        f = st.date_input("Fecha")
        tipo = st.selectbox("Tipo", ["Externa", "Consumo Propio"])
        esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        cli = st.text_input("Nombre Cliente", value="Particular" if tipo == "Externa" else "Casa")
        pro = st.text_input("Producto", value="Huevos" if esp != "Pollos" else "Carne")
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total, especie, tipo_venta) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), cli, pro, can, tot, esp, tipo))
            conn.commit(); st.success("Venta registrada")

elif menu == "💸 REGISTRAR GASTO":
    st.title("💸 Gastos Manuales")
    with st.form("g"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Asignar a", ["General", "Gallinas", "Pollos", "Codornices"])
        cat = st.selectbox("Categoría", ["Pienso", "Infraestructura", "Salud", "Varios"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, esp))
            conn.commit(); st.success("Gasto guardado")

elif menu == "🥚 REGISTRAR PRODUCCIÓN":
    st.title("🥚 Producción")
    with st.form("p"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        can = st.number_input("Unidades recogidas", min_value=0)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), esp, can))
            conn.commit(); st.success("Producción anotada")

elif menu == "🛠️ BASE DE DATOS":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
