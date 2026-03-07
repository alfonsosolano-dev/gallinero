import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px # Para gráficos más bonitos
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.6 - PRO", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db_v26():
    # Aseguramos tablas y nuevas columnas
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT)')
    
    # Parches para columnas nuevas (Cliente y Tipo)
    for col, tipo in [('cliente', 'TEXT DEFAULT "Particular"'), ('tipo_venta', 'TEXT DEFAULT "Externa"')]:
        try: c.execute(f"ALTER TABLE ventas ADD COLUMN {col} {tipo}")
        except: pass
    conn.commit()

inicializar_db_v26()

# --- MENÚ ---
menu = st.sidebar.radio("MENÚ", ["📊 DASHBOARD E HISTÓRICOS", "💰 VENTAS Y CLIENTES", "🐣 LOTES", "🥚 PRODUCCIÓN", "💸 GASTOS", "🛠️ DATOS"])

# --- 1. DASHBOARD E HISTÓRICOS ---
if menu == "📊 DASHBOARD E HISTÓRICOS":
    st.title("📊 Análisis Histórico y Ventas")
    
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    
    if not df_v.empty:
        # Métricas
        c1, c2, c3 = st.columns(3)
        c1.metric("VENTAS TOTALES", f"{round(df_v[df_v['tipo_venta']=='Externa']['total'].sum(), 2)} €")
        c2.metric("CLIENTES ATENDIDOS", len(df_v['cliente'].unique()))
        c3.metric("UNIDADES VENDIDAS", df_v['cantidad'].sum())

        st.divider()
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("📈 Ventas por Especie")
            fig_esp = px.pie(df_v[df_v['tipo_venta']=='Externa'], values='total', names='especie', hole=.3)
            st.plotly_chart(fig_esp, use_container_width=True)
            
        with col_b:
            st.subheader("👥 Top Clientes")
            df_cli = df_v[df_v['tipo_venta']=='Externa'].groupby('cliente')['total'].sum().reset_index()
            st.bar_chart(df_cli.set_index('cliente'))
            
        st.subheader("📅 Evolución Mensual")
        # Convertimos fecha para ordenar cronológicamente
        df_v['fecha_dt'] = pd.to_datetime(df_v['fecha'], format='%d/%m/%Y')
        df_mes = df_v.set_index('fecha_dt').resample('M')['total'].sum().reset_index()
        st.line_chart(df_mes.set_index('fecha_dt'))
    else:
        st.info("Aún no hay datos suficientes para mostrar históricos.")

# --- 2. VENTAS Y CLIENTES (AUTOMATIZADO) ---
elif menu == "💰 VENTAS Y CLIENTES":
    st.title("💰 Registro de Salidas")
    
    with st.form("f_v", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        tipo = col1.selectbox("Tipo de Salida", ["Externa", "Consumo Propio"])
        esp = col2.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        
        # AUTOMATIZACIÓN DE NOMBRE DE PRODUCTO
        prod_sugerido = "Huevos" if esp in ["Gallinas", "Codornices"] else "Carne/Canal"
        pro = col2.text_input("Producto", value=prod_sugerido)
        
        cli = col1.text_input("Nombre del Cliente", value="Particular" if tipo == "Externa" else "Casa")
        can = col2.number_input("Cantidad", min_value=1)
        
        # Precio: 0 si es para casa
        val_total = 0.0 if tipo == "Consumo Propio" else 0.0
        tot = col1.number_input("Total Cobrado (€)", min_value=0.0, value=val_total)
        
        if st.form_submit_button("✅ REGISTRAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total, especie, tipo_venta) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), cli, pro, can, tot, esp, tipo))
            conn.commit()
            st.success(f"✅ Venta registrada a {cli}: {can} {pro} de {esp}.")

# --- OTROS (Sin cambios drásticos para mantener estabilidad) ---
elif menu == "🐣 LOTES":
    st.title("🐣 Entrada de Animales")
    with st.form("l", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1); pre = st.number_input("Precio/ud")
        if st.form_submit_button("✅ GUARDAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f_s, f"Compra {esp}", can*pre, "Animales", esp))
            conn.commit(); st.success("✅ Guardado.")

elif menu == "🥚 PRODUCCIÓN":
    st.title("🥚 Producción (Recogida)")
    with st.form("p", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        can = st.number_input("Cantidad huevos recogidos", min_value=0)
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), esp, can))
            conn.commit(); st.success("✅ Registrado.")

elif menu == "💸 GASTOS":
    st.title("💸 Gastos")
    with st.form("g", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Asignar a", ["Gallinas", "Pollos", "Codornices", "General"])
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipos"]); imp = st.number_input("Importe €")
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), "Gasto manual", imp, cat, esp))
            conn.commit(); st.success("✅ Gasto anotado.")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["ventas", "lotes", "gastos", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
