import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN VISUAL (ESTILO ANTERIOR)
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

# ====================== 2. BASE DE DATOS (CON PARCHE ANTICOLISIÓN) ======================
# Usamos un nombre nuevo para que no choque con los errores anteriores
DB_PATH = './data/corral_sistema_v3.db'
if not os.path.exists('data'): os.makedirs('data')

def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn(); c = conn.cursor()
    # Estructura completa de las tablas originales
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, total REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha_primera_puesta TEXT, usuario TEXT)''')
    
    # Usuario admin por defecto
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit(); conn.close()

inicializar_db()

# ====================== 3. LOGIN ======================
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})

if not st.session_state['autenticado']:
    st.sidebar.title("🔐 Acceso")
    with st.sidebar.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT rango FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            conn.close()
            if res:
                st.session_state.update({'autenticado': True, 'usuario': u, 'rango': res[0]})
                st.rerun()
            else: st.error("Acceso denegado")
    st.stop()

# ====================== 4. FUNCIONES CARGA ======================
def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

# ====================== 5. NAVEGACIÓN (TU INTERFAZ FAVORITA) ======================
st.sidebar.divider()
st.sidebar.write(f"👤 **{st.session_state['usuario']}**")
menu = st.sidebar.radio("IR A:", ["🏠 DASHBOARD", "📊 RENTABILIDAD", "📈 MADUREZ", "🥚 REGISTRO PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA AVES", "💉 SALUD", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.update({'autenticado': False})
    st.rerun()

# ---------------- DASHBOARD ----------------
if menu == "🏠 DASHBOARD":
    st.title("🏠 Dashboard Maestro")
    df_l = cargar('lotes'); df_v = cargar('ventas'); df_g = cargar('gastos')
    c1, c2, c3 = st.columns(3)
    c1.metric("Aves Activas", int(df_l['cantidad'].sum()) if not df_l.empty else 0)
    c2.metric("Ingresos", f"{df_v['total'].sum() if not df_v.empty else 0:.2f}€")
    c3.metric("Gastos", f"{df_g['importe'].sum() if not df_g.empty else 0:.2f}€")
    
    if not df_g.empty:
        st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="Distribución de Gastos"))

# ---------------- REGISTRO PUESTA (CON BOTÓN DE PRIMERA PUESTA) ----------------
elif menu == "🥚 REGISTRO PUESTA":
    st.title("🥚 Producción Diaria")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    activos = df_l[df_l['estado']=='Activo']
    
    if activos.empty: st.warning("No hay lotes activos.")
    else:
        with st.form("form_p"):
            l_id = st.selectbox("Lote", activos['id'].tolist())
            tiene_f1 = not df_pm.empty and l_id in df_pm['lote_id'].values
            
            if not tiene_f1:
                f_ini = st.date_input("🌟 Fecha de Primera Puesta")
            else:
                st.info(f"📅 Poniendo desde: {df_pm[df_pm['lote_id']==l_id]['fecha_primera_puesta'].values[0]}")
            
            cant = st.number_input("Cantidad de Huevos", min_value=1)
            if st.form_submit_button("✅ CONFIRMAR DATOS"):
                conn = get_conn(); c = conn.cursor()
                row = activos[activos['id']==l_id].iloc[0]
                c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie, usuario) VALUES (?,?,?,?,?)",
                          (datetime.now().strftime('%d/%m/%Y'), row['raza'], cant, row['especie'], st.session_state['usuario']))
                if not tiene_f1:
                    c.execute("INSERT INTO puesta_manual (lote_id, fecha_primera_puesta, usuario) VALUES (?,?,?)",
                              (l_id, f_ini.strftime('%d/%m/%Y'), st.session_state['usuario']))
                conn.commit(); conn.close(); st.success("Guardado"); st.rerun()

# ---------------- MADUREZ ----------------
elif menu == "📈 MADUREZ":
    st.title("📈 Ciclo de Vida")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    for _, r in df_l[df_l['estado']=='Activo'].iterrows():
        f_llegada = datetime.strptime(r['fecha'], '%d/%m/%Y')
        edad = (datetime.now() - f_llegada).days + r['edad_inicial']
        st.write(f"🏷️ **Lote {r['id']}**: {r['especie']} ({r['raza']}) - {edad} días")
        if not df_pm.empty and r['id'] in df_pm['lote_id'].values:
            st.caption(f"✨ Primera puesta: {df_pm[df_pm['lote_id']==r['id']]['fecha_primera_puesta'].values[0]}")
        st.progress(min(1.0, edad/150))

# ---------------- ALTA AVES ----------------
elif menu == "🐣 ALTA AVES":
    st.title("🐣 Nuevo Lote")
    with st.form("f_alta"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.text_input("Raza"); can = st.number_input("Cantidad", 1); ed = st.number_input("Edad (días)", 0)
        if st.form_submit_button("✅ CONFIRMAR ENTRADA"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), esp, rz, can, 'Activo', ed, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Lote creado"); st.rerun()

# ---------------- GASTOS ----------------
elif menu == "💸 GASTOS":
    st.title("💸 Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipo"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe (€)", 0.0)
        if st.form_submit_button("💰 REGISTRAR GASTO"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, usuario) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Anotado"); st.rerun()

# ---------------- PLAN NAVIDAD ----------------
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación Navidad 2026")
    tipo = st.radio("Crianza", ["Campero (95 días)", "Blanco (60 días)"])
    d = 95 if "Campero" in tipo else 60
    f_c = datetime(2026, 12, 24) - timedelta(days=d)
    st.success(f"📅 Compra los pollitos el: **{f_c.strftime('%d/%m/%Y')}**")

# ---------------- ADMIN ----------------
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Panel Admin")
    if st.session_state['rango'] == 'Admin':
        if st.button("📥 Descargar Backup Excel"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ['lotes','gastos','ventas','produccion','salud','usuarios','puesta_manual']:
                    cargar(t).to_excel(writer, index=False, sheet_name=t)
            st.download_button("Descargar", output.getvalue(), "corral_pro.xlsx")
    else: st.error("Sin permisos")
