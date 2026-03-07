import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.7 - CONTABILIDAD REAL", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db_v27():
    # Asegurar todas las tablas con sus columnas necesarias
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL)')
    conn.commit()

inicializar_db_v27()

# --- MENÚ ---
menu = st.sidebar.radio("MENÚ PRINCIPAL", ["📈 HOJA DE CONTABILIDAD", "💰 VENTAS Y CLIENTES", "🥚 PRODUCCIÓN DIARIA", "💸 REGISTRO DE GASTOS", "🐣 LOTES", "🛠️ DATOS"])

# --- 1. HOJA DE CONTABILIDAD (NUEVA PETICIÓN) ---
if menu == "📈 HOJA DE CONTABILIDAD":
    st.title("📈 Hoja de Contabilidad y Análisis Real")
    
    # --- BLOQUE 1: RESUMEN GENERAL ---
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    df_g = pd.read_sql("SELECT * FROM gastos", conn)
    df_p = pd.read_sql("SELECT * FROM produccion", conn)
    
    col1, col2, col3, col4 = st.columns(4)
    ing_reales = df_v[df_v['tipo_venta'] == 'Externa']['total'].sum()
    gas_total = df_g['importe'].sum()
    gas_comun = df_g[df_g['especie'] == 'General']['importe'].sum()
    
    col1.metric("INGRESOS CAJA", f"{round(ing_reales, 2)} €")
    col2.metric("GASTOS TOTALES", f"{round(gas_total, 2)} €")
    col3.metric("GASTOS COMUNES", f"{round(gas_comun, 2)} €", help="Comederos, bebederos, etc.")
    col4.metric("BALANCE NETO", f"{round(ing_reales - gas_total, 2)} €")

    st.divider()

    # --- BLOQUE 2: HISTÓRICOS DE PRODUCCIÓN ---
    st.subheader("🥚 Histórico de Producción por Especie")
    if not df_p.empty:
        df_p['fecha_dt'] = pd.to_datetime(df_p['fecha'], format='%d/%m/%Y')
        fig_prod = px.line(df_p, x='fecha_dt', y='cantidad', color='especie', 
                          title="Evolución de Recogida (Huevos/Unidades)",
                          labels={'fecha_dt': 'Fecha', 'cantidad': 'Cantidad'})
        st.plotly_chart(fig_prod, use_container_width=True)
    else:
        st.info("No hay datos de producción para graficar.")

    st.divider()

    # --- BLOQUE 3: GASTOS DETALLADOS ---
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("💸 Gastos por Categoría")
        fig_cat = px.bar(df_g, x='categoria', y='importe', color='especie', title="¿En qué gastamos el dinero?")
        st.plotly_chart(fig_cat, use_container_width=True)
        
    with col_g2:
        st.subheader("🐣 Inversión por Especie")
        df_g_esp = df_g.groupby('especie')['importe'].sum().reset_index()
        fig_pie_g = px.pie(df_g_esp, values='importe', names='especie', hole=.3)
        st.plotly_chart(fig_pie_g, use_container_width=True)

# --- 2. VENTAS Y CLIENTES (AUTOMATIZADO) ---
elif menu == "💰 VENTAS Y CLIENTES":
    st.title("💰 Salidas (Ventas y Autoconsumo)")
    with st.form("f_v", clear_on_submit=True):
        f = st.date_input("Fecha")
        col_v1, col_v2 = st.columns(2)
        tipo = col_v1.selectbox("Tipo de Salida", ["Externa", "Consumo Propio"])
        esp = col_v2.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        
        prod_sugerido = "Huevos" if esp in ["Gallinas", "Codornices"] else "Carne"
        pro = col_v2.text_input("Producto", value=prod_sugerido)
        cli = col_v1.text_input("Cliente", value="Particular" if tipo == "Externa" else "Casa")
        
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total Cobrado (€)", min_value=0.0)
        
        if st.form_submit_button("✅ REGISTRAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total, especie, tipo_venta) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), cli, pro, can, tot, esp, tipo))
            conn.commit()
            st.success(f"Venta de {pro} registrada a {cli}")

# --- 3. GASTOS (CON OPCIÓN GENERAL) ---
elif menu == "💸 REGISTRO DE GASTOS":
    st.title("💸 Control de Gastos")
    with st.form("f_g", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Asignar gasto a:", ["General (Común)", "Gallinas", "Pollos", "Codornices"])
        # Limpiamos el nombre para la DB
        esp_val = "General" if "General" in esp else esp
        
        cat = st.selectbox("Categoría", ["Pienso", "Infraestructura (Comederos/Bebederos)", "Salud", "Animales", "Otros"])
        con = st.text_input("Concepto (ej: Comedero automático)")
        imp = st.number_input("Importe (€)", min_value=0.0)
        
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, esp_val))
            conn.commit()
            st.success(f"Gasto de {imp}€ guardado en {esp_val}")

# --- PESTAÑAS RESTANTES ---
elif menu == "🥚 PRODUCCIÓN DIARIA":
    st.title("🥚 Registro de Recogida")
    with st.form("p"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        can = st.number_input("Cantidad", min_value=0)
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), esp, can))
            conn.commit(); st.success("Registrado.")

elif menu == "🐣 LOTES":
    st.title("🐣 Entrada de Lotes")
    with st.form("l"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1); pre = st.number_input("Precio/ud")
        if st.form_submit_button("✅"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,'Animales',?)", (f_s, f"Lote {esp}", can*pre, esp))
            conn.commit(); st.success("Lote guardado.")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["ventas", "gastos", "produccion", "lotes"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
