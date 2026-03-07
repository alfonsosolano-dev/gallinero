import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.28.0 - RENTABILIDAD", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

# --- RECONSTRUCCIÓN ESTRUCTURAL (ASEGURAR COLUMNAS) ---
def inicializar_db():
    estructuras = {
        'lotes': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL DEFAULT 0.0, estado TEXT DEFAULT "Activo"',
        'gastos': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT DEFAULT "General"',
        'ventas': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT DEFAULT "Externa"',
        'produccion': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL'
    }
    for tabla, definicion in estructuras.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {tabla} ({definicion})")
    conn.commit()

inicializar_db()

# --- NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ", ["📈 RENTABILIDAD POR ESPECIE", "💰 VENTAS", "🥚 PRODUCCIÓN", "💸 GASTOS", "🐣 LOTES", "🛠️ DATOS"])

# --- 1. RENTABILIDAD POR ESPECIE (NUEVA LÓGICA) ---
if menu == "📈 RENTABILIDAD POR ESPECIE":
    st.title("📈 Análisis de Beneficio Neto y Costos Exactos")
    
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    df_g = pd.read_sql("SELECT * FROM gastos", conn)
    
    t_gen, t_gal, t_pol, t_cod = st.tabs(["🌎 GENERAL", "🐔 GALLINAS", "🍗 POLLOS", "🐦 CODORNICES"])

    with t_gen:
        st.subheader("📊 Balance Consolidado")
        ing_t = df_v[df_v['tipo_venta'] == 'Externa']['total'].sum() if not df_v.empty else 0
        gas_t = df_g['importe'].sum() if not df_g.empty else 0
        beneficio = ing_t - gas_t
        
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS TOTALES", f"{round(ing_t, 2)} €")
        c2.metric("GASTOS TOTALES", f"{round(gas_t, 2)} €")
        c3.metric("BENEFICIO NETO", f"{round(beneficio, 2)} €", delta=f"{round((beneficio/ing_t*100) if ing_t > 0 else 0, 1)}% Margen")

    def analizar_especie(nombre, color):
        v = df_v[df_v['especie'] == nombre] if not df_v.empty else pd.DataFrame()
        g = df_g[df_g['especie'] == nombre] if not df_g.empty else pd.DataFrame()
        
        # 1. Métricas Críticas
        ing = v[v['tipo_venta'] == 'Externa']['total'].sum() if not v.empty else 0
        gas = g['importe'].sum() if not g.empty else 0
        neto = ing - gas
        margen = (neto / ing * 100) if ing > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric(f"Beneficio {nombre}", f"{round(neto, 2)} €")
        col2.metric("Inversión Total", f"{round(gas, 2)} €")
        col3.metric("Margen Real", f"{round(margen, 1)} %")

        st.divider()

        # 2. Gráfico Comparativo Ingresos vs Gastos
        st.write(f"📅 **Histórico de Flujo de Caja: {nombre}**")
        if not v.empty or not g.empty:
            # Unificamos para el gráfico
            v_plot = v.copy(); v_plot['Tipo'] = 'Ingreso'
            g_plot = g.copy(); g_plot['Tipo'] = 'Gasto'; g_plot['total'] = g_plot['importe']
            combined = pd.concat([v_plot[['fecha', 'total', 'Tipo']], g_plot[['fecha', 'total', 'Tipo']]])
            combined['fecha'] = pd.to_datetime(combined['fecha'], format='%d/%m/%Y', errors='coerce')
            
            fig = px.bar(combined.sort_values('fecha'), x='fecha', y='total', color='Tipo', 
                         barmode='group', color_discrete_map={'Ingreso':'#2ECC71', 'Gasto':'#E74C3C'},
                         title=f"Ingresos vs Gastos por Fecha - {nombre}")
            st.plotly_chart(fig, use_container_width=True)

        # 3. Costos Exactos por Categoría
        st.write(f"🔍 **Desglose de Costos de {nombre}**")
        if not g.empty:
            df_costos = g.groupby('categoria')['importe'].sum().reset_index()
            st.table(df_costos.sort_values(by='importe', ascending=False).style.format({"importe": "{:.2f} €"}))
        else:
            st.info("No hay gastos registrados para esta especie.")

    with t_gal: analizar_especie("Gallinas", "orange")
    with t_pol: analizar_especie("Pollos", "red")
    with t_cod: analizar_especie("Codornices", "blue")

# --- SECCIONES DE REGISTRO (SIN CAMBIOS PARA EVITAR ERRORES) ---
elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    with st.form("fv"):
        f = st.date_input("Fecha"); tipo = st.selectbox("Tipo", ["Externa", "Consumo Propio"])
        esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        cli = st.text_input("Cliente", value="Particular" if tipo == "Externa" else "Casa")
        pro = st.text_input("Producto", value="Huevos" if esp != "Pollos" else "Carne")
        can = st.number_input("Cantidad", min_value=1); tot = st.number_input("Total (€)", min_value=0.0)
        if st.form_submit_button("✅ REGISTRAR"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total, especie, tipo_venta) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), cli, pro, can, tot, esp, tipo))
            conn.commit(); st.success("Venta guardada.")

elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    with st.form("fg"):
        f = st.date_input("Fecha"); esp = st.selectbox("Asignar a", ["General", "Gallinas", "Pollos", "Codornices"])
        cat = st.selectbox("Categoría", ["Pienso", "Infraestructura", "Salud", "Animales", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, esp))
            conn.commit(); st.success("Gasto anotado.")

elif menu == "🐣 LOTES":
    st.title("🐣 Entrada de Animales")
    with st.form("fl"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1); pre = st.number_input("Precio/ud", min_value=0.0)
        if st.form_submit_button("✅"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f_s, f"Compra Lote {esp}", can*pre, "Animales", esp))
            conn.commit(); st.success("Lote registrado.")

elif menu == "🥚 PRODUCCIÓN":
    st.title("🥚 Producción")
    with st.form("fp"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"]); can = st.number_input("Unidades")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), esp, can))
            conn.commit(); st.success("OK")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
