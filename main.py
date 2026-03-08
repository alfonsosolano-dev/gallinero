import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
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
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    # Usuario administrador por defecto
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 2. SISTEMA DE SESIÓN / LOGIN ======================
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})

def login():
    st.sidebar.title("🔐 Acceso al Sistema")
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
            else:
                st.error("Usuario o clave incorrectos")

if not st.session_state['autenticado']:
    login()
    st.info("Por favor, inicia sesión en la barra lateral para acceder.")
    st.stop()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})
    st.rerun()

# ====================== 3. FUNCIONES AUXILIARES ======================
def cargar(tabla):
    conn = get_conn()
    try:
        return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()

# ====================== 4. MENÚ Y NAVEGACIÓN ======================
st.sidebar.write(f"👤 Usuario: **{st.session_state['usuario']}**")
menu = st.sidebar.radio("MENÚ:", ["🏠 DASHBOARD", "📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA", "💉 SALUD", "🎄 NAVIDAD", "🛠️ ADMIN"])

# ---------------- DASHBOARD ----------------
if menu == "🏠 DASHBOARD":
    st.title("🏠 Dashboard General")
    df_l = cargar('lotes'); df_v = cargar('ventas'); df_g = cargar('gastos'); df_p = cargar('produccion')
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Stock Aves", int(df_l['cantidad'].sum()) if not df_l.empty else 0)
    ing = df_v['total'].sum() if not df_v.empty else 0
    gas = df_g['importe'].sum() if not df_g.empty else 0
    c2.metric("Ingresos Totales", f"{ing:.2f}€")
    c3.metric("Gastos Totales", f"{gas:.2f}€", delta_color="inverse")
    
    st.divider()
    if not df_p.empty:
        st.subheader("Producción de Huevos (Últimos registros)")
        st.plotly_chart(px.bar(df_p.head(10), x='fecha', y='cantidad', color='raza', title="Puesta por Día"))

# ---------------- PUESTA ----------------
elif menu == "🥚 PUESTA":
    st.title("🥚 Registro de Puesta")
    df_l = cargar('lotes')
    razas = df_l['raza'].unique().tolist() if not df_l.empty else ["Roja", "Blanca"]
    with st.form("fp"):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", razas)
        can = st.number_input("Cantidad", min_value=1)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); c = conn.cursor()
            esp = "Gallinas" if rz != "Codorniz" else "Codornices"
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie, usuario) VALUES (?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), rz, can, esp, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Registrado"); st.rerun()

# ---------------- GASTOS ----------------
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    with st.form("fg"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        kgs = st.number_input("Kilos", min_value=0.0)
        if st.form_submit_button("Guardar Gasto"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, raza, usuario) VALUES (?,?,?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), con, imp, kgs, cat, "General", st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Gasto guardado"); st.rerun()

# ---------------- ALTA ANIMALES ----------------
elif menu == "🐣 ALTA":
    st.title("🐣 Alta de Lotes")
    with st.form("fa"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.text_input("Raza (Ej: Campero, Roja...)")
        can = st.number_input("Cantidad", min_value=1)
        e_ini = st.number_input("Edad Inicial (Días)", value=0)
        if st.form_submit_button("Crear Lote"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (?,?,?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), esp, rz, can, "Activo", e_ini, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Lote creado"); st.rerun()

# ---------------- SALUD ----------------
elif menu == "💉 SALUD":
    st.title("💉 Registro Sanitario")
    df_l = cargar('lotes')
    with st.form("fs"):
        f = st.date_input("Fecha")
        l_id = st.selectbox("Lote ID", df_l['id'].tolist() if not df_l.empty else [0])
        tipo = st.selectbox("Tipo", ["Vacuna", "Desparasitación", "Tratamiento"])
        nota = st.text_area("Notas")
        if st.form_submit_button("Guardar Salud"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO salud (fecha, lote_id, tipo, notas, usuario) VALUES (?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), l_id, tipo, nota, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Historial actualizado"); st.rerun()

# ---------------- ADMIN ----------------
elif menu == "🛠️ ADMIN":
    if st.session_state['rango'] != 'Admin':
        st.error("Acceso restringido a Administradores.")
    else:
        st.title("🛠️ Panel Administrativo")
        t1, t2, t3 = st.tabs(["👥 Gestión Usuarios", "💾 Backup", "🗑️ Mantenimiento"])
        
        with t1:
            st.subheader("Nuevo Usuario")
            with st.form("nu"):
                un = st.text_input("Nombre")
                up = st.text_input("Clave")
                ur = st.selectbox("Rango", ["Editor", "Admin"])
                if st.form_submit_button("Crear"):
                    try:
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", (un, up, ur))
                        conn.commit(); conn.close(); st.success("Usuario creado"); st.rerun()
                    except: st.error("El usuario ya existe")
            st.dataframe(cargar('usuarios'))

        with t2:
            st.subheader("Copia de Seguridad (Excel)")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for tab in ['lotes','gastos','ventas','produccion','salud','usuarios']:
                    df = cargar(tab)
                    if not df.empty: df.to_excel(writer, sheet_name=tab, index=False)
            st.download_button("📥 Descargar Todo en Excel", output.getvalue(), file_name="corral_backup.xlsx")

        with t3:
            st.subheader("Eliminar Registros")
            sel_t = st.selectbox("Tabla", ['lotes','gastos','ventas','produccion','salud'])
            df_view = cargar(sel_t)
            st.dataframe(df_view)
            id_del = st.number_input("ID a eliminar", min_value=0)
            if st.button("🗑️ Eliminar Permanente"):
                conn = get_conn(); c = conn.cursor()
                c.execute(f"DELETE FROM {sel_t} WHERE id=?", (id_del,))
                conn.commit(); conn.close(); st.success("Borrado"); st.rerun()

# ---------------- RENTABILIDAD, CRECIMIENTO, NAVIDAD, VENTAS ----------------
# (Implementaciones rápidas para completar el código)
elif menu == "💰 VENTAS":
    st.title("💰 Ventas")
    with st.form("fv"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        prod = st.text_input("Producto"); tot = st.number_input("Total (€)", min_value=0.0)
        if st.form_submit_button("Registrar Venta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, especie, usuario) VALUES (?,?,?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), prod, 1, tot, "General", esp, st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("Venta guardada"); st.rerun()

elif menu == "📈 CRECIMIENTO":
    st.title("📈 Control de Madurez")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, r in df_l[df_l['estado']=='Activo'].iterrows():
            f_e = datetime.strptime(r['fecha'], '%d/%m/%Y')
            edad = (datetime.now() - f_e).days + int(r['edad_inicial'])
            st.write(f"🔹 {r['especie']} {r['raza']} - {edad} días")
            st.progress(min(1.0, edad/120))

elif menu == "🎄 NAVIDAD":
    st.title("🎄 Plan Navidad 2026")
    t = st.selectbox("Tipo", ["Pollo Campero", "Pollo Blanco"])
    d = 95 if "Campero" in t else 60
    f_c = datetime(2026, 12, 24) - timedelta(days=d)
    st.success(f"📅 Fecha de compra: **{f_c.strftime('%d/%m/%Y')}**")

elif menu == "📊 RENTABILIDAD":
    st.title("📊 Rentabilidad")
    st.write("Consulta el balance general en el Dashboard.")
