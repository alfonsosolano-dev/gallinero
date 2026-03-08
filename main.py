import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.61", layout="wide")
conn = sqlite3.connect('corral_v61_final.db', check_same_thread=False)
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
st.sidebar.title("🐓 CORRAL INTELIGENTE")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. SECCIÓN: PLAN NAVIDAD + CALCULADORA DE BENEFICIO PREVISTO ---
if menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación y Previsión de Beneficios")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🍗 Plan de Engorde")
        tipo_p = st.selectbox("Tipo de Pollo para Navidad", ["Pollo Campero", "Pollo Blanco (Engorde)"])
        cant_p = st.number_input("¿Cuántos pollos piensas criar?", min_value=1, value=10)
        
        # Lógica de fechas (Navidad 2026)
        navidad = datetime(2026, 12, 24)
        dias = 95 if "Campero" in tipo_p else 60
        f_compra = navidad - timedelta(days=dias)
        
        st.success(f"📅 Compra los pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")
        st.info(f"Ciclo de engorde: {dias} días.")

    with col2:
        st.subheader("💰 Calculadora de Beneficio")
        p_compra = st.number_input("Precio de compra por pollito (€)", value=1.5)
        p_pienso = st.number_input("Gasto estimado en pienso por pollo (€)", value=4.5)
        v_estimada = st.number_input("Precio de venta estimado por unidad (€)", value=15.0)
        
        coste_total = (p_compra + p_pienso) * cant_p
        ingreso_total = v_estimada * cant_p
        beneficio = ingreso_total - coste_total
        
        st.metric("Beneficio Previsto", f"{beneficio:.2f}€", delta=f"{beneficio/cant_p:.2f}€ por pollo")
        st.write(f"Inversión necesaria: {coste_total:.2f}€")

    st.divider()
    st.subheader("💡 Recordatorio de Luz (Gallinas)")
    st.warning("Para tener huevos en Navidad: 14h de luz total (Natural + Artificial).")

# --- 4. SECCIÓN: CRECIMIENTO + REPOSICIÓN ---
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Estado de Madurez Actual")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            
            # Metas automáticas
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
            else: meta = 140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"🔹 {row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.progress(prog)
                if prog >= 0.8: 
                    st.warning("⚠️ REPOSICIÓN: Este lote terminará pronto. ¡Planifica la compra del relevo!")
                st.write(f"Progreso: {int(prog*100)}% | Meta: {meta} días")

# --- (RESTO DE SECCIONES: RENTABILIDAD, PUESTA, GASTOS, ALTA, ADMIN) ---
elif menu == "📊 RENTABILIDAD":
    st.title("📊 Rentabilidad"); df_g = cargar('gastos'); df_v = cargar('ventas')
    st.metric("Balance", f"{df_v['total'].sum() - df_g['importe'].sum():.2f}€")

elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Alta"); 
    with st.form("fa"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Pollo Blanco (Engorde)", "Pollo Campero", "Codorniz Japónica", "OTRA"])
        can = st.number_input("Cant."); pre = st.number_input("Precio/ud"); e_ini = st.number_input("Edad inicial", value=15)
        if st.form_submit_button("✅ REGISTRAR"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, pre, 'Activo'))
            conn.commit(); st.rerun()

elif menu == "🥚 PUESTA":
    st.title("🥚 Puesta"); f = st.date_input("Fecha"); rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Azul", "Codorniz"]); can = st.number_input("Huevos", 1)
    if st.button("Anotar"): c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, "Gallinas")); conn.commit(); st.rerun()

elif menu == "💸 GASTOS":
    st.title("💸 Gastos"); cat = st.selectbox("Cat", ["Pienso", "Animales", "Salud", "Infraestructura"]); imp = st.number_input("€")
    if st.button("Guardar"): c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (datetime.now().strftime('%d/%m/%Y'), "Gasto", imp, cat, "General")); conn.commit(); st.rerun()

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Admin"); tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        st.dataframe(df)
        if st.button("Borrar Registro"): c.execute(f"DELETE FROM {tab} WHERE id=?", (st.number_input("ID", 0),)); conn.commit(); st.rerun()
