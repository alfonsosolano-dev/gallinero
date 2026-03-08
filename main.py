import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN Y DB ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide")

if not os.path.exists('data'):
    os.makedirs('data')

DB_PATH = './data/corral_final_consolidado.db'

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Tablas con columna 'usuario' para trazabilidad
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, raza TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT)''')
    # TABLA DE USUARIOS
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    
    # Usuarios por defecto
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 2. SISTEMA DE SESIÓN ======================
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})

def login():
    st.sidebar.title("🔐 Acceso")
    with st.sidebar.form("login"):
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
            else: st.error("Error de acceso")

if not st.session_state['autenticado']:
    login()
    st.info("Inicia sesión para continuar.")
    st.stop()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})
    st.rerun()

# ====================== 3. FUNCIONES ======================
def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    finally: conn.close()

# ====================== 4. MENÚ ======================
st.sidebar.write(f"👤 **{st.session_state['usuario']}** ({st.session_state['rango']})")
menu = st.sidebar.radio("IR A:", ["🏠 DASHBOARD", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA", "💉 SALUD", "🛠️ ADMIN"])

# ---------------- DASHBOARD ----------------
if menu == "🏠 DASHBOARD":
    st.title("🏠 Dashboard")
    df_l = cargar('lotes'); df_v = cargar('ventas'); df_g = cargar('gastos')
    c1, c2, c3 = st.columns(3)
    c1.metric("Stock Animales", int(df_l['cantidad'].sum()) if not df_l.empty else 0)
    c2.metric("Ingresos", f"{df_v['total'].sum() if not df_v.empty else 0:.2f}€")
    c3.metric("Gastos", f"{df_g['importe'].sum() if not df_g.empty else 0:.2f}€")

# ---------------- ADMIN + GESTIÓN USUARIOS ----------------
elif menu == "🛠️ ADMIN":
    if st.session_state['rango'] != 'Admin':
        st.error("Acceso denegado.")
    else:
        st.title("🛠️ Administración")
        t_admin = st.tabs(["👥 Usuarios", "💾 Backup", "🗑️ Borrar Datos"])
        
        with t_admin[0]:
            st.subheader("Crear Nuevo Usuario")
            with st.form("nuevo_user"):
                n_u = st.text_input("Nombre de Usuario")
                n_p = st.text_input("Contraseña")
                n_r = st.selectbox("Rango", ["Editor", "Admin"])
                if st.form_submit_button("Añadir Usuario"):
                    try:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", (n_u, n_p, n_r))
                        conn.commit(); conn.close(); st.success("Usuario creado"); st.rerun()
                    except: st.error("El usuario ya existe.")
            st.write("Usuarios actuales:")
            st.dataframe(cargar('usuarios'))

        with t_admin[1]:
            st.subheader("Descargar Base de Datos")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ['lotes','gastos','ventas','produccion','salud','usuarios']:
                    df = cargar(t)
                    if not df.empty: df.to_excel(writer, sheet_name=t, index=False)
            st.download_button("📥 Descargar Excel", output.getvalue(), file_name="corral_pro.xlsx")

        with t_admin[2]:
            st.subheader("Eliminar Registros")
            tab_del = st.selectbox("Tabla", ['lotes','gastos','ventas','produccion','salud'])
            df_del = cargar(tab_del)
            st.dataframe(df_del)
            id_del = st.number_input("ID a borrar", min_value=0)
            if st.button("🗑️ Confirmar Borrado"):
                conn = get_conn(); c = conn.cursor()
                c.execute(f"DELETE FROM {tab_del} WHERE id=?", (id_del,))
                conn.commit(); conn.close(); st.rerun()

# (Secciones de Puesta, Gastos, etc. simplificadas con 'usuario')
elif menu == "🥚 PUESTA":
    st.title("🥚 Puesta")
    with st.form("p"):
        f = st.date_input("Fecha")
        can = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO produccion (fecha, cantidad, usuario) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), can, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Guardado"); st.rerun()
