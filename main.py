import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V15", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_y_reparar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, perdida_estimada REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS hitos(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT)")
    
    try: c.execute("ALTER TABLE gastos ADD COLUMN kilos_pienso REAL DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE bajas ADD COLUMN perdida_estimada REAL DEFAULT 0")
    except: pass
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

def eliminar_reg(tabla, id_reg):
    conn = get_conn()
    conn.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_reg,))
    conn.commit()
    conn.close()

inicializar_y_reparar_db()

# ====================== 2. CARGA DE DATOS Y CÁLCULOS ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas"); hitos = cargar("hitos")

# --- LÓGICA DE PIENSO DESCONTANDO CONSUMO ---
def calc_pienso_real(categoria_pienso, especie_filtro):
    kg_comprados = gastos[gastos['categoria'] == categoria_pienso]['kilos_pienso'].sum() if not gastos.empty else 0
    cons_diario_actual = 0
    total_consumido_hist = 0
    
    if not lotes.empty:
        for _, r in lotes[lotes['especie'] == especie_filtro].iterrows():
            b_l = bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0
            vivas = max(0, r['cantidad'] - b_l)
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias_desde_alta = (datetime.now() - f_l).days
            edad_hoy = dias_desde_alta + r["edad_inicial"]
            
            if especie_filtro == "Gallinas": f = 0.120
            elif especie_filtro == "Codornices": f = 0.030
            else: f = 0.05 if edad_hoy < 14 else 0.12 if edad_hoy < 30 else 0.18
            
            cons_diario_actual += (vivas * f)
            total_consumido_hist += (vivas * f * max(0, dias_desde_alta))
            
    return max(0, kg_comprados - total_consumido_hist), cons_diario_actual

st_gal, c_gal = calc_pienso_real("Pienso Gallinas", "Gallinas")
st_pol, c_pol = calc_pienso_real("Pienso Pollos", "Pollos")
st_cod, c_cod = calc_pienso_real("Pienso Codornices", "Codornices")

# --- FINANZAS ---
v_cash = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
v_home = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
g_total = gastos['cantidad'].sum() if not gastos.empty else 0
inv_lotes = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
bal_caja = v_cash - g_total - inv_lotes
ben_total = (v_cash + v_home) - g_total - inv_lotes

# ====================== 3. NAVEGACIÓN LATERAL (SIN DESPLEGABLE) ======================
st.sidebar.title("🐓 CORRAL ELITE")
if "seccion" not in st.session_state:
    st.session_state.seccion = "Dashboard"

def cambiar_seccion(nombre):
    st.session_state.seccion = nombre

st.sidebar.subheader("Menú Principal")
if st.sidebar.button("🏠 Dashboard", use_container_width=True): cambiar_seccion("Dashboard")
if st.sidebar.button("🎄 Plan Navidad", use_container_width=True): cambiar_seccion("Navidad")
if st.sidebar.button("🐣 Alta de Lotes", use_container_width=True): cambiar_seccion("Lotes")
if st.sidebar.button("📈 Crecimiento", use_container_width=True): cambiar_seccion("Crecimiento")
if st.sidebar.button("🥚 Producción Diaria", use_container_width=True): cambiar_seccion("Produccion")
if st.sidebar.button("🌟 Primera Puesta", use_container_width=True): cambiar_seccion("Puesta")
if st.sidebar.button("💸 Gastos", use_container_width=True): cambiar_seccion("Gastos")
if st.sidebar.button("💰 Ventas y Consumo", use_container_width=True): cambiar_seccion("Ventas")
if st.sidebar.button("💀 Bajas", use_container_width=True): cambiar_seccion("Bajas")
if st.sidebar.button("📜 Histórico", use_container_width=True): cambiar_seccion("Historico")
st.sidebar.divider()
if st.sidebar.button("💾 SEGURIDAD", use_container_width=True): cambiar_seccion("Seguridad")

# ====================== 4. CONTENIDO DE LAS SECCIONES ======================
sec = st.session_state.seccion

if sec == "Dashboard":
    st.title("🏠 Dashboard de Control")
    st.subheader("📊 Finanzas")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Caja (Efectivo)", f"{bal_caja:.2f}€")
    c2.metric("Ahorro Casa", f"{v_home:.2f}€")
    c3.metric("Beneficio Total", f"{ben_total:.2f}€", delta=f"{v_home:.2f} ahorro")
    c4.metric("Inversión Animales", f"{inv_lotes:.2f}€")
    st.divider()
    st.subheader("📦 Almacén de Pienso")
    p1, p2, p3 = st.columns(3)
    p1.metric("Gallinas", f"{st_gal:.1f} kg", f"-{c_gal:.2f} kg/día")
    p2.metric("Pollos", f"{st_pol:.1f} kg", f"-{c_pol:.2f} kg/día")
    p3.metric("Codornices", f"{st_cod:.1f} kg", f"-{c_cod:.2f} kg/día")

