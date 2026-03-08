import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL PRO V.63", layout="wide")
conn = sqlite3.connect('corral_v63_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    # Añadida columna 'kilos' a gastos
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
st.sidebar.title("🐓 GESTIÓN DE CORRAL")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS (PIENSO)", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. SECCIÓN: RENTABILIDAD (CON COSTE POR KILO) ---
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis de Costes y Beneficios")
    df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    
    tab_gen, tab_gall, tab_poll, tab_cod = st.tabs(["🌍 General", "🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])
    
    with tab_gen:
        g_t = df_g['importe'].sum(); v_t = df_v['total'].sum()
        st.metric("Beneficio Neto", f"{v_t - g_t:.2f}€", delta=f"{v_t - g_t:.2f}€")
        
        # Análisis de Pienso
        df_pienso = df_g[df_g['categoria'].str.contains("Pienso", na=False)]
        if not df_pienso.empty:
            kg_tot = df_pienso['kilos'].sum()
            coste_avg = df_pienso['importe'].sum() / kg_tot if kg_tot > 0 else 0
            st.subheader("🛒 Eficiencia de Compra")
            st.write(f"Has comprado un total de **{kg_tot:.1f} kg** de pienso.")
            st.info(f"Precio medio del kilo: **{coste_avg:.2f}€/kg**")

    # Pestañas específicas
    for tab, esp in [(tab_gall, "Gallinas"), (tab_poll, "Pollos"), (tab_cod, "Codornices")]:
        with tab:
            g_e = df_g[df_g['categoria'].str.contains(esp, na=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp]['total'].sum()
            p_e = df_p[df_p['especie'] == esp]['cantidad'].sum()
            
            c1, c2 = st.columns(2)
            c1.metric(f"Ventas {esp}", f"{v_e:.2f}€")
            if p_e > 0 and g_e > 0:
                coste_huevo = g_e / p_e
                c2.metric("Coste por unidad producida", f"{coste_huevo:.2f}€")

# --- 4. SECCIÓN: GASTOS (ACTUALIZADA CON KILOS) ---
elif menu == "💸 GASTOS (PIENSO)":
    st.title("💸 Registro de Compras y Suministros")
    with st.form("fg", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        cat = col2.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        con = st.text_input("Concepto (Ej: Saco 25kg Iniciación)")
        
        c3, c4 = st.columns(2)
        imp = c3.number_input("Importe Total (€)", min_value=0.0, step=0.1)
        kgs = c4.number_input("Kilos comprados (kg)", min_value=0.0, step=0.5)
        
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, raza) VALUES (?,?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), con, imp, kgs, cat, "General"))
            conn.commit(); st.rerun()
    
    df_visual = cargar('gastos')
    if not df_visual.empty:
        # Añadimos columna de precio/kg visualmente
        df_visual['€/kg'] = df_visual['importe'] / df_visual['kilos']
        st.dataframe(df_visual[['fecha', 'categoria', 'concepto', 'kilos', 'importe', '€/kg']])

# --- 5. SECCIÓN: CRECIMIENTO ---
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Control de Madurez")
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
            with st.expander(f"🔹 {row['especie']} {row['raza']} - {edad_t} días"):
                st.progress(prog)
                st.write(f"Meta: {meta} días | Progreso: {int(prog*100)}%")

# --- 6. SECCIÓN: PLAN NAVIDAD ---
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación Navidad")
    tipo_p = st.selectbox("Tipo de Pollo", ["Pollo Campero", "Pollo Blanco (Engorde)"])
    navidad = datetime(2026, 12, 24)
    dias = 95 if "Campero" in tipo_p else 60
    f_compra = navidad - timedelta(days=dias)
    st.success(f"Compra tus pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# --- SECCIONES RESTANTES (PUESTA, VENTAS, ALTA, ADMIN) ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Puesta")
    with st.form("fp"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Azul", "Codorniz"]); can = st.number_input("Huevos", 1)
        if st.form_submit_button("✅"):
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
    st.title("🛠️ Admin")
    tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        st.dataframe(df)
        if st.button("🗑️ Borrar"): c.execute(f"DELETE FROM {tab} WHERE id=?", (st.number_input("ID", 0),)); conn.commit(); st.rerun()
