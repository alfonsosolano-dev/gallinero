import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.58", layout="wide")
conn = sqlite3.connect('corral_v58_final.db', check_same_thread=False)
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
st.sidebar.title("🦆 MENÚ PRINCIPAL")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "🍗 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. SECCIÓN: RENTABILIDAD ---
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis Financiero")
    df_l = cargar('lotes'); df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    tab_gen, tab_gall, tab_poll, tab_cod = st.tabs(["🌍 General", "🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])
    
    for pestaña, esp_nombre in [(tab_gall, "Gallinas"), (tab_poll, "Pollos"), (tab_cod, "Codornices")]:
        with pestaña:
            g_e = df_g[df_g['raza'].str.contains(esp_nombre, case=False, na=False) | df_g['categoria'].str.contains(esp_nombre, case=False, na=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp_nombre]['total'].sum()
            st.subheader(f"Balance {esp_nombre}: {v_e - g_e:.2f}€")
            p_e = df_p[df_p['especie'] == esp_nombre]
            if not p_e.empty: st.plotly_chart(px.line(p_e, x='fecha', y='cantidad', title=f"Producción {esp_nombre}"))

# --- 4. SECCIÓN: CRECIMIENTO (METAS AJUSTADAS: CAMPEROS Y CODORNICES) ---
elif menu == "🍗 CRECIMIENTO":
    st.title("📈 Madurez por Especie y Raza")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            raza_u = row['raza'].upper()
            
            # LÓGICA DE METAS ESPECÍFICAS
            if row['especie'] == 'Codornices': 
                meta = 45 # Crecen muy rápido
            elif row['especie'] == 'Pollos':
                if "BLANCO" in raza_u: meta = 60
                elif "CAMPERO" in raza_u: meta = 95 # El campero necesita más tiempo para calidad
                else: meta = 110
            else: # Gallinas
                if "ROJA" in raza_u: meta = 140
                elif "CHOCOLATE" in raza_u: meta = 180
                else: meta = 160
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"{row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.write(f"**Meta de Madurez:** {meta} días")
                st.progress(prog)
                if edad_t >= meta: st.success("🎯 ¡Listo!")

# --- 5. SECCIÓN: PUESTA ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Diario de Puesta")
    df_l = cargar('lotes')
    with st.form("fp", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        rz = st.selectbox("Capa/Color", ["Roja", "Blanca", "Chocolate", "Azules", "Codorniz Japónica"])
        can = st.number_input("Huevos", min_value=1)
        if st.form_submit_button("✅ ANOTAR"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); st.rerun()

# --- 8. SECCIÓN: ALTA ANIMALES (DESPLEGABLES COMPLETOS) ---
elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Alta de Nuevos Lotes")
    with st.form("fa"):
        f = st.date_input("Fecha adquisición")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        
        # RAZAS ESPECÍFICAS PARA CAMPEROS Y CODORNICES
        rz_sel = st.selectbox("Raza/Línea", 
                             ["Roja", "Blanca", "Chocolate", "Pollo Blanco (Engorde)", 
                              "Pollo Campero", "Codorniz Japónica", "OTRA"])
        rz_input = st.text_input("Si elegiste 'OTRA', escribe aquí:")
        raza_final = rz_input if rz_sel == "OTRA" else rz_sel
        
        tipo = st.selectbox("Uso", ["Puesta", "Carne", "Reposición"])
        e_ini = st.number_input("Edad al comprar (días)", value=15)
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud (€)")
        
        if st.form_submit_button("✅ REGISTRAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", 
                      (f_s, esp, raza_final, tipo, e_ini, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", 
                      (f_s, f"Compra {can} {raza_final}", can*pre, "Animales", raza_final))
            conn.commit(); st.rerun()

# --- (SECCIONES GASTOS, VENTAS, NAVIDAD Y ADMIN IGUALES) ---
elif menu == "💸 GASTOS":
    st.title("💸 Gastos")
    with st.form("fg"):
        f = st.date_input("Fecha"); cat = st.selectbox("Cat.", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura"])
        rz = st.text_input("Raza"); con = st.text_input("Concepto"); imp = st.number_input("€")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit(); st.rerun()
    st.dataframe(cargar('gastos'))

elif menu == "💰 VENTAS":
    st.title("💰 Ventas"); st.dataframe(cargar('ventas'))

elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Plan Invierno"); st.info("Recuerda la luz artificial para las gallinas.")

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Admin")
    tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        st.dataframe(df)
        id_b = st.number_input("ID a borrar", min_value=0)
        if st.button("🗑️ Borrar"): c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,)); conn.commit(); st.rerun()
