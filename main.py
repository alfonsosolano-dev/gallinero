import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO V17", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, perdida_estimada REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS hitos(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT)")
    conn.commit(); conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

inicializar_db()

# ====================== 2. LÓGICA DE BIO-PRECISIÓN (CONSUMO DINÁMICO) ======================
lotes = cargar("lotes"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas"); hitos = cargar("hitos")

def obtener_consumo_diario(raza, edad_dias):
    """Gramos de pienso según raza y edad"""
    if raza in ["Roja", "Blanca", "Chocolate"]:
        if edad_dias < 30: return 0.040
        if edad_dias < 120: return 0.085
        return 0.125
    if raza == "Blanco Engorde":
        if edad_dias < 14: return 0.045
        if edad_dias < 35: return 0.130
        return 0.210
    if raza == "Campero":
        if edad_dias < 21: return 0.040
        if edad_dias < 60: return 0.095
        return 0.150
    if raza == "Codorniz":
        return 0.025 if edad_dias < 20 else 0.035
    return 0.110

def calc_pienso_real(categoria_pienso, especie_filtro):
    kg_comprados = gastos[gastos['categoria'] == categoria_pienso]['kilos_pienso'].sum() if not gastos.empty else 0
    cons_diario_hoy = 0
    cons_acumulado_total = 0
    if not lotes.empty:
        lotes_filtrados = lotes[lotes['especie'] == especie_filtro]
        for _, r in lotes_filtrados.iterrows():
            b_l = bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0
            vivas = max(0, r['cantidad'] - b_l)
            f_alta = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias_pasados = (datetime.now() - f_alta).days
            
            # Consumo acumulado desde el primer día hasta ayer
            for d in range(dias_pasados):
                edad_d = r["edad_inicial"] + d
                cons_acumulado_total += (vivas * obtener_consumo_diario(r["raza"], edad_d))
            
            # Consumo de HOY
            cons_hoy = vivas * obtener_consumo_diario(r["raza"], r["edad_inicial"] + dias_pasados)
            cons_diario_hoy += cons_hoy
            cons_acumulado_total += cons_hoy
            
    return max(0, kg_comprados - cons_acumulado_total), cons_diario_hoy

# Ejecución de cálculos
st_gal, c_gal = calc_pienso_real("Pienso Gallinas", "Gallinas")
st_pol, c_pol = calc_pienso_real("Pienso Pollos", "Pollos")
st_cod, c_cod = calc_pienso_real("Pienso Codornices", "Codornices")

# Finanzas
v_cash = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
v_home = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
g_total = gastos['cantidad'].sum() if not gastos.empty else 0
inv_ini = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
balance = v_cash - g_total - inv_ini

# ====================== 3. NAVEGACIÓN LATERAL ======================
st.sidebar.title("🐓 CORRAL MAESTRO V17")
# Usamos un radio button pero con estilo de lista para evitar errores de refresco
seccion = st.sidebar.radio("IR A:", [
    "🏠 Dashboard", "🎄 Plan Navidad", "🐣 Alta Lotes", "📈 Crecimiento", 
    "🥚 Producción", "🌟 Primera Puesta", "💸 Gastos", "💰 Ventas/Consumo", 
    "💀 Bajas", "📜 Histórico", "💾 SEGURIDAD"
])

# ====================== 4. SECCIONES ======================
if seccion == "🏠 Dashboard":
    st.title("🏠 Dashboard")
    # Alertas
    if st_gal < 5: st.error(f"⚠️ Pienso Gallinas bajo: {st_gal:.1f}kg")
    if st_pol < 5: st.error(f"⚠️ Pienso Pollos bajo: {st_pol:.1f}kg")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Caja Real", f"{balance:.2f}€")
    c2.metric("Ahorro Consumo", f"{v_home:.2f}€")
    c3.metric("Inversión en Aves", f"{inv_ini:.2f}€")
    
    st.divider()
    p1, p2, p3 = st.columns(3)
    p1.metric("Stock Gallinas", f"{st_gal:.1f} kg", f"-{c_gal:.2f}/día")
    p2.metric("Stock Pollos", f"{st_pol:.1f} kg", f"-{c_pol:.2f}/día")
    p3.metric("Stock Codornices", f"{st_cod:.1f} kg", f"-{c_cod:.2f}/día")

elif seccion == "🎄 Plan Navidad":
    st.title("🎄 Planificación Navidad")
    obj = datetime(datetime.now().year, 12, 18)
    st.info(f"Para Blanco Engorde comprar el: {(obj - timedelta(days=55)).strftime('%d/%m')}")
    st.success(f"Para Campero comprar el: {(obj - timedelta(days=90)).strftime('%d/%m')}")

elif seccion == "🐣 Alta Lotes":
    st.title("🐣 Nuevo Lote")
    with st.form("f1"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cantidad", 1); ed = c1.number_input("Edad (días)", 0); pr = c2.number_input("Precio/Ud", 0.0)
        if st.form_submit_button("Registrar"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            conn.commit(); st.rerun()

elif seccion == "🥚 Producción":
    st.title("🥚 Registro de Huevos")
    with st.form("f2"):
        f = st.date_input("Fecha")
        ids = lotes[lotes['especie']=='Gallinas']['id'].tolist() if not lotes.empty else []
        l_id = st.selectbox("Lote ID", ids)
        cant = st.number_input("Nº Huevos", 1)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(cant)))
            conn.commit(); st.rerun()

elif seccion == "🌟 Primera Puesta":
    st.title("🌟 Primera Puesta")
    with st.form("f3"):
        ids = lotes[lotes['especie']=='Gallinas']['id'].tolist() if not lotes.empty else []
        l_id = st.selectbox("Lote ID", ids)
        f_h = st.date_input("Fecha primer huevo")
        if st.form_submit_button("Guardar Hito"):
            conn = get_conn(); conn.execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?, 'Primera Puesta', ?)", (int(l_id), f_h.strftime("%d/%m/%Y")))
            conn.commit(); st.rerun()

elif seccion == "💀 Bajas":
    st.title("💀 Registro de Bajas")
    with st.form("f4"):
        f = st.date_input("Fecha")
        l_id = st.selectbox("Lote afectado", lotes['id'].tolist() if not lotes.empty else [])
        cant = st.number_input("Cantidad", 1); mot = st.text_input("Motivo")
        if st.form_submit_button("Registrar Baja"):
            l_sel = lotes[lotes['id']==l_id].iloc[0]
            perd = cant * l_sel['precio_ud']
            conn = get_conn(); conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo, perdida_estimada) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(cant), mot, perd))
            conn.commit(); st.rerun()

elif seccion == "💸 Gastos":
    st.title("💸 Registro de Gastos")
    with st.form("f5"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2); imp = c1.number_input("Importe €", 0.0); kg = c2.number_input("Kilos Pienso", 0.0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); st.rerun()

elif seccion == "💰 Ventas/Consumo":
    st.title("💰 Ventas y Consumo Propio")
    with st.form("f6"):
        f = st.date_input("Fecha"); t = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        con = st.text_input("Producto"); imp = st.number_input("Valor €", 0.0); cli = st.text_input("Cliente/Quién")
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cli, t, con, imp))
            conn.commit(); st.rerun()

elif seccion == "📜 Histórico":
    st.title("📜 Histórico")
    tabla = st.selectbox("Seleccionar Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
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
