import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN DE PÁGINA (DEBE SER LA PRIMERA LÍNEA DE STREAMLIT)
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🚜")

# ====================== 2. MOTOR DE BASE DE DATOS ======================
# Cambiamos el nombre para evitar conflictos con versiones viejas
DB_PATH = './data/corral_maestro_2026.db'
if not os.path.exists('data'): 
    os.makedirs('data')

def get_conn(): 
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Tablas con la estructura NUEVA y LIMPIA
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha TEXT, tipo TEXT, raza TEXT, 
        cantidad INTEGER, estado TEXT, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha TEXT, lote_id INTEGER, cantidad INTEGER, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS finanzas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha TEXT, tipo TEXT, categoria TEXT, concepto TEXT, importe REAL, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS bajas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT, usuario TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    
    # Insertar admin solo si no existe
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit()
    conn.close()

# Ejecutamos la creación de tablas
try:
    inicializar_db()
except Exception as e:
    st.error(f"Error al iniciar base de datos: {e}")

# ====================== 3. CONTROL DE ACCESO ======================
if 'auth' not in st.session_state: 
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso al Sistema")
    with st.container():
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("ENTRAR"):
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT nombre, rango FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            conn.close()
            if res:
                st.session_state.auth = True
                st.session_state.user = res[0]
                st.session_state.rango = res[1]
                st.rerun()
            else: 
                st.error("Usuario o contraseña incorrectos")
    st.stop()

# ====================== 4. FUNCIONES DE DATOS ======================
def leer(tabla):
    conn = get_conn()
    try:
        df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

# ====================== 5. INTERFAZ PRINCIPAL ======================
st.sidebar.title(f"👤 {st.session_state.user}")
st.sidebar.write(f"Rango: `{st.session_state.rango}`")

opcion = st.sidebar.radio("SELECCIONE TAREA:", [
    "🏠 Vista General", 
    "🐣 Entrada de Animales", 
    "🥚 Registro de Puesta", 
    "☠️ Reportar Baja", 
    "💰 Gastos y Ventas", 
    "📊 Estadísticas",
    "🛠️ Administración"
])

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.auth = False
    st.rerun()

# ---------------- 🏠 VISTA GENERAL ----------------
if opcion == "🏠 Vista General":
    st.title("🏠 Estado Actual del Corral")
    df_l = leer('lotes')
    df_b = leer('bajas')
    
    if df_l.empty:
        st.info("El corral está vacío. Registra tu primer lote en 'Entrada de Animales'.")
    else:
        actuales = df_l['cantidad'].sum() - (df_b['cantidad'].sum() if not df_b.empty else 0)
        c1, c2, c3 = st.columns(3)
        c1.metric("Aves Totales", f"{int(actuales)} uds")
        c2.metric("Lotes Activos", len(df_l))
        c3.metric("Bajas", int(df_b['cantidad'].sum()) if not df_b.empty else 0, delta_color="inverse")
        
        st.divider()
        st.subheader("📋 Resumen de Lotes")
        st.dataframe(df_l[['id', 'tipo', 'raza', 'cantidad', 'fecha']], use_container_width=True)

# ---------------- 🐣 ENTRADA DE ANIMALES ----------------
elif opcion == "🐣 Entrada de Animales":
    st.title("🐣 Registro de Nuevo Lote")
    with st.form("form_alta"):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Animal", ["Gallina Ponedora", "Pollo Engorde", "Codorniz", "Pavo", "Pato"])
            raza = st.selectbox("Raza", ["Isabrown", "Leghorn", "Ross 308", "Cobb 500", "Japónica", "Personalizada"])
            if raza == "Personalizada": raza = st.text_input("Escribe la raza:")
        with col2:
            cant = st.number_input("Cantidad de aves", min_value=1, value=10)
            fecha = st.date_input("Fecha de entrada")
        
        st.write("---")
        if st.form_submit_button("✅ CONFIRMAR ENTRADA"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, tipo, raza, cantidad, estado, usuario) VALUES (?,?,?,?,?,?)",
                      (fecha.strftime('%d/%m/%Y'), tipo, raza, cant, 'Activo', st.session_state.user))
            conn.commit(); conn.close()
            st.success("¡Lote registrado con éxito!")
            st.balloons()

# ---------------- 🥚 REGISTRO DE PUESTA ----------------
elif opcion == "🥚 Registro de Puesta":
    st.title("🥚 Producción Diaria")
    df_l = leer('lotes')
    if df_l.empty:
        st.warning("No hay animales registrados.")
    else:
        with st.form("form_puesta"):
            l_id = st.selectbox("ID del Lote", df_l['id'].tolist())
            cant_h = st.number_input("Huevos recogidos", min_value=1)
            if st.form_submit_button("💾 GUARDAR REGISTRO"):
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO produccion (fecha, lote_id, cantidad, usuario) VALUES (?,?,?,?)",
                          (datetime.now().strftime('%d/%m/%Y'), l_id, cant_h, st.session_state.user))
                conn.commit(); conn.close()
                st.success("Producción anotada.")

# ---------------- ☠️ REPORTAR BAJA ----------------
elif opcion == "☠️ Reportar Baja":
    st.title("☠️ Registro de Bajas")
    df_l = leer('lotes')
    if df_l.empty:
        st.warning("No hay animales.")
    else:
        with st.form("form_bajas"):
            l_id = st.selectbox("Lote", df_l['id'].tolist())
            c_baja = st.number_input("Cantidad de bajas", min_value=1)
            motivo = st.selectbox("Motivo", ["Enfermedad", "Depredador", "Accidente", "Desconocido"])
            if st.form_submit_button("❌ CONFIRMAR BAJA"):
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo, usuario) VALUES (?,?,?,?,?)",
                          (datetime.now().strftime('%d/%m/%Y'), l_id, c_baja, motivo, st.session_state.user))
                conn.commit(); conn.close()
                st.error(f"Registradas {c_baja} bajas.")

# ---------------- 💰 GASTOS Y VENTAS ----------------
elif opcion == "💰 Gastos y Ventas":
    st.title("💰 Movimientos de Caja")
    with st.form("form_finanzas"):
        tipo_m = st.selectbox("Operación", ["Gasto", "Venta"])
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Suministros", "Venta Huevos", "Venta Carne", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("💰 REGISTRAR"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO finanzas (fecha, tipo, categoria, concepto, importe, usuario) VALUES (?,?,?,?,?,?)",
                      (datetime.now().strftime('%d/%m/%Y'), tipo_m, cat, con, imp, st.session_state.user))
            conn.commit(); conn.close()
            st.success("Operación guardada.")

# ---------------- 🛠️ ADMINISTRACIÓN ----------------
elif opcion == "🛠️ Administración":
    st.title("🛠️ Panel de Control")
    if st.session_state.rango != 'Admin':
        st.error("No tienes permisos.")
    else:
        if st.button("📥 Descargar Copia de Seguridad (Excel)"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ['lotes', 'produccion', 'finanzas', 'bajas', 'usuarios']:
                    leer(t).to_excel(writer, sheet_name=t, index=False)
            st.download_button("Descargar Archivo", output.getvalue(), "corral_backup.xlsx")
