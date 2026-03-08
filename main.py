import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.62", layout="wide")
conn = sqlite3.connect('corral_v62_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    conn.commit()

inicializar_db()

def cargar(tabla):
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()

# --- 2. MENÚ LATERAL ---
st.sidebar.title("🐓 GESTIÓN DE CORRAL")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. SECCIÓN: RENTABILIDAD (VUELVEN LAS PESTAÑAS) ---
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis Financiero por Especie")
    df_l = cargar('lotes'); df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    
    tab_gen, tab_gall, tab_poll, tab_cod = st.tabs(["🌍 General", "🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])
    
    with tab_gen:
        g_t = df_g['importe'].sum(); v_t = df_v['total'].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("Inversión Total", f"{g_t:.2f}€")
        col2.metric("Ventas Totales", f"{v_t:.2f}€")
        col3.metric("Beneficio Neto", f"{v_t - g_t:.2f}€", delta=f"{v_t - g_t:.2f}€")
        if not df_g.empty:
            st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="Distribución de Gastos Globales"))

    for tab, esp_nombre in [(tab_gall, "Gallinas"), (tab_poll, "Pollos"), (tab_cod, "Codornices")]:
        with tab:
            # Filtro inteligente: por raza o por categoría de gasto
            g_e = df_g[df_g['raza'].str.contains(esp_nombre, case=False, na=False) | df_g['categoria'].str.contains(esp_nombre, case=False, na=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp_nombre]['total'].sum()
            
            c1, c2 = st.columns(2)
            c1.subheader(f"Balance {esp_nombre}")
            c1.write(f"📉 Gastos acumulados: {g_e:.2f}€")
            c1.write(f"📈 Ventas acumuladas: {v_e:.2f}€")
            c1.info(f"**Resultado: {v_e - g_e:.2f}€**")
            
            p_e = df_p[df_p['especie'] == esp_nombre]
            if not p_e.empty:
                with c2:
                    st.plotly_chart(px.line(p_e, x='fecha', y='cantidad', title=f"Evolución Producción {esp_nombre}"))

# --- 4. SECCIÓN: CRECIMIENTO (METAS POR RAZA) ---
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Control de Madurez y Relevo")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
            else: meta = 140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"🔹 {row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.progress(prog)
                if prog >= 0.8 and row['especie'] != 'Gallinas':
                    st.warning("⚠️ AVISO: Lote cerca de finalizar. ¡Toca comprar reposición!")
                if edad_t >= meta: st.success("🎯 ¡LISTO PARA PRODUCCIÓN / SACRIFICIO!")
                st.write(f"Meta: {meta} días | Progreso: {int(prog*100)}%")

# --- 5. SECCIÓN: PLAN NAVIDAD (CALCULADORA DE BENEFICIOS) ---
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Operación Navidad 2026")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📅 Calendario de Compra")
        tipo_p = st.selectbox("Tipo de Pollo", ["Pollo Campero", "Pollo Blanco (Engorde)"])
        navidad = datetime(2026, 12, 24)
        dias = 95 if "Campero" in tipo_p else 60
        f_compra = navidad - timedelta(days=dias)
        st.success(f"Compra tus pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")
    
    with col2:
        st.subheader("💰 Previsión Económica")
        cant = st.number_input("Nº de pollos", value=10)
        coste_u = st.number_input("Coste pollito + pienso (€/unidad)", value=6.0)
        venta_u = st.number_input("Precio venta estimado (€/unidad)", value=18.0)
        st.metric("Beneficio Neto Previsto", f"{(venta_u - coste_u) * cant:.2f}€")

# --- 6. SECCIONES: PUESTA, GASTOS, VENTAS, ALTA ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Registro de Puesta")
    with st.form("fp", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Azul", "Codorniz"])
        can = st.number_input("Cantidad Huevos", min_value=1)
        if st.form_submit_button("✅ ANOTAR"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); st.rerun()

elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    with st.form("fg", clear_on_submit=True):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe (€)")
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, "General"))
            conn.commit(); st.rerun()
    st.dataframe(cargar('gastos'))

elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    with st.form("fv", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro = st.selectbox("Producto", ["Huevos", "Animal Vivo", "Carne"]); can = st.number_input("Cant."); tot = st.number_input("Total (€)")
        if st.form_submit_button("✅ REGISTRAR"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, especie) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, can, tot, "General", esp))
            conn.commit(); st.rerun()

elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Alta de Nuevos Lotes")
    with st.form("fa"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Pollo Blanco (Engorde)", "Pollo Campero", "Codorniz Japónica", "OTRA"])
        can = st.number_input("Cantidad"); pre = st.number_input("Precio/ud"); e_ini = st.number_input("Edad inicial (días)", value=15)
        if st.form_submit_button("✅ DAR DE ALTA"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, pre, 'Activo'))
            conn.commit(); st.rerun()

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Administración")
    tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        st.dataframe(df)
        if st.button("🗑️ Borrar registro"):
            id_b = st.number_input("ID", 0)
            c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,))
            conn.commit(); st.rerun()
