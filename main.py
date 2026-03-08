import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="CORRAL MAESTRO V2", layout="wide", page_icon="🚜")

# ====================== 2. MOTOR DE BASE DE DATOS ======================
DB_PATH = './data/corral_v2.db'
if not os.path.exists('data'): os.makedirs('data')

def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn(); c = conn.cursor()
    # Tablas Optimizadas
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, raza TEXT, cantidad INTEGER, estado TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS finanzas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, categoria TEXT, concepto TEXT, importe REAL, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit(); conn.close()

inicializar_db()

# ====================== 3. CONTROL DE ACCESO ======================
if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Clave", type="password")
    if st.button("ENTRAR"):
        conn = get_conn(); c = conn.cursor()
        c.execute("SELECT nombre, rango FROM usuarios WHERE nombre=? AND clave=?", (u, p))
        res = c.fetchone()
        if res:
            st.session_state.auth = True
            st.session_state.user = res[0]
            st.session_state.rango = res[1]
            st.rerun()
        else: st.error("Datos incorrectos")
    st.stop()

# ====================== 4. FUNCIONES DE DATOS ======================
def leer(tabla):
    conn = get_conn()
    df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
    conn.close()
    return df

# ====================== 5. INTERFAZ PRINCIPAL ======================
st.sidebar.title(f"Bienvenido, {st.session_state.user}")
opcion = st.sidebar.selectbox("SELECCIONE TAREA:", [
    "🏠 Vista General", 
    "🐣 Entrada de Animales", 
    "🥚 Registro de Puesta", 
    "☠️ Reportar Baja", 
    "💰 Gastos y Ventas", 
    "📊 Estadísticas",
    "🛠️ Administración"
])

# ---------------- 🏠 VISTA GENERAL ----------------
if opcion == "🏠 Vista General":
    st.title("🏠 Estado Actual del Corral")
    df_l = leer('lotes')
    df_b = leer('bajas')
    
    if df_l.empty:
        st.info("No hay lotes activos. Empieza en 'Entrada de Animales'.")
    else:
        # Cálculo de animales reales (Total - Bajas)
        total_inicial = df_l['cantidad'].sum()
        total_bajas = df_b['cantidad'].sum() if not df_b.empty else 0
        actuales = total_inicial - total_bajas
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Aves en Corral", f"{int(actuales)} uds")
        c2.metric("Lotes Activos", len(df_l[df_l['estado']=='Activo']))
        c3.metric("Bajas Totales", int(total_bajas), delta_color="inverse")

# ---------------- 🐣 ENTRADA DE ANIMALES ----------------
elif opcion == "🐣 Entrada de Animales":
    st.title("🐣 Registro de Nuevo Lote")
    with st.form("nuevo_lote"):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo de Animal", ["Gallina Ponedora", "Pollo Engorde", "Codorniz", "Pavo", "Pato"])
            raza = st.selectbox("Raza", ["Isabrown", "Leghorn", "Ross 308", "Cobb 500", "Japónica", "Personalizada"])
            if raza == "Personalizada": raza = st.text_input("Escribe la raza:")
        with col2:
            cant = st.number_input("Cantidad inicial", min_value=1)
            fecha = st.date_input("Fecha de llegada")
        
        st.write("⚠️ **Confirme que los datos son correctos antes de guardar.**")
        if st.form_submit_button("✅ CONFIRMAR ENTRADA"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, tipo, raza, cantidad, estado, usuario) VALUES (?,?,?,?,?,?)",
                      (fecha.strftime('%d/%m/%Y'), tipo, raza, cant, 'Activo', st.session_state.user))
            conn.commit(); conn.close()
            st.success(f"¡Lote de {tipo} guardado!")

