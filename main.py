import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.60", layout="wide")
conn = sqlite3.connect('corral_v60_final.db', check_same_thread=False)
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
st.sidebar.title("🐓 MI CORRAL V.60")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. SECCIÓN: RENTABILIDAD ---
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis por Especie")
    df_l = cargar('lotes'); df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    tab_gen, tab_gall, tab_poll, tab_cod = st.tabs(["🌍 Global", "🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])
    for tab, esp in [(tab_gall, "Gallinas"), (tab_poll, "Pollos"), (tab_cod, "Codornices")]:
        with tab:
            g_e = df_g[df_g['raza'].str.contains(esp, case=False, na=False) | df_g['categoria'].str.contains(esp, case=False, na=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp]['total'].sum()
            st.subheader(f"Balance {esp}: {v_e - g_e:.2f}€")
            p_e = df_p[df_p['especie'] == esp]
            if not p_e.empty: st.plotly_chart(px.line(p_e, x='fecha', y='cantidad', title=f"Producción {esp}"))

# --- 4. SECCIÓN: CRECIMIENTO + REPOSICIÓN ---
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Madurez y Reposición")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            
            # Metas
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
            else: meta = 140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"🔹 {row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.progress(prog)
                if prog >= 0.8: st.warning(f"⚠️ **REPOSICIÓN:** Lote al {int(prog*100)}%. ¡Compra el relevo ya!")
                if edad_t >= meta: st.success("🎯 ¡MADUREZ ALCANZADA!")

# --- 5. SECCIÓN: PLAN NAVIDAD (LOGICA DE POLLOS) ---
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación Especial Navidad")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🐔 Huevos en Invierno")
        st.info("Para mantener la puesta en Navidad necesitas **14h de luz**. \n\nInstala un programador: \n- Encendido: 06:30 AM \n- Apagado: Salida del sol.")
    
    with col2:
        st.subheader("🍗 Cena de Navidad (24 Dic)")
        tipo_p = st.selectbox("¿Qué pollos quieres para Navidad?", ["Pollo Campero", "Pollo Blanco (Rápido)"])
        
        # Cálculo de fechas
        hoy = datetime.now()
        navidad = datetime(2026, 12, 24) # Ajustado al año actual del corral
        
        if "Campero" in tipo_p:
            dias_crecimiento = 95
            fecha_compra = navidad - timedelta(days=dias_crecimiento)
        else:
            dias_crecimiento = 60
            fecha_compra = navidad - timedelta(days=dias_crecimiento)
            
        st.write(f"Para que el pollo esté listo el 24 de diciembre:")
        st.success(f"📅 **DEBES COMPRAR LOS POLLITOS EL: {fecha_compra.strftime('%d de %B de %Y')}**")
        st.write(f"*(Cálculo basado en {dias_crecimiento} días de engorde)*")

# --- 6. SECCIONES RESTANTES (ALTA, PUESTA, GASTOS, ADMIN) ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Puesta"); df_l = cargar('lotes')
    with st.form("fp"):
        f = st.date_input("Fecha"); rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Azul", "Codorniz"])
        can = st.number_input("Cantidad", min_value=1)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, "Gallinas"))
            conn.commit(); st.rerun()

elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Alta"); 
    with st.form("fa"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Pollo Blanco (Engorde)", "Pollo Campero", "Codorniz Japónica", "OTRA"])
        can = st.number_input("Cant."); pre = st.number_input("Precio/ud"); e_ini = st.number_input("Edad inicial", value=15)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, pre, 'Activo'))
            conn.commit(); st.rerun()

elif menu == "💸 GASTOS":
    st.title("💸 Gastos")
    with st.form("fg"):
        f = st.date_input("Fecha"); cat = st.selectbox("Cat.", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura"]); imp = st.number_input("€")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,? ,?,?,?)", (f.strftime('%d/%m/%Y'), "Gasto", imp, cat, "General"))
            conn.commit(); st.rerun()

elif menu == "💰 VENTAS":
    st.title("💰 Ventas"); st.dataframe(cargar('ventas'))

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Admin")
    tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        st.dataframe(df)
        id_b = st.number_input("ID a borrar", min_value=0)
        if st.button("🗑️ Borrar"): c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,)); conn.commit(); st.rerun()
