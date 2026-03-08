import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN VISUAL ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

# ====================== 2. MOTOR DE BASE DE DATOS ======================
DB_PATH = './data/corral_sistema_v4.db'
if not os.path.exists('data'): 
    os.makedirs('data')

def get_conn(): 
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn(); c = conn.cursor()
    # Tablas con estructura completa
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, total REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bajas 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha_primera_puesta TEXT, usuario TEXT)''')
    
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit(); conn.close()

inicializar_db()

# ====================== 3. CONTROL DE ACCESO ======================
if 'auth' not in st.session_state:
    st.session_state.update({'auth': False, 'user': "", 'rango': ""})

if not st.session_state.auth:
    st.title("🔐 Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Clave", type="password")
    if st.button("ENTRAR"):
        conn = get_conn(); c = conn.cursor()
        c.execute("SELECT nombre, rango FROM usuarios WHERE nombre=? AND clave=?", (u, p))
        res = c.fetchone()
        conn.close()
        if res:
            st.session_state.update({'auth': True, 'user': res[0], 'rango': res[1]})
            st.rerun()
        else: st.error("Acceso denegado")
    st.stop()

# ====================== 4. FUNCIONES DE CARGA ======================
def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

# ====================== 5. NAVEGACIÓN (TU INTERFAZ FAVORITA) ======================
st.sidebar.title(f"👤 {st.session_state.user}")
menu = st.sidebar.radio("IR A:", [
    "🏠 DASHBOARD", 
    "📈 MADUREZ", 
    "🥚 REGISTRO PUESTA", 
    "☠️ REPORTAR BAJA",
    "💸 GASTOS", 
    "💰 VENTAS", 
    "🐣 ALTA AVES", 
    "💉 SALUD", 
    "🎄 PLAN NAVIDAD", 
    "🛠️ ADMIN"
])

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.auth = False
    st.rerun()

# ---------------- 🏠 DASHBOARD ----------------
if menu == "🏠 DASHBOARD":
    st.title("🏠 Panel de Control General")
    df_l = cargar('lotes'); df_v = cargar('ventas'); df_g = cargar('gastos'); df_b = cargar('bajas')
    
    aves_iniciales = df_l['cantidad'].sum() if not df_l.empty else 0
    total_bajas = df_b['cantidad'].sum() if not df_b.empty else 0
    actuales = aves_iniciales - total_bajas

    c1, c2, c3 = st.columns(3)
    c1.metric("Aves Activas", f"{int(actuales)} uds")
    c2.metric("Ingresos", f"{df_v['total'].sum() if not df_v.empty else 0:.2f}€")
    c3.metric("Gastos", f"{df_g['importe'].sum() if not df_g.empty else 0:.2f}€")

# ---------------- 📈 MADUREZ ----------------
elif menu == "📈 MADUREZ":
    st.title("📈 Ciclo de Vida y Madurez")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    if df_l.empty: st.info("No hay lotes registrados.")
    for _, r in df_l[df_l['estado']=='Activo'].iterrows():
        f_llegada = datetime.strptime(r['fecha'], '%d/%m/%Y')
        edad = (datetime.now() - f_llegada).days + r['edad_inicial']
        st.subheader(f"Lote {r['id']} - {r['especie']} ({r['raza']})")
        st.write(f"🎂 Edad actual: **{edad} días**")
        if not df_pm.empty and r['id'] in df_pm['lote_id'].values:
            st.success(f"🥚 Poniendo desde: {df_pm[df_pm['lote_id']==r['id']]['fecha_primera_puesta'].values[0]}")
        st.progress(min(1.0, edad/150))
        st.divider()

# ---------------- 🥚 REGISTRO PUESTA ----------------
elif menu == "🥚 REGISTRO PUESTA":
    st.title("🥚 Producción Diaria")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    activos = df_l[df_l['estado']=='Activo']
    if activos.empty: st.warning("No hay lotes activos.")
    else:
        with st.form("f_puesta"):
            l_id = st.selectbox("Seleccione Lote", activos['id'].tolist())
            tiene_f1 = not df_pm.empty and l_id in df_pm['lote_id'].values
            if not tiene_f1:
                f_ini = st.date_input("🌟 Fecha de Primera Puesta (Solo la primera vez)")
            else:
                st.info(f"📅 Fecha de inicio registrada: {df_pm[df_pm['lote_id']==l_id]['fecha_primera_puesta'].values[0]}")
            cant = st.number_input("Cantidad de Huevos", min_value=1)
            if st.form_submit_button("✅ CONFIRMAR REGISTRO"):
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO produccion (fecha, lote_id, cantidad, usuario) VALUES (?,?,?,?)",
                          (datetime.now().strftime('%d/%m/%Y'), l_id, cant, st.session_state.user))
                if not tiene_f1:
                    c.execute("INSERT INTO puesta_manual (lote_id, fecha_primera_puesta, usuario) VALUES (?,?,?)",
                              (l_id, f_ini.strftime('%d/%m/%Y'), st.session_state.user))
                conn.commit(); conn.close(); st.success("Guardado"); st.rerun()

# ---------------- ☠️ REPORTAR BAJA ----------------
elif menu == "☠️ REPORTAR BAJA":
    st.title("☠️ Registro de Bajas")
    df_l = cargar('lotes')
    with st.form("f_bajas"):
        l_id = st.selectbox("Lote afectado", df_l['id'].tolist() if not df_l.empty else [0])
        c_baja = st.number_input("Cantidad", min_value=1)
        motivo = st.selectbox("Motivo", ["Enfermedad", "Depredador", "Accidente", "Desconocido"])
        if st.form_submit_button("❌ CONFIRMAR BAJA"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo, usuario) VALUES (?,?,?,?,?)",
                      (datetime.now().strftime('%d/%m/%Y'), l_id, c_baja, motivo, st.session_state.user))
            conn.commit(); conn.close(); st.error("Baja registrada."); st.rerun()

# ---------------- 💸 GASTOS ----------------
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    with st.form("f_gastos"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipo"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe (€)", 0.0)
        if st.form_submit_button("💰 GUARDAR GASTO"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, usuario) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, st.session_state.user))
            conn.commit(); conn.close(); st.success("Gasto anotado"); st.rerun()

# ---------------- 🐣 ALTA AVES ----------------
elif menu == "🐣 ALTA AVES":
    st.title("🐣 Nuevo Lote de Animales")
    with st.form("f_alta"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices", "Patos"])
        rz = st.text_input("Raza", value="Roja"); can = st.number_input("Cantidad", 1); ed = st.number_input("Edad Inicial (días)", 0)
        if st.form_submit_button("✅ CONFIRMAR ENTRADA"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), esp, rz, can, 'Activo', ed, st.session_state.user))
            conn.commit(); conn.close(); st.success("Lote creado"); st.balloons(); st.rerun()

# ---------------- 💉 SALUD ----------------
elif menu == "💉 SALUD":
    st.title("💉 Registro Sanitario")
    df_l = cargar('lotes')
    with st.form("f_salud"):
        l_id = st.selectbox("Lote", df_l['id'].tolist() if not df_l.empty else [0])
        tipo = st.selectbox("Tipo", ["Vacuna", "Desparasitación", "Tratamiento"])
        notas = st.text_area("Notas")
        if st.form_submit_button("💾 GUARDAR"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO salud (fecha, lote_id, tipo, notas, usuario) VALUES (?,?,?,?,?)",
                      (datetime.now().strftime('%d/%m/%Y'), l_id, tipo, notas, st.session_state.user))
            conn.commit(); conn.close(); st.success("Historial actualizado"); st.rerun()

# ---------------- 🎄 PLAN NAVIDAD ----------------
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación Campaña Navidad")
    tipo = st.radio("Tipo de Engorde", ["Pollo Campero (95 días)", "Pollo Blanco (60 días)"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=dias)
    st.success(f"📅 Para Navidad, debes comprar los pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# ---------------- 🛠️ ADMIN ----------------
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Panel de Administración")
    if st.session_state.rango == 'Admin':
        if st.button("📥 Descargar Todo (Excel)"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ['lotes','gastos','ventas','produccion','salud','bajas','puesta_manual']:
                    cargar(t).to_excel(writer, index=False, sheet_name=t)
            st.download_button("Click para Descargar", output.getvalue(), "corral_maestro_pro.xlsx")
    else: st.error("Acceso denegado.")
