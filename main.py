import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL INTELIGENTE V.56", layout="wide")
conn = sqlite3.connect('corral_v56_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM gastos WHERE concepto LIKE '%Material%'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                  ('21/02/2026', 'Compra Material Inicial', 100.0, 'Infraestructura', 'General'))
    conn.commit()

inicializar_db()

def cargar(tabla):
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()

# --- 2. MENÚ LATERAL ---
st.sidebar.title("🦆 MENÚ PRINCIPAL")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "🍗 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. SECCIÓN: RENTABILIDAD (POR PESTAÑAS) ---
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis Financiero Detallado")
    df_l = cargar('lotes'); df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')

    tab_gen, tab_gall, tab_poll, tab_cod = st.tabs(["🌍 General", "🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])

    with tab_gen:
        st.subheader("Balance Global")
        g_tot = df_g['importe'].sum(); v_tot = df_v['total'].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Gastos Totales", f"{g_tot:.2f}€")
        col2.metric("Ventas Totales", f"{v_tot:.2f}€")
        col3.metric("Beneficio", f"{v_tot - g_tot:.2f}€")
        if not df_g.empty:
            st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="¿En qué gastamos?"))

    especies_list = [(tab_gall, "Gallinas"), (tab_poll, "Pollos"), (tab_cod, "Codornices")]
    for pestaña, esp_nombre in especies_list:
        with pestaña:
            st.header(f"Control de {esp_nombre}")
            g_esp = df_g[df_g['raza'].str.contains(esp_nombre, case=False, na=False) | df_g['categoria'].str.contains(esp_nombre, case=False, na=False)]['importe'].sum()
            v_esp = df_v[df_v['especie'] == esp_nombre]['total'].sum()
            st.subheader(f"Balance {esp_nombre}: {v_esp - g_esp:.2f}€")
            
            p_esp = df_p[df_p['especie'] == esp_nombre]
            if not p_esp.empty:
                st.plotly_chart(px.line(p_esp, x='fecha', y='cantidad', title=f"Producción {esp_nombre}"))

# --- 4. SECCIÓN: CRECIMIENTO (METAS POR RAZA) ---
elif menu == "🍗 CRECIMIENTO":
    st.title("📈 Madurez y Reposición")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            raza = row['raza'].upper()
            
            # Lógica de metas
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in raza else 110
            else: # Gallinas
                if "ROJA" in raza: meta = 140
                elif "CHOCOLATE" in raza: meta = 180
                else: meta = 160
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"{row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.progress(prog)
                if prog > 0.8: st.warning("⚠️ Planifica reposición pronto.")
                if edad_t >= meta: st.success("🎯 Madurez alcanzada.")

# --- 5. SECCIÓN: PUESTA (CON ALERTA) ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Diario de Puesta")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, lote in df_l[(df_l['especie'] == 'Gallinas') & (df_l['estado'] == 'Activo')].iterrows():
            f_ent = datetime.strptime(lote['fecha'], '%d/%m/%Y')
            edad = (datetime.now() - f_ent).days + int(lote['edad_inicial'])
            if edad >= 130: st.error(f"🔥 ¡ALERTA! {lote['raza']} con {edad} días. ¡Revisar nidos!")

    with st.form("f_puesta", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Azules", "Codorniz"])
        can = st.number_input("Cantidad Huevos", min_value=1)
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); st.rerun()

# --- 6. GASTOS, VENTAS, ALTA Y NAVIDAD (ESTRUCTURA FINAL) ---
elif menu == "💸 GASTOS":
    st.title("💸 Gastos")
    with st.form("fg"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Animales"])
        rz = st.text_input("Asignar a Raza (Ej: Roja)"); con = st.text_input("Concepto"); imp = st.number_input("Importe (€)")
        if st.form_submit_button("✅ ANOTAR"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit(); st.rerun()
    st.dataframe(cargar('gastos'))

elif menu == "💰 VENTAS":
    st.title("💰 Ventas")
    with st.form("fv"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro = st.selectbox("Producto", ["Huevos", "Animal Vivo", "Carne"]); can = st.number_input("Cant."); tot = st.number_input("Total (€)")
        if st.form_submit_button("✅ VENDER"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, especie) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, can, tot, "General", esp))
            conn.commit(); st.rerun()

elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Alta")
    with st.form("fa"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Pollos", "Gallinas", "Codornices"])
        rz = st.text_input("Raza (Escribe ROJA, BLANCA o CHOCOLATE para objetivos)"); e_ini = st.number_input("Edad al comprar (días)", value=15)
        can = st.number_input("Cantidad"); pre = st.number_input("Precio/ud")
        if st.form_submit_button("✅ REGISTRAR"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), f"Compra {rz}", can*pre, "Animales", rz))
            conn.commit(); st.rerun()

elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Plan de Invierno")
    st.info("Recordatorio: 14h de luz diaria para mantener la puesta en diciembre.")
    if st.button("⏰ Activar Plan de Luz"): st.success("Plan activado en el calendario.")

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Admin")
    if st.button("📥 EXPORTAR EXCEL"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            cargar('lotes').to_excel(writer, sheet_name='Lotes')
            cargar('gastos').to_excel(writer, sheet_name='Gastos')
        st.download_button("Descargar", output.getvalue(), "corral.xlsx")
    tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        st.dataframe(df)
        id_b = st.number_input("ID a borrar", min_value=0)
        if st.button("🗑️ Borrar"): c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,)); conn.commit(); st.rerun()
