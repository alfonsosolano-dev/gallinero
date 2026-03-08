import streamlit as st  # <--- Asegúrate de que esto esté arriba del todo
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# 1. ESTO DEBE SER LO PRIMERO QUE EJECUTA STREAMLIT
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

# ====================== BASE DE DATOS ======================
if not os.path.exists('data'):
    os.makedirs('data')

DB_PATH = './data/corral_final_consolidado.db'

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Crear tablas
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, total REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha_primera_puesta TEXT, usuario TEXT)''')
    
    # PARCHE: Añadir columna usuario a tablas viejas si no existe
    for t in ['lotes', 'gastos', 'ventas', 'produccion', 'salud']:
        try:
            c.execute(f"ALTER TABLE {t} ADD COLUMN usuario TEXT")
        except:
            pass
            
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== LOGIN ======================
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

# ====================== FUNCIONES ======================
def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

# ====================== NAVEGACIÓN ======================
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})
    st.rerun()

st.sidebar.write(f"👤 **{st.session_state['usuario']}**")
menu = st.sidebar.radio("IR A:", ["🏠 DASHBOARD", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA", "💉 SALUD", "🛠️ ADMIN"])

# (Aquí sigue el resto del código de las secciones...)
if menu == "🏠 DASHBOARD":
    st.title("🏠 Panel Principal")
    df_l = cargar('lotes')
    st.metric("Aves Activas", int(df_l['cantidad'].sum()) if not df_l.empty else 0)

elif menu == "🐣 ALTA":
    st.title("🐣 Alta de Aves")
    with st.form("f_alta"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.text_input("Raza")
        can = st.number_input("Cantidad", 1)
        ed = st.number_input("Edad", 0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), esp, rz, can, 'Activo', ed, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Lote creado"); st.rerun()

# (Repite la misma lógica de INSERT para el resto de secciones añadiendo el campo usuario al final)
