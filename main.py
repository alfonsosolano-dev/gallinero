import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN
st.set_page_config(page_title="CORRAL MAESTRO LOCAL", layout="wide", page_icon="🐓")

# ====================== 2. MOTOR DE BASE DE DATOS LOCAL ======================
def get_connection():
    return sqlite3.connect("corral.db", check_same_thread=False)

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, estado TEXT, edad_inicial INTEGER, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bajas 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha_primera_puesta TEXT)''')
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 3. LOGIN SENCILLO ======================
if 'auth' not in st.session_state:
    st.session_state.update({'auth': False, 'user': ""})

if not st.session_state.auth:
    st.title("🔐 Acceso al Corral")
    u = st.text_input("Usuario")
    p = st.text_input("Clave", type="password")
    if st.button("ENTRAR"):
        if u == "admin" and p == "1234":
            st.session_state.update({'auth': True, 'user': "Administrador"})
            st.rerun()
        else: st.error("Clave incorrecta")
    st.stop()

# ====================== 4. INTERFAZ Y MENÚ ======================
menu = st.sidebar.radio("MENÚ", ["🏠 DASHBOARD", "🥚 PUESTA", "🐣 ALTA AVES", "☠️ BAJAS", "💸 GASTOS", "💾 SEGURIDAD"])

# ---------------- 🏠 DASHBOARD ----------------
if menu == "🏠 DASHBOARD":
    st.title("🏠 Estado General")
    conn = get_connection()
    df_l = pd.read_sql("SELECT * FROM lotes", conn)
    df_b = pd.read_sql("SELECT * FROM bajas", conn)
    conn.close()
    
    total_aves = (df_l['cantidad'].sum() if not df_l.empty else 0) - (df_b['cantidad'].sum() if not df_b.empty else 0)
    st.metric("Aves en el Corral", f"{int(total_aves)} uds")

# ---------------- 🥚 PUESTA ----------------
elif menu == "🥚 PUESTA":
    st.title("🥚 Registro de Huevos")
    conn = get_connection()
    activos = pd.read_sql("SELECT * FROM lotes WHERE estado='Activo'", conn)
    if activos.empty: st.warning("No hay lotes.")
    else:
        with st.form("f"):
            l_id = st.selectbox("Lote", activos['id'].tolist())
            cant = st.number_input("Huevos", 1)
            if st.form_submit_button("Guardar"):
                c = conn.cursor()
                c.execute("INSERT INTO produccion (fecha, lote_id, cantidad) VALUES (?,?,?)", 
                          (datetime.now().strftime('%d/%m/%Y'), l_id, cant))
                conn.commit()
                st.success("¡Registrado!")
    conn.close()

# ---------------- 🐣 ALTA AVES ----------------
elif menu == "🐣 ALTA AVES":
    st.title("🐣 Nuevo Lote")
    with st.form("f"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        rz = st.text_input("Raza", "Roja")
        can = st.number_input("Cantidad", 1)
        ed = st.number_input("Edad inicial (días)", 0)
        if st.form_submit_button("Crear"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial) VALUES (?,?,?,?,'Activo',?)",
                      (datetime.now().strftime('%d/%m/%Y'), esp, rz, can, ed))
            conn.commit()
            conn.close()
            st.success("Lote creado")

# ---------------- 💾 SEGURIDAD (LA CLAVE) ----------------
elif menu == "💾 SEGURIDAD":
    st.title("💾 Gestión de Datos")
    st.info("Como estamos en modo local, usa esta sección para no perder tus datos.")
    
    # BOTÓN PARA DESCARGAR
    with open("corral.db", "rb") as f:
        st.download_button("📥 DESCARGAR COPIA DE SEGURIDAD (DB)", f, "corral_backup.db")
    
    st.divider()
    
    # BOTÓN PARA SUBIR
    st.subheader("📤 Restaurar Copia")
    archivo_subido = st.file_uploader("Sube tu archivo .db para recuperar tus datos", type="db")
    if archivo_subido:
        with open("corral.db", "wb") as f:
            f.write(archivo_subido.getbuffer())
        st.success("✅ Datos restaurados. ¡Reinicia la página!")
