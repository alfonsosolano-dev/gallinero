import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

if not os.path.exists('data'):
    os.makedirs('data')

DB_PATH = './data/corral_final_consolidado.db'

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Estructura consolidada de tablas
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT,
        cantidad INTEGER, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL,
        kilos REAL DEFAULT 0, categoria TEXT, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT,
        total REAL, especie TEXT, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT,
        cantidad REAL, especie TEXT, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS salud (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER,
        tipo TEXT, notas TEXT, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER,
        fecha_primera_puesta TEXT, usuario TEXT)''')
    
    # Usuario maestro
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 2. SISTEMA DE AUTENTICACIÓN ======================
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})

def login():
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

if not st.session_state['autenticado']:
    login()
    st.info("Inicia sesión para gestionar el corral.")
    st.stop()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})
    st.rerun()

# ====================== 3. LÓGICA DE DATOS ======================
def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

def beneficio_mensual():
    df_g = cargar('gastos'); df_v = cargar('ventas')
    if df_g.empty and df_v.empty: return pd.DataFrame()
    for df, col in [(df_g, 'importe'), (df_v, 'total')]:
        if not df.empty: df['fecha_dt'] = pd.to_datetime(df['fecha'], format='%d/%m/%Y', errors='coerce')
    
    g_m = df_g.groupby(pd.Grouper(key='fecha_dt', freq='ME'))['importe'].sum().reset_index() if not df_g.empty else pd.DataFrame()
    v_m = df_v.groupby(pd.Grouper(key='fecha_dt', freq='ME'))['total'].sum().reset_index() if not df_v.empty else pd.DataFrame()
    
    m = pd.merge(v_m, g_m, on='fecha_dt', how='outer').fillna(0)
    m['Beneficio'] = m['total'] - m['importe']
    m['mes'] = m['fecha_dt'].dt.strftime('%b %Y')
    return m.sort_values('fecha_dt')

# ====================== 4. NAVEGACIÓN Y MENÚ ======================
st.sidebar.divider()
st.sidebar.write(f"👤 **{st.session_state['usuario']}** | `{st.session_state['rango']}`")
menu = st.sidebar.radio("IR A:", ["🏠 DASHBOARD", "📊 RENTABILIDAD", "📈 MADUREZ", "🥚 REGISTRO PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA AVES", "💉 SALUD", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# ---------------- DASHBOARD ----------------
if menu == "🏠 DASHBOARD":
    st.title("🏠 Dashboard Maestro")
    df_l = cargar('lotes'); df_v = cargar('ventas'); df_g = cargar('gastos'); df_s = cargar('salud')
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Aves Activas", int(df_l[df_l['estado']=='Activo']['cantidad'].sum()) if not df_l.empty else 0)
    ing = df_v['total'].sum() if not df_v.empty else 0
    gas = df_g['importe'].sum() if not df_g.empty else 0
    col2.metric("Ingresos", f"{ing:.2f}€")
    col3.metric("Gastos", f"{gas:.2f}€", delta_color="inverse")
    
    st.divider()
    c_izq, c_der = st.columns([2, 1])
    with c_izq:
        df_b = beneficio_mensual()
        if not df_b.empty:
            st.plotly_chart(px.bar(df_b, x='mes', y='Beneficio', title="Balance Neto Mensual", color='Beneficio', text_auto='.2f'), use_container_width=True)
    with c_der:
        st.subheader("💉 Próximas Citas")
        hoy = datetime.now().date()
        if not df_s.empty:
            df_s['f_dt'] = pd.to_datetime(df_s['fecha'], format='%d/%m/%Y', errors='coerce').dt.date
            prox = df_s[(df_s['f_dt'] >= hoy) & (df_s['f_dt'] <= hoy + timedelta(days=7))]
            for _, r in prox.iterrows(): st.warning(f"{r['tipo']} - Lote {r['lote_id']}")
            if prox.empty: st.success("Sin tareas pendientes")

# ---------------- PUESTA ----------------
elif menu == "🥚 REGISTRO PUESTA":
    st.title("🥚 Producción Diaria")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    if df_l.empty: st.warning("Crea un lote primero.")
    else:
        with st.form("form_puesta"):
            l_id = st.selectbox("Lote", df_l[df_l['estado']=='Activo']['id'].tolist())
            datos_lote = df_l[df_l['id'] == l_id].iloc[0]
            
            f1_existente = None
            if not df_pm.empty and l_id in df_pm['lote_id'].values:
                f1_existente = df_pm[df_pm['lote_id']==l_id]['fecha_primera_puesta'].values[0]
                st.info(f"📅 Primera puesta: {f1_existente}")
            else:
                f1_input = st.date_input("Fecha de inicio de puesta")
            
            cant = st.number_input("Cantidad de Huevos", min_value=1)
            if st.form_submit_button("Guardar Registro"):
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie, usuario) VALUES (?,?,?,?,?)",
                          (datetime.now().strftime('%d/%m/%Y'), datos_lote['raza'], cant, datos_lote['especie'], st.session_state['usuario']))
                if f1_existente is None:
                    c.execute("INSERT INTO puesta_manual (lote_id, fecha_primera_puesta, usuario) VALUES (?,?,?)",
                              (l_id, f1_input.strftime('%d/%m/%Y'), st.session_state['usuario']))
                conn.commit(); conn.close(); st.success("Anotado"); st.rerun()

# ---------------- GASTOS ----------------
elif menu == "💸 GASTOS":
    st.title("💸 Gastos y Suministros")
    with st.form("form_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Medicinas", "Infraestructura", "Compra Aves"])
        con = st.text_input("Concepto / Marca")
        imp = st.number_input("Precio Total (€)", min_value=0.0)
        kg = st.number_input("Peso (Kilos)", min_value=0.0)
        if st.form_submit_button("Registrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, usuario) VALUES (?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, kg, cat, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Gasto guardado"); st.rerun()

# ---------------- ALTA ----------------
elif menu == "🐣 ALTA AVES":
    st.title("🐣 Entrada de Nuevo Lote")
    with st.form("form_alta"):
        f = st.date_input("Fecha de llegada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.text_input("Raza / Variedad")
        can = st.number_input("Cantidad inicial", min_value=1)
        ed = st.number_input("Edad actual (días)", value=0)
        if st.form_submit_button("Dar de Alta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), esp, rz, can, 'Activo', ed, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Lote registrado"); st.rerun()

# ---------------- MADUREZ ----------------
elif menu == "📈 MADUREZ":
    st.title("📈 Ciclo de Vida")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    for _, r in df_l[df_l['estado']=='Activo'].iterrows():
        f_llegada = datetime.strptime(r['fecha'], '%d/%m/%Y')
        edad_actual = (datetime.now() - f_llegada).days + r['edad_inicial']
        st.write(f"🏷️ **Lote {r['id']}**: {r['especie']} ({r['raza']})")
        st.write(f"🎂 Edad: {edad_actual} días")
        if not df_pm.empty and r['id'] in df_pm['lote_id'].values:
            f1 = df_pm[df_pm['lote_id']==r['id']]['fecha_primera_puesta'].values[0]
            st.caption(f"✨ Poniendo desde: {f1}")
        st.progress(min(1.0, edad_actual/150))
        st.divider()

# ---------------- VENTAS ----------------
elif menu == "💰 VENTAS":
    st.title("💰 Ventas de Productos")
    with st.form("form_v"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Origen", ["Gallinas", "Pollos", "Codornices"])
        pro = st.text_input("Producto (Huevos, Carne...)")
        val = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("Cobrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO ventas (fecha, producto, total, especie, usuario) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), pro, val, esp, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Venta anotada"); st.rerun()

# ---------------- SALUD ----------------
elif menu == "💉 SALUD":
    st.title("💉 Control Sanitario")
    df_l = cargar('lotes')
    with st.form("form_s"):
        f = st.date_input("Fecha programada/realizada")
        l_id = st.selectbox("Lote afectado", df_l['id'].tolist() if not df_l.empty else [0])
        accion = st.selectbox("Acción", ["Vacunación", "Desparasitación", "Control de Peso"])
        nota = st.text_area("Notas médicas")
        if st.form_submit_button("Anotar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO salud (fecha, lote_id, tipo, notas, usuario) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), l_id, accion, nota, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Historial médico guardado"); st.rerun()

# ---------------- NAVIDAD ----------------
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación Navidad 2026")
    tipo = st.radio("Tipo de crianza", ["Pollo Campero (95 días)", "Pollo Blanco (60 días)"])
    d = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=d)
    st.success(f"📅 Para Navidad, debes comprar los pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# ---------------- ADMIN ----------------
elif menu == "🛠️ ADMIN":
    if st.session_state['rango'] != 'Admin':
        st.error("Área restringida.")
    else:
        st.title("🛠️ Panel de Control")
        t1, t2, t3 = st.tabs(["👥 Usuarios", "💾 Backup", "🗑️ Depuración"])
        with t1:
            st.subheader("Registrar nuevo personal")
            with st.form("f_u"):
                u_n = st.text_input("Nombre")
                u_p = st.text_input("Clave")
                u_r = st.selectbox("Permisos", ["Editor", "Admin"])
                if st.form_submit_button("Crear"):
                    try:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", (u_n, u_p, u_r))
                        conn.commit(); conn.close(); st.success("Añadido"); st.rerun()
                    except: st.error("Ese usuario ya existe.")
            st.dataframe(cargar('usuarios'))
        with t2:
            st.subheader("Copia en Excel")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                for t in ['lotes','gastos','ventas','produccion','salud','usuarios','puesta_manual']:
                    df = cargar(t)
                    if not df.empty: df.to_excel(wr, sheet_name=t, index=False)
            st.download_button("📥 Descargar Backup", buf.getvalue(), "corral_final.xlsx")
        with t3:
            st.subheader("Eliminar registro específico")
            tab = st.selectbox("Tabla", ['lotes','gastos','ventas','produccion','salud'])
            df_v = cargar(tab)
            st.dataframe(df_v)
            id_b = st.number_input("ID a borrar", min_value=0)
            if st.button("🗑️ Borrar Permanente"):
                conn = get_conn(); c = conn.cursor()
                c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,))
                conn.commit(); conn.close(); st.success("Eliminado"); st.rerun()

# ---------------- RENTABILIDAD ----------------
elif menu == "📊 RENTABILIDAD":
    st.title("📊 Rentabilidad")
    df_g = cargar('gastos'); df_v = cargar('ventas')
    if not df_g.empty:
        st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="¿En qué gastamos más?"))
