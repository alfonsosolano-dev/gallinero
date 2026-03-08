import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

DB_PATH = './data/corral_maestro_fusion.db'
if not os.path.exists('data'): os.makedirs('data')

# ====================== 2. BASE DE DATOS ======================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT,
        cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, raza TEXT, cantidad REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, raza TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    # Admin por defecto
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin','1234','Admin'))
    conn.commit(); conn.close()

inicializar_db()

# ====================== 3. LOGIN ======================
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})

def login():
    st.sidebar.title("🔐 Acceso")
    with st.sidebar.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT rango FROM usuarios WHERE nombre=? AND clave=?", (u,p))
            res = c.fetchone(); conn.close()
            if res:
                st.session_state.update({'autenticado': True, 'usuario': u, 'rango': res[0]})
                st.rerun()
            else: st.error("Usuario o contraseña incorrectos")

if not st.session_state['autenticado']:
    login()
    st.stop()

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})
    st.rerun()

# ====================== 4. FUNCIONES ======================
def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

# ====================== 5. MENÚ ======================
st.sidebar.write(f"👤 Usuario: **{st.session_state['usuario']}**")
menu = st.sidebar.radio("Menú:", ["🏠 Dashboard","🐣 Alta Animales","🥚 Puesta","☠️ Bajas","💰 Finanzas","📈 Crecimiento","📊 Rentabilidad","🎄 Navidad","🛠️ Admin"])

# ------------------- DASHBOARD -------------------
if menu=="🏠 Dashboard":
    st.title("🏠 Dashboard de Control")
    df_l = cargar('lotes'); df_v = cargar('ventas'); df_g = cargar('gastos'); df_p = cargar('produccion'); df_s = cargar('salud')
    # Población
    col1, col2, col3 = st.columns(3)
    col1.metric("Gallinas", int(df_l[df_l['especie']=='Gallinas']['cantidad'].sum() if not df_l.empty else 0))
    col2.metric("Pollos", int(df_l[df_l['especie']=='Pollos']['cantidad'].sum() if not df_l.empty else 0))
    col3.metric("Codornices", int(df_l[df_l['especie']=='Codornices']['cantidad'].sum() if not df_l.empty else 0))
    # Beneficio
    ing = df_v['total'].sum() if not df_v.empty else 0
    gas = df_g['importe'].sum() if not df_g.empty else 0
    st.metric("Beneficio Neto", f"{ing-gas:.2f}€")
    # Próximas vacunas
    st.subheader("💉 Próximas Vacunas")
    hoy = datetime.now().date()
    if not df_s.empty:
        df_s['fecha_dt'] = pd.to_datetime(df_s['fecha'], format='%d/%m/%Y', errors='coerce').dt.date
        proximos = df_s[df_s['fecha_dt'] <= hoy + timedelta(days=7)]
        if not proximos.empty:
            for _, r in proximos.iterrows(): st.warning(f"{r['tipo']} - Lote {r['lote_id']} ({r['fecha']})")
        else: st.success("Todo al día")
    else: st.info("Sin registros de salud")

