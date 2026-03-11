import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V17.3", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, kilos_finales REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, perdida_estimada REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS hitos(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT)")
    
    try: c.execute("ALTER TABLE ventas ADD COLUMN kilos_finales REAL DEFAULT 0")
    except: pass
    conn.commit(); conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

inicializar_db()

# ====================== 2. LÓGICA DE CÁLCULOS ======================
lotes = cargar("lotes"); gastos = cargar("gastos"); ventas = cargar("ventas")
bajas = cargar("bajas"); hitos = cargar("hitos")

def obtener_consumo_diario(raza, edad_dias):
    if raza in ["Roja", "Blanca", "Chocolate"]:
        return 0.040 if edad_dias < 30 else 0.085 if edad_dias < 120 else 0.125
    if raza == "Blanco Engorde":
        return 0.045 if edad_dias < 14 else 0.130 if edad_dias < 35 else 0.210
    if raza == "Campero":
        return 0.040 if edad_dias < 21 else 0.095 if edad_dias < 60 else 0.150
    if raza == "Codorniz":
        return 0.020 if edad_dias < 15 else 0.035
    return 0.110

def calc_pienso_real(cat, esp):
    kg_c = gastos[gastos['categoria'] == cat]['kilos_pienso'].sum() if not gastos.empty else 0
    cons_tot = 0; cons_hoy = 0
    if not lotes.empty:
        for _, r in lotes[lotes['especie'] == esp].iterrows():
            vivas = max(0, r['cantidad'] - (bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0))
            dias = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days
            for d in range(dias + 1):
                f = obtener_consumo_diario(r["raza"], r["edad_inicial"] + d)
                cons_tot += (vivas * f)
                if d == dias: cons_hoy += (vivas * f)
    return max(0, kg_c - cons_tot), cons_hoy

st_gal, c_gal = calc_pienso_real("Pienso Gallinas", "Gallinas")
st_pol, c_pol = calc_pienso_real("Pienso Pollos", "Pollos")
st_cod, c_cod = calc_pienso_real("Pienso Codornices", "Codornices")

# Finanzas
v_cash = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
v_home = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
g_tot = gastos['cantidad'].sum() if not gastos.empty else 0
inv_ini = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0

# ====================== 3. INTERFAZ ======================
seccion = st.sidebar.radio("MENÚ ELITE:", [
    "🏠 Dashboard", "🎄 Plan Navidad", "🐣 Alta Lotes", "📈 Crecimiento", 
    "🥚 Producción", "🌟 Primera Puesta", "💸 Gastos", "💰 Ventas/Consumo", 
    "💀 Bajas", "📜 Histórico", "💾 SEGURIDAD"
])

if seccion == "🏠 Dashboard":
    st.title("🏠 Control Maestro")
    if st_gal < 5: st.error(f"🚨 Pienso Gallinas Crítico: {st_gal:.1f}kg")
    if st_pol < 5: st.error(f"🚨 Pienso Pollos Crítico: {st_pol:.1f}kg")
    if st_cod < 2: st.error(f"🚨 Pienso Codornices Crítico: {st_cod:.1f}kg")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Caja (Cash)", f"{v_cash - g_tot - inv_ini:.2f}€")
    c2.metric("Ahorro Casa", f"{v_home:.2f}€")
    c3.metric("Inversión Aves", f"{inv_ini:.2f}€")
    c4.metric("Gastos Otros", f"{g_tot:.2f}€")
    
    st.divider()
    st.subheader("📦 Almacén de Pienso")
    p1, p2, p3 = st.columns(3)
    p1.metric("Gallinas", f"{st_gal:.1f} kg", f"-{c_gal:.2f}/día")
    p2.metric("Pollos", f"{st_pol:.1f} kg", f"-{c_pol:.2f}/día")
    p3.metric("Codornices", f"{st_cod:.1f} kg", f"-{c_cod:.2f}/día")

elif seccion == "🎄 Plan Navidad":
    st.title("🎄 Planificador Navidad")
    obj = datetime(datetime.now().year, 12, 18)
    col1, col2 = st.columns(2)
    with col1:
        st.info("🐔 **Pollo Blanco (Rápido)**")
        st.write(f"Fecha compra: **{(obj - timedelta(days=55)).strftime('%d de Octubre')}**")
    with col2:
        st.success("🐓 **Pollo Campero (Lento)**")
        st.write(f"Fecha compra: **{(obj - timedelta(days=90)).strftime('%d de Septiembre')}**")

