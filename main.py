import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN DE PÁGINA ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

# ====================== 2. BASE DE DATOS ======================
DB_PATH = './data/corral_maestro_2026.db'
if not os.path.exists('data'):
    os.makedirs('data')

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Tablas principales
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, especie TEXT, raza TEXT,
        tipo_engorde TEXT, edad_inicial INTEGER DEFAULT 0,
        cantidad INTEGER, precio_ud REAL, estado TEXT, usuario TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, lote_id INTEGER,
        cantidad INTEGER, especie TEXT, raza TEXT, usuario TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0,
        categoria TEXT, raza TEXT, usuario TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, producto TEXT, cantidad INTEGER, total REAL,
        raza TEXT, especie TEXT, usuario TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE, clave TEXT, rango TEXT
    )''')
    # Usuario admin por defecto
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 3. LOGIN ======================
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

# ====================== 4. FUNCIONES AUXILIARES ======================
def cargar(tabla):
    conn = get_conn()
    try:
        return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()

# ====================== 5. MENÚ ======================
st.sidebar.write(f"👤 Usuario: **{st.session_state['usuario']}**")
st.sidebar.write(f"Rango: {st.session_state['rango']}")
menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📊 Rentabilidad", "📈 Crecimiento", "🥚 Puesta", 
                                   "💸 Gastos", "💰 Ventas", "🐣 Alta Animales", "💉 Salud", 
                                   "🎄 Navidad", "🛠️ Administración"])

# ====================== 6. DASHBOARD ======================
if menu == "🏠 Dashboard":
    st.title("🏠 Estado del Corral")
    df_l = cargar('lotes'); df_p = cargar('produccion'); df_v = cargar('ventas'); df_g = cargar('gastos')
    tot_aves = df_l['cantidad'].sum() if not df_l.empty else 0
    tot_gastos = df_g['importe'].sum() if not df_g.empty else 0
    tot_ventas = df_v['total'].sum() if not df_v.empty else 0
    tot_beneficio = tot_ventas - tot_gastos
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Aves", tot_aves)
    c2.metric("Ingresos (€)", f"{tot_ventas:.2f}")
    c3.metric("Beneficio Neto (€)", f"{tot_beneficio:.2f}")

# ====================== 7. RENTABILIDAD ======================
elif menu == "📊 Rentabilidad":
    st.title("📊 Rentabilidad por Especie")
    df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    tabs = st.tabs(["Global", "Gallinas", "Pollos", "Codornices"])
    # Global
    with tabs[0]:
        g_total = df_g['importe'].sum() if not df_g.empty else 0
        v_total = df_v['total'].sum() if not df_v.empty else 0
        st.metric("Beneficio Total", f"{v_total - g_total:.2f}€")
    # Por especie
    especies = ["Gallinas", "Pollos", "Codornices"]
    for i, esp in enumerate(especies, 1):
        with tabs[i]:
            g_e = df_g[df_g['categoria'].str.contains(esp, na=False)]['importe'].sum() if not df_g.empty else 0
            v_e = df_v[df_v['especie'] == esp]['total'].sum() if not df_v.empty else 0
            st.metric(f"Balance {esp}", f"{v_e - g_e:.2f}€")
            p_data = df_p[df_p['especie'] == esp]
            if not p_data.empty:
                st.plotly_chart(px.line(p_data, x='fecha', y='cantidad', color='raza', title=f"Producción {esp}"))

# ====================== 8. CRECIMIENTO ======================
elif menu == "📈 Crecimiento":
    st.title("📈 Madurez de Lotes")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
            else: meta = 140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
            prog = min(1.0, edad/meta)
            with st.expander(f"{row['especie']} {row['raza']} - {edad} días"):
                st.progress(prog)
                st.write(f"Meta: {meta} días | Progreso: {int(prog*100)}%")
                if prog >= 0.8 and row['especie'] != 'Gallinas': st.warning("⚠️ Reposición próxima")

# ====================== 9. PUESTA ======================
elif menu == "🥚 Puesta":
    st.title("🥚 Registro de Puesta")
    df_l = cargar('lotes')
    if df_l.empty:
        st.warning("No hay lotes registrados.")
    else:
        razas_por_especie = {
            "Gallinas": ["Roja", "Blanca", "Chocolate"],
            "Pollos": ["Pollo Blanco (Engorde)", "Pollo Campero"],
            "Codornices": ["Codorniz Japónica"]
        }
        with st.form("fp"):
            f = st.date_input("Fecha")
            esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
            razas_disponibles = razas_por_especie.get(esp, [])
            rz = st.selectbox("Raza", razas_disponibles + ["Otra"])
            if rz == "Otra": rz = st.text_input("Escribe la raza")
            can = st.number_input("Cantidad de huevos", min_value=1)
            if st.form_submit_button("Guardar"):
                conn = get_conn(); c = conn.cursor()
                c.execute("INSERT INTO produccion (fecha, lote_id, cantidad, especie, raza, usuario) VALUES (?,?,?,?,?,?)",
                          (f.strftime('%d/%m/%Y'), 0, can, esp, rz, st.session_state['usuario']))
                conn.commit(); conn.close()
                st.success("✅ Puesta registrada")
                st.rerun()

# ====================== 10. GASTOS ======================
elif menu == "💸 Gastos":
    st.title("💸 Registro de Gastos")
    with st.form("fg"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        kgs = st.number_input("Kilos", min_value=0.0)
        if st.form_submit_button("Registrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, raza, usuario) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, kgs, cat, "General", st.session_state['usuario']))
            conn.commit(); conn.close()
            st.success("✅ Gasto guardado")
            st.rerun()

# ====================== 11. VENTAS ======================
elif menu == "💰 Ventas":
    st.title("💰 Registro de Ventas")
    with st.form("fv"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        prod = st.text_input("Producto")
        tot = st.number_input("Total (€)", min_value=0.0)
        if st.form_submit_button("Registrar Venta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, especie, usuario) VALUES (?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), prod, 1, tot, "General", esp, st.session_state['usuario']))
            conn.commit(); conn.close()
            st.success("✅ Venta registrada")
            st.rerun()

# ====================== 12. ALTA ANIMALES ======================
elif menu == "🐣 Alta Animales":
    st.title("🐣 Entrada de Animales")
    razas_por_especie = {
        "Gallinas": ["Roja", "Blanca", "Chocolate"],
        "Pollos": ["Pollo Blanco (Engorde)", "Pollo Campero"],
        "Codornices": ["Codorniz Japónica"]
    }
    with st.form("fa"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        razas_disponibles = razas_por_especie.get(esp, [])
        rz = st.selectbox("Raza", razas_disponibles + ["Otra"])
        if rz == "Otra": rz = st.text_input("Escribe la raza")
        can = st.number_input("Cantidad", min_value=1)
        e_ini = st.number_input("Edad inicial (días)", value=15)
        pre = st.number_input("Precio por unidad (€)", min_value=0.0)
        if st.form_submit_button("Dar de Alta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado, usuario) VALUES (?,?,?,?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, pre, "Activo", st.session_state['usuario']))
            conn.commit(); conn.close()
            st.success("✅ Lote creado")
            st.rerun()

# ====================== 13. SALUD ======================
elif menu == "💉 Salud":
    st.title("💉 Registro Sanitario")
    df_l = cargar('lotes')
    with st.form("fs"):
        f = st.date_input("Fecha")
        l_id = st.selectbox("Lote", df_l['id'].tolist() if not df_l.empty else [0])
        tipo = st.selectbox("Tipo", ["Vacuna", "Desparasitación", "Tratamiento"])
        nota = st.text_area("Notas")
        if st.form_submit_button("Guardar Salud"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO salud (fecha, lote_id, tipo, notas, usuario) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), l_id, tipo, nota, st.session_state['usuario']))
            conn.commit(); conn.close()
            st.success("✅ Registro médico guardado")
            st.rerun()

# ====================== 14. NAVIDAD ======================
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    tipo = st.selectbox("Tipo de Pollo", ["Pollo Campero", "Pollo Blanco"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=dias)
    st.success(f"📅 Comprar pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# ====================== 15. ADMINISTRACIÓN ======================
elif menu == "🛠️ Administración":
    st.title("🛠️ Panel Administrativo")
    if st.session_state['rango'] != 'Admin':
        st.error("Acceso restringido a Administradores.")
    else:
        tab = st.selectbox("Tabla", ['lotes','produccion','gastos','ventas','salud','usuarios'])
        df = cargar(tab)
        st.dataframe(df)
        id_del = st.number_input("ID a borrar", min_value=0)
        if st.button("🗑️ Eliminar Registro"):
            conn = get_conn(); c = conn.cursor()
            c.execute(f"DELETE FROM {tab} WHERE id=?", (id_del,))
            conn.commit(); conn.close()
            st.success("✅ Registro eliminado")
            st.rerun()

        st.divider()
        st.subheader("💾 Backup Completo")
        if st.button("📥 Descargar Excel"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ['lotes','produccion','gastos','ventas','salud','usuarios']:
                    df_b = cargar(t)
                    df_b.to_excel(writer, index=False, sheet_name=t)
            st.download_button("📥 Descargar Backup", output.getvalue(), file_name=f"backup_corral_{datetime.now().strftime('%Y%m%d')}.xlsx")
