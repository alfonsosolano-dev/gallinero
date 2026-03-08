import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN INICIAL (Debe ser lo primero)
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

# ====================== 2. BASE DE DATOS Y MIGRACIONES ======================
if not os.path.exists('data'):
    os.makedirs('data')

DB_PATH = './data/corral_final_consolidado.db'

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Creación de tablas base
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, total REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha_primera_puesta TEXT, usuario TEXT)''')
    
    # MIGRACIÓN: Añadir columna 'usuario' si no existía en versiones previas
    for tabla in ['lotes', 'gastos', 'ventas', 'produccion', 'salud']:
        try:
            c.execute(f"ALTER TABLE {tabla} ADD COLUMN usuario TEXT")
        except sqlite3.OperationalError:
            pass # Ya existe
            
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 3. SISTEMA DE SESIÓN ======================
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})

def login():
    st.sidebar.title("🔐 Acceso Corral")
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
            else: st.error("Usuario/Clave incorrectos")

if not st.session_state['autenticado']:
    login()
    st.info("Inicia sesión para continuar.")
    st.stop()

# ====================== 4. FUNCIONES DE CARGA ======================
def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

def beneficio_mensual():
    df_g = cargar('gastos'); df_v = cargar('ventas')
    if df_g.empty and df_v.empty: return pd.DataFrame()
    if not df_g.empty: df_g['f'] = pd.to_datetime(df_g['fecha'], format='%d/%m/%Y', errors='coerce')
    if not df_v.empty: df_v['f'] = pd.to_datetime(df_v['fecha'], format='%d/%m/%Y', errors='coerce')
    
    g_m = df_g.groupby(pd.Grouper(key='f', freq='ME'))['importe'].sum() if not df_g.empty else pd.Series()
    v_m = df_v.groupby(pd.Grouper(key='f', freq='ME'))['total'].sum() if not df_v.empty else pd.Series()
    
    res = pd.DataFrame({'Ventas': v_m, 'Gastos': g_m}).fillna(0)
    res['Beneficio'] = res['Ventas'] - res['Gastos']
    res['mes'] = res.index.strftime('%b %Y')
    return res

# ====================== 5. INTERFAZ Y MENÚ ======================
st.sidebar.button("Cerrar Sesión", on_click=lambda: st.session_state.update({'autenticado': False}))
st.sidebar.write(f"👤 **{st.session_state['usuario']}** ({st.session_state['rango']})")
menu = st.sidebar.radio("MENÚ", ["🏠 DASHBOARD", "📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA AVES", "💉 SALUD", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# ---------------- DASHBOARD ----------------
if menu == "🏠 DASHBOARD":
    st.title("🏠 Dashboard Maestro")
    df_l = cargar('lotes'); df_v = cargar('ventas'); df_g = cargar('gastos'); df_s = cargar('salud')
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Aves Activas", int(df_l[df_l['estado']=='Activo']['cantidad'].sum()) if not df_l.empty else 0)
    c2.metric("Ingresos", f"{df_v['total'].sum() if not df_v.empty else 0:.2f}€")
    c3.metric("Gastos", f"{df_g['importe'].sum() if not df_g.empty else 0:.2f}€")
    
    st.divider()
    col_izq, col_der = st.columns([2, 1])
    with col_izq:
        df_b = beneficio_mensual()
        if not df_b.empty:
            st.plotly_chart(px.bar(df_b, x='mes', y='Beneficio', title="Balance Neto por Mes", color='Beneficio'))
    with col_der:
        st.subheader("🚨 Alertas Salud")
        hoy = datetime.now().date()
        if not df_s.empty:
            df_s['dt'] = pd.to_datetime(df_s['fecha'], format='%d/%m/%Y', errors='coerce').dt.date
            alertas = df_s[(df_s['dt'] >= hoy) & (df_s['dt'] <= hoy + timedelta(days=7))]
            for _, r in alertas.iterrows(): st.warning(f"{r['tipo']} - Lote {r['lote_id']}")
            if alertas.empty: st.success("Sin pendientes")

# ---------------- PUESTA ----------------
elif menu == "🥚 PUESTA":
    st.title("🥚 Registro de Puesta")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    lotes_activos = df_l[df_l['estado']=='Activo']
    if lotes_activos.empty: st.warning("No hay lotes activos.")
    else:
        with st.form("f_puesta"):
            lote_id = st.selectbox("Lote", lotes_activos['id'].tolist())
            row_l = lotes_activos[lotes_activos['id']==lote_id].iloc[0]
            
            f1_existente = None
            if not df_pm.empty and lote_id in df_pm['lote_id'].values:
                f1_existente = df_pm[df_pm['lote_id']==lote_id]['fecha_primera_puesta'].values[0]
                st.info(f"📅 Primera puesta: {f1_existente}")
            else:
                f1_input = st.date_input("Fecha primera puesta")
            
            cant = st.number_input("Cantidad de Huevos", 1)
            if st.form_submit_button("Guardar"):
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie, usuario) VALUES (?,?,?,?,?)",
                          (datetime.now().strftime('%d/%m/%Y'), row_l['raza'], cant, row_l['especie'], st.session_state['usuario']))
                if f1_existente is None:
                    c.execute("INSERT INTO puesta_manual (lote_id, fecha_primera_puesta, usuario) VALUES (?,?,?)",
                              (lote_id, f1_input.strftime('%d/%m/%Y'), st.session_state['usuario']))
                conn.commit(); conn.close(); st.success("Guardado"); st.rerun()

# ---------------- GASTOS ----------------
elif menu == "💸 GASTOS":
    st.title("💸 Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Medicinas", "Aves", "Equipo"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", 0.0)
        kg = st.number_input("Kilos", 0.0)
        if st.form_submit_button("Anotar Gasto"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, usuario) VALUES (?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, kg, cat, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Gasto registrado"); st.rerun()

# ---------------- ALTA AVES ----------------
elif menu == "🐣 ALTA AVES":
    st.title("🐣 Nuevo Lote")
    with st.form("f_alta"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.text_input("Raza")
        can = st.number_input("Cantidad", 1)
        ed = st.number_input("Edad (días)", 0)
        if st.form_submit_button("Crear"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), esp, rz, can, 'Activo', ed, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Lote creado"); st.rerun()

# ---------------- VENTAS ----------------
elif menu == "💰 VENTAS":
    st.title("💰 Ventas")
    with st.form("f_v"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Origen", ["Gallinas", "Pollos", "Codornices"])
        pro = st.text_input("Producto")
        val = st.number_input("Total (€)", 0.0)
        if st.form_submit_button("Cobrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO ventas (fecha, producto, total, especie, usuario) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), pro, val, esp, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Venta guardada"); st.rerun()

# ---------------- SALUD ----------------
elif menu == "💉 SALUD":
    st.title("💉 Salud")
    df_l = cargar('lotes')
    with st.form("f_s"):
        f = st.date_input("Fecha")
        l_id = st.selectbox("Lote", df_l['id'].tolist() if not df_l.empty else [0])
        acc = st.selectbox("Tipo", ["Vacuna", "Desparasitar", "Control"])
        not_s = st.text_area("Notas")
        if st.form_submit_button("Registrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO salud (fecha, lote_id, tipo, notas, usuario) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), l_id, acc, not_s, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Historial actualizado"); st.rerun()

# ---------------- CRECIMIENTO ----------------
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Control de Edad")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    if not df_l.empty:
        for _, r in df_l[df_l['estado']=='Activo'].iterrows():
            f_llegada = datetime.strptime(r['fecha'], '%d/%m/%Y')
            edad = (datetime.now() - f_llegada).days + r['edad_inicial']
            st.write(f"🔹 **Lote {r['id']}**: {r['raza']} - {edad} días")
            if not df_pm.empty and r['id'] in df_pm['lote_id'].values:
                st.caption(f"🥚 Poniendo desde: {df_pm[df_pm['lote_id']==r['id']]['fecha_primera_puesta'].values[0]}")
            st.progress(min(1.0, edad/150))

# ---------------- PLAN NAVIDAD ----------------
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Plan Navidad 2026")
    tipo = st.radio("Crianza", ["Campero (95 días)", "Blanco (60 días)"])
    d = 95 if "Campero" in tipo else 60
    f_c = datetime(2026, 12, 24) - timedelta(days=d)
    st.success(f"📅 Fecha ideal de compra: **{f_c.strftime('%d/%m/%Y')}**")

# ---------------- RENTABILIDAD ----------------
elif menu == "📊 RENTABILIDAD":
    st.title("📊 Rentabilidad")
    df_g = cargar('gastos')
    if not df_g.empty:
        st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="Gastos por Categoría"))
    else: st.info("Sin datos suficientes.")

# ---------------- ADMIN ----------------
elif menu == "🛠️ ADMIN":
    if st.session_state['rango'] != 'Admin':
        st.error("Acceso denegado.")
    else:
        st.title("🛠️ Panel de Control")
        t1, t2, t3 = st.tabs(["👥 Personal", "💾 Backup", "🗑️ Borrar"])
        with t1:
            with st.form("n_u"):
                u_n = st.text_input("Nuevo Usuario")
                u_c = st.text_input("Clave")
                u_r = st.selectbox("Rango", ["Editor", "Admin"])
                if st.form_submit_button("Añadir"):
                    try:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", (u_n, u_c, u_r))
                        conn.commit(); conn.close(); st.success("Añadido"); st.rerun()
                    except: st.error("El usuario ya existe")
            st.dataframe(cargar('usuarios'))
        with t2:
            st.subheader("Copia en Excel")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                for tab in ['lotes','gastos','ventas','produccion','salud','usuarios','puesta_manual']:
                    df = cargar(tab)
                    if not df.empty: df.to_excel(wr, sheet_name=tab, index=False)
            st.download_button("📥 Descargar Todo", buf.getvalue(), "backup_corral.xlsx")
        with t3:
            tab_b = st.selectbox("Tabla a limpiar", ['lotes','gastos','ventas','produccion','salud'])
            df_b = cargar(tab_b)
            st.dataframe(df_b)
            id_b = st.number_input("ID a eliminar", 0)
            if st.button("BORRAR PERMANENTE"):
                conn = get_conn(); c = conn.cursor()
                c.execute(f"DELETE FROM {tab_b} WHERE id=?", (id_b,))
                conn.commit(); conn.close(); st.success("Eliminado"); st.rerun()