elif seccion == "📈 Crecimiento":
    st.title("📈 Desarrollo de Lotes")
    metas = {"Roja": 150, "Blanca": 150, "Blanco Engorde": 55, "Campero": 90, "Codorniz": 45}
    for _, r in lotes.iterrows():
        edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
        m = metas.get(r["raza"], 100); porc = min(100, int((edad/m)*100))
        ya_pone = "🥚" if not hitos[(hitos['lote_id']==r['id']) & (hitos['tipo']=='Primera Puesta')].empty else ""
        st.write(f"**Lote {r['id']} ({r['raza']})** {ya_pone} - {edad} días")
        st.progress(porc/100)

elif seccion == "🥚 Producción":
    st.title("🥚 Registro de Producción")
    with st.form("f_prod"):
        f = st.date_input("Fecha")
        ids = lotes[lotes['especie'].isin(['Gallinas', 'Codornices'])]['id'].tolist() if not lotes.empty else []
        l_id = st.selectbox("Lote ID", ids); cant = st.number_input("Nº Huevos", 1)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(cant)))
            conn.commit(); st.rerun()

elif seccion == "🌟 Primera Puesta":
    st.title("🌟 Registro de Primera Puesta")
    with st.form("f_puesta"):
        ids = lotes[lotes['especie'].isin(['Gallinas', 'Codornices'])]['id'].tolist() if not lotes.empty else []
        l_id = st.selectbox("Lote ID", ids)
        f_h = st.date_input("Fecha primer huevo")
        if st.form_submit_button("Guardar Hito de Puesta"):
            conn = get_conn(); conn.execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?, 'Primera Puesta', ?)", (int(l_id), f_h.strftime("%d/%m/%Y")))
            conn.commit(); st.rerun()

elif seccion == "💰 Ventas/Consumo":
    st.title("💰 Ventas y Beneficio Real")
    with st.form("v_form"):
        f = st.date_input("Fecha"); t = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l_id = st.selectbox("Lote de procedencia", lotes['id'].tolist() if not lotes.empty else [])
        colx, coly = st.columns(2)
        con = colx.text_input("Producto"); imp = coly.number_input("Precio Venta €", 0.0)
        kg_f = colx.number_input("Kilos Finales (kg)", 0.0); cli = coly.text_input("Cliente/Quién")
        if st.form_submit_button("Registrar Venta"):
            conn = get_conn(); conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad, lote_id, kilos_finales) VALUES (?,?,?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cli, t, con, imp, int(l_id), kg_f))
            conn.commit(); st.rerun()

elif seccion == "💀 Bajas":
    st.title("💀 Registro de Bajas")
    with st.form("f_baja"):
        f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        cant = st.number_input("Cantidad", 1); mot = st.text_input("Motivo")
        if st.form_submit_button("Registrar Baja"):
            l_sel = lotes[lotes['id']==l_id].iloc[0]; perd = cant * l_sel['precio_ud']
            conn = get_conn(); conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo, perdida_estimada) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(cant), mot, perd))
            conn.commit(); st.rerun()

elif seccion == "🐣 Alta Lotes":
    st.title("🐣 Nuevo Lote")
    with st.form("f_alta"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cantidad", 1); ed = c1.number_input("Edad (días)", 0); pr = c2.number_input("Precio/Ud", 0.0)
        if st.form_submit_button("Registrar"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            conn.commit(); st.rerun()

elif seccion == "💸 Gastos":
    st.title("💸 Otros Gastos")
    with st.form("f_gasto"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2); imp = c1.number_input("Importe €", 0.0); kg = c2.number_input("Kilos", 0.0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); st.rerun()

elif seccion == "📜 Histórico":
    st.title("📜 Histórico")
    tabla = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    df = cargar(tabla); st.dataframe(df, use_container_width=True)
    id_del = st.number_input("ID a eliminar", 0)
    if st.button("Eliminar"):
        conn = get_conn(); conn.execute(f"DELETE FROM {tabla} WHERE id=?", (id_del,)); conn.commit(); st.rerun()

elif seccion == "💾 SEGURIDAD":
    st.title("💾 Seguridad")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("Descargar Base de Datos", f, "corral.db")
    if st.button("🔥 FORMATEAR SISTEMA"):
        if os.path.exists(DB_PATH): os.remove(DB_PATH); st.rerun()