elif sec == "Navidad":
    st.title("🎄 Planificador Navidad")
    objetivo = datetime(datetime.now().year, 12, 15)
    compra = objetivo - timedelta(days=77)
    st.info(f"📅 Compra tus pollitos el: **{compra.strftime('%d de Octubre')}**")

elif sec == "Lotes":
    st.title("🐣 Alta de Lotes")
    with st.form("f_l"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cant", 1); ed = c1.number_input("Edad i.", 0); pr = c2.number_input("Precio Ud", 0.0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            conn.commit(); conn.close(); st.success("Lote guardado"); st.rerun()

elif sec == "Crecimiento":
    st.title("📈 Crecimiento")
    conf = {"Roja": 140, "Blanca": 155, "Chocolate": 170, "Blanco Engorde": 45, "Campero": 90, "Codorniz": 42}
    for _, r in lotes.iterrows():
        f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
        edad = (datetime.now() - f_l).days + r["edad_inicial"]
        meta = conf.get(r["raza"], 150)
        porc = min(100, int((edad/meta)*100))
        ya_pone = "🥚" if not hitos[(hitos['lote_id']==r['id']) & (hitos['tipo']=='Primera Puesta')].empty else ""
        with st.expander(f"Lote {r['id']}: {r['raza']} {ya_pone} ({porc}%)"):
            st.progress(porc/100); st.write(f"Edad: {edad} días.")

elif sec == "Produccion":
    st.title("🥚 Producción Diaria")
    with st.form("f_p"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1); cant = st.number_input("Huevos", 1)
        if st.form_submit_button("Anotar"):
            conn = get_conn(); conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(cant)))
            conn.commit(); conn.close(); st.success("Anotado"); st.rerun()

elif sec == "Puesta":
    st.title("🌟 Primera Puesta")
    with st.form("f_h"):
        l_id = st.selectbox("Lote", lotes[lotes['especie']=='Gallinas']['id'].tolist() if not lotes.empty else [])
        f_h = st.date_input("Fecha primer huevo")
        if st.form_submit_button("Registrar Hito"):
            conn = get_conn(); conn.execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?, 'Primera Puesta', ?)", (int(l_id), f_h.strftime("%d/%m/%Y")))
            conn.commit(); conn.close(); st.success("Hito guardado"); st.rerun()

elif sec == "Gastos":
    st.title("💸 Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Salud", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2); imp = c1.number_input("€", 0.0); kg = c2.number_input("Kg", 0.0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close(); st.success("Gasto guardado"); st.rerun()

elif sec == "Ventas":
    st.title("💰 Ventas y Consumo")
    with st.form("f_v"):
        f = st.date_input("Fecha"); tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        con = st.text_input("Concepto"); imp = st.number_input("Valor €", 0.0); cli = st.text_input("Quién")
        if st.form_submit_button("Registrar"):
            conn = get_conn(); conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cli, tipo, con, imp))
            conn.commit(); conn.close(); st.success("Venta registrada"); st.rerun()

elif sec == "Bajas":
    st.title("💀 Registro de Bajas")
    with st.form("f_b"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1); cant = st.number_input("Cant", 1); mot = st.text_input("Motivo")
        if st.form_submit_button("Registrar Baja"):
            l_sel = lotes[lotes['id']==l_id].iloc[0] if not lotes.empty else None
            perd = cant * (l_sel['precio_ud'] if l_sel is not None else 0)
            conn = get_conn(); conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo, perdida_estimada) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(cant), mot, perd))
            conn.commit(); conn.close(); st.error(f"Pérdida: {perd}€"); st.rerun()

elif sec == "Historico":
    st.title("📜 Histórico")
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    df = cargar(t); st.dataframe(df, use_container_width=True)
    id_b = st.number_input("ID a borrar", 0)
    if st.button("BORRAR ID"): eliminar_reg(t, id_b); st.rerun()

elif sec == "Seguridad":
    st.title("💾 Seguridad")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("Descargar DB", f, "corral.db")
    if st.button("🔥 REINICIAR TODO"):
        if os.path.exists(DB_PATH): os.remove(DB_PATH); st.rerun()