# ------------------- ALTA ANIMALES -------------------
elif menu=="🐣 Alta Animales":
    st.title("🐣 Entrada de Animales")
    with st.form("fa"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas","Pollos","Codornices"])
        rz = st.text_input("Raza")
        can = st.number_input("Cantidad", min_value=1)
        e_ini = st.number_input("Edad inicial (días)", value=15)
        pre = st.number_input("Precio por unidad", min_value=0.0)
        if st.form_submit_button("Dar de Alta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado, usuario) VALUES (?,?,?,?,?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, pre, "Activo", st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("✅ Lote creado"); st.rerun()

# ------------------- PUESTA -------------------
elif menu=="🥚 Puesta":
    st.title("🥚 Registro de Puesta")
    df_l = cargar('lotes')
    if df_l.empty: st.warning("No hay lotes")
    else:
        with st.form("fp"):
            f = st.date_input("Fecha")
            l_id = st.selectbox("Lote", df_l['id'].tolist())
            can = st.number_input("Cantidad de huevos", min_value=1)
            if st.form_submit_button("Guardar"):
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO produccion (fecha, lote_id, raza, cantidad, especie, usuario) VALUES (?,?,?,?,?,?)",
                          (f.strftime('%d/%m/%Y'), l_id, df_l[df_l['id']==l_id]['raza'].values[0], can, df_l[df_l['id']==l_id]['especie'].values[0], st.session_state['usuario']))
                conn.commit(); conn.close(); st.success("✅ Puesta registrada"); st.rerun()

# ------------------- BAJAS -------------------
elif menu=="☠️ Bajas":
    st.title("☠️ Reportar Baja")
    df_l = cargar('lotes')
    with st.form("fb"):
        l_id = st.selectbox("Lote", df_l['id'].tolist() if not df_l.empty else [0])
        cant = st.number_input("Cantidad", min_value=1)
        motivo = st.selectbox("Motivo", ["Enfermedad","Depredador","Accidente","Desconocido"])
        if st.form_submit_button("Confirmar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO salud (fecha,lote_id,tipo,notas,usuario) VALUES (?,?,?,?,?)",
                      (datetime.now().strftime('%d/%m/%Y'), l_id, "Baja: "+motivo, f"{cant} aves", st.session_state['usuario']))
            conn.commit(); conn.close(); st.success(f"{cant} bajas registradas"); st.rerun()

# ------------------- FINANZAS -------------------
elif menu=="💰 Finanzas":
    st.title("💰 Gastos y Ventas")
    with st.form("ff"):
        tipo = st.selectbox("Tipo", ["Gasto","Venta"])
        cat = st.text_input("Categoría")
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)")
        if st.form_submit_button("Registrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha,concepto,importe,kilos,categoria,raza,usuario) VALUES (?,?,?,?,?,?,?)" if tipo=="Gasto" else
                      "INSERT INTO ventas (fecha,producto,cantidad,total,raza,especie,usuario) VALUES (?,?,?,?,?,?,?)",
                      (datetime.now().strftime('%d/%m/%Y'), con, imp, 0, cat, "General", st.session_state['usuario']))
            conn.commit(); conn.close(); st.success("✅ Registrado"); st.rerun()
    st.subheader("Últimos Movimientos")
    st.dataframe(cargar('gastos'))

# ------------------- CRECIMIENTO -------------------
elif menu=="📈 Crecimiento":
    st.title("📈 Control de Madurez")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'],'%d/%m/%Y')
            edad = (datetime.now()-f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            if row['especie']=='Codornices': meta=45
            elif row['especie']=='Pollos': meta=60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
            else: meta=140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
            prog = min(1.0, edad/meta)
            st.write(f"{row['especie']} {row['raza']} - {edad} días")
            st.progress(prog)

# ------------------- RENTABILIDAD -------------------
elif menu=="📊 Rentabilidad":
    st.title("📊 Análisis de Rentabilidad")
    df_g = cargar('gastos'); df_v = cargar('ventas')
    if not df_g.empty and not df_v.empty:
        ing = df_v['total'].sum(); gas = df_g['importe'].sum()
        st.metric("Beneficio Neto", f"{ing-gas:.2f}€")

# ------------------- NAVIDAD -------------------
elif menu=="🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    tipo = st.selectbox("Tipo de Pollo", ["Pollo Campero","Pollo Blanco"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026,12,24)-timedelta(days=dias)
    st.success(f"📅 Comprar pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# ------------------- ADMIN -------------------
elif menu=="🛠️ Admin":
    st.title("🛠️ Panel Administrativo")
    if st.session_state['rango']!="Admin":
        st.error("Acceso restringido")
    else:
        tab = st.selectbox("Seleccionar Tabla", ['lotes','produccion','gastos','ventas','salud','usuarios'])
        df = cargar(tab)
        st.dataframe(df)
        id_b = st.number_input("ID a borrar",0)
        if st.button("🗑️ BORRAR"):
            conn = get_conn(); c = conn.cursor()
            c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,))
            conn.commit(); conn.close(); st.success("Registro eliminado")
        st.divider()
        if st.button("📥 Descargar Backup Excel"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ['lotes','produccion','gastos','ventas','salud','usuarios']:
                    cargar(t).to_excel(writer, index=False, sheet_name=t)
            st.download_button("Descargar", output.getvalue(), f"backup_corral_{datetime.now().strftime('%Y%m%d')}.xlsx")