# ---------------- 🥚 REGISTRO DE PUESTA ----------------
elif opcion == "🥚 Registro de Puesta":
    st.title("🥚 Producción de Huevos")
    df_l = leer('lotes')
    ponedoras = df_l[df_l['tipo'].isin(['Gallina Ponedora', 'Codorniz'])]
    
    if ponedoras.empty:
        st.warning("No tienes lotes de ponedoras activos.")
    else:
        with st.form("puesta"):
            lote = st.selectbox("Seleccione Lote", ponedoras['id'].tolist())
            cant_h = st.number_input("Cantidad de huevos hoy", min_value=1)
            if st.form_submit_button("💾 REGISTRAR PUESTA"):
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO produccion (fecha, lote_id, cantidad, usuario) VALUES (?,?,?,?)",
                          (datetime.now().strftime('%d/%m/%Y'), lote, cant_h, st.session_state.user))
                conn.commit(); conn.close()
                st.success("Producción anotada.")

# ---------------- ☠️ REPORTAR BAJA ----------------
elif opcion == "☠️ Reportar Baja":
    st.title("☠️ Registro de Bajas (Mortalidad)")
    df_l = leer('lotes')
    with st.form("bajas"):
        l_id = st.selectbox("Lote afectado", df_l['id'].tolist())
        c_baja = st.number_input("Número de bajas", min_value=1)
        motivo = st.selectbox("Motivo", ["Enfermedad", "Depredador", "Accidente", "Desconocido"])
        if st.form_submit_button("❌ CONFIRMAR BAJA"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo, usuario) VALUES (?,?,?,?,?)",
                      (datetime.now().strftime('%d/%m/%Y'), l_id, c_baja, motivo, st.session_state.user))
            conn.commit(); conn.close()
            st.error(f"Se han registrado {c_baja} bajas.")

# ---------------- 💰 GASTOS Y VENTAS ----------------
elif opcion == "💰 Gastos y Ventas":
    st.title("💰 Movimientos Económicos")
    tipo_m = st.radio("Tipo de movimiento", ["Gasto (Dinero que sale)", "Venta (Dinero que entra)"])
    
    with st.form("finanzas"):
        f_fin = st.date_input("Fecha")
        if tipo_m == "Gasto (Dinero que sale)":
            cat = st.selectbox("Categoría", ["Pienso/Comida", "Salud", "Luz/Agua", "Infraestructura"])
        else:
            cat = st.selectbox("Categoría", ["Venta Huevos", "Venta Carne", "Abono", "Otros"])
            
        con = st.text_input("Concepto (Ej: Saco de pienso 25kg)")
        imp = st.number_input("Importe (€)", min_value=0.01)
        
        if st.form_submit_button("💰 REGISTRAR OPERACIÓN"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO finanzas (fecha, tipo, categoria, concepto, importe, usuario) VALUES (?,?,?,?,?,?)",
                      (f_fin.strftime('%d/%m/%Y'), tipo_m, cat, con, imp, st.session_state.user))
            conn.commit(); conn.close()
            st.success("Operación financiera guardada.")

# ---------------- 🛠️ ADMINISTRACIÓN ----------------
elif opcion == "🛠️ Administración":
    if st.session_state.rango != 'Admin':
        st.error("No tienes permisos de administrador.")
    else:
        st.title("🛠️ Configuración y Seguridad")
        tab1, tab2 = st.tabs(["👥 Usuarios", "💾 Base de Datos"])
        
        with tab1:
            with st.form("nuevo_u"):
                n_u = st.text_input("Nombre de usuario")
                n_c = st.text_input("Contraseña")
                if st.form_submit_button("CREAR USUARIO"):
                    try:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", (n_u, n_c, 'Editor'))
                        conn.commit(); conn.close(); st.success("Usuario creado.")
                    except: st.error("El usuario ya existe.")
        
        with tab2:
            if st.button("📥 Descargar Backup Excel"):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    for t in ['lotes', 'produccion', 'finanzas', 'bajas']:
                        leer(t).to_excel(writer, sheet_name=t, index=False)
                st.download_button("Click aquí para descargar", output.getvalue(), "backup_corral.xlsx")
