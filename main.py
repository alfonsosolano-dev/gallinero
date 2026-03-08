import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO TOTAL", layout="wide")
conn = sqlite3.connect('corral_final_consolidado.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    conn.commit()

inicializar_db()

def cargar(tabla):
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()

# --- 2. MENÚ LATERAL ---
st.sidebar.title("🐓 GESTIÓN INTEGRAL")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS (PIENSO)", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. RENTABILIDAD POR PESTAÑAS (Recuperado de v62) ---
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis Financiero y Producción")
    df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    
    tabs = st.tabs(["🌍 General", "🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])
    
    with tabs[0]: # GENERAL
        g_t = df_g['importe'].sum(); v_t = df_v['total'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Inversión", f"{g_t:.2f}€")
        c2.metric("Ventas", f"{v_t:.2f}€")
        c3.metric("Beneficio", f"{v_t - g_t:.2f}€", delta=f"{v_t - g_t:.2f}€")
        if not df_g.empty: st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="Gastos"))

    for i, esp in enumerate(["Gallinas", "Pollos", "Codornices"], 1):
        with tabs[i]:
            g_e = df_g[df_g['categoria'].str.contains(esp, na=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp]['total'].sum()
            p_e = df_p[df_p['especie'] == esp]['cantidad'].sum()
            
            col_a, col_b = st.columns(2)
            col_a.metric(f"Balance {esp}", f"{v_e - g_e:.2f}€")
            if p_e > 0: col_b.metric("Coste/Unidad Producción", f"{g_e/p_e:.2f}€")
            
            p_data = df_p[df_p['especie'] == esp]
            if not p_data.empty: st.plotly_chart(px.line(p_data, x='fecha', y='cantidad', title=f"Producción {esp}"))

# --- 4. CRECIMIENTO Y REPOSICIÓN (Recuperado de v59/v63) ---
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Madurez de Lotes y Relevo")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            
            # Lógica de Metas
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
            else: meta = 140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"🔹 {row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.progress(prog)
                if prog >= 0.8 and row['especie'] != 'Gallinas':
                    st.warning("⚠️ AVISO DE REPOSICIÓN: Lote al 80%. Compra el relevo para no parar el ciclo.")
                st.write(f"Meta: {meta} días | Progreso: {int(prog*100)}%")

# --- 5. GASTOS CON KILOS (Recuperado de v63/v64) ---
elif menu == "💸 GASTOS (PIENSO)":
    st.title("💸 Control de Suministros")
    with st.form("fg"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe (€)"); kgs = st.number_input("Kilos (kg)", value=0.0)
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, raza) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, kgs, cat, "General"))
            conn.commit(); st.rerun()
    df_g = cargar('gastos')
    if not df_g.empty:
        df_g['€/kg'] = df_g.apply(lambda x: x['importe']/x['kilos'] if x['kilos']>0 else 0, axis=1)
        st.dataframe(df_g)

# --- 6. PLAN NAVIDAD Y CALCULADORA (Recuperado de v61) ---
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Plan Navidad 2026")
    tipo = st.selectbox("Tipo de Pollo", ["Pollo Campero (95 días)", "Pollo Blanco (60 días)"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=dias)
    st.success(f"📅 Fecha ideal de compra: **{f_compra.strftime('%d/%m/%Y')}**")
    
    st.divider(); st.subheader("💰 Previsión de Beneficio")
    c1, c2, c3 = st.columns(3)
    n = c1.number_input("Cantidad", 10); cost = c2.number_input("Coste x Ave (€)", 6.0); vent = c3.number_input("Venta x Ave (€)", 18.0)
    st.metric("Beneficio Estimado", f"{(vent-cost)*n:.2f}€")

# --- 7. PUESTA, VENTAS, ALTA Y ADMIN (BÁSICOS REVISADOS) ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Puesta"); f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
    rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Azul", "Codorniz"]); can = st.number_input("Huevos", 1)
    if st.button("Anotar"):
        c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, esp))
        conn.commit(); st.rerun()

elif menu == "💰 VENTAS":
    st.title("💰 Ventas"); st.dataframe(cargar('ventas'))

elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Alta"); 
    with st.form("fa"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Pollo Blanco (Engorde)", "Pollo Campero", "Codorniz Japónica", "OTRA"])
        can = st.number_input("Cant."); pre = st.number_input("Precio/ud"); e_ini = st.number_input("Edad inicial", 15)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, pre, 'Activo'))
            conn.commit(); st.rerun()

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Admin"); tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        st.dataframe(df)
        id_b = st.number_input("ID a borrar", 0)
        if st.button("Borrar"): c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,)); conn.commit(); st.rerun()
