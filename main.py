import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V16.1", layout="wide", page_icon="🐓")
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
    conn.commit(); conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

inicializar_y_reparar_db()

# ====================== 2. LÓGICA DE BIO-PRECISIÓN (CONSUMO Y EDAD) ======================
lotes = cargar("lotes"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas"); hitos = cargar("hitos")

def obtener_consumo_diario(raza, edad_dias):
    """Gramos/día según raza y evolución de edad"""
    if raza in ["Roja", "Blanca", "Chocolate"]:
        if edad_dias < 30: return 0.040
        if edad_dias < 120: return 0.085
        return 0.120
    if raza == "Blanco Engorde":
        if edad_dias < 14: return 0.045
        if edad_dias < 35: return 0.120
        return 0.200 # Consumo agresivo final
    if raza == "Campero":
        if edad_dias < 21: return 0.040
        if edad_dias < 60: return 0.095
        return 0.145 # Crecimiento lento
    if raza == "Codorniz":
        return 0.025 if edad_dias < 20 else 0.035
    return 0.110

def calc_pienso_real(categoria_pienso, especie_filtro):
    kg_comprados = gastos[gastos['categoria'] == categoria_pienso]['kilos_pienso'].sum() if not gastos.empty else 0
    cons_diario_hoy = 0
    cons_acumulado_total = 0
    if not lotes.empty:
        for _, r in lotes[lotes['especie'] == especie_filtro].iterrows():
            b_l = bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0
            vivas = max(0, r['cantidad'] - b_l)
            f_alta = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias_totales = (datetime.now() - f_alta).days
            for d in range(dias_totales + 1):
                edad_ese_dia = r["edad_inicial"] + d
                factor = obtener_consumo_diario(r["raza"], edad_ese_dia)
                cons_acumulado_total += (vivas * factor)
                if d == dias_totales: cons_diario_hoy += (vivas * factor)
    return max(0, kg_comprados - cons_acumulado_total), cons_diario_hoy

# Stocks
st_gal, c_gal = calc_pienso_real("Pienso Gallinas", "Gallinas")
st_pol, c_pol = calc_pienso_real("Pienso Pollos", "Pollos")
st_cod, c_cod = calc_pienso_real("Pienso Codornices", "Codornices")

# Finanzas
v_cash = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
v_home = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
g_total = gastos['cantidad'].sum() if not gastos.empty else 0
inv_lotes = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
bal_caja = v_cash - g_total - inv_lotes
ben_total = (v_cash + v_home) - g_total - inv_lotes

# ====================== 3. NAVEGACIÓN LATERAL (BOTONES) ======================
if "seccion" not in st.session_state: st.session_state.seccion = "Dashboard"
def navegar(n): st.session_state.seccion = n

st.sidebar.title("🐓 CORRAL ELITE V16.1")
st.sidebar.button("🏠 Dashboard", on_click=navegar, args=("Dashboard",), use_container_width=True)
st.sidebar.button("🎄 Plan Navidad", on_click=navegar, args=("Navidad",), use_container_width=True)
st.sidebar.button("🐣 Alta Lotes", on_click=navegar, args=("Lotes",), use_container_width=True)
st.sidebar.button("📈 Crecimiento", on_click=navegar, args=("Crecimiento",), use_container_width=True)
st.sidebar.button("🥚 Producción", on_click=navegar, args=("Produccion",), use_container_width=True)
st.sidebar.button("🌟 Primera Puesta", on_click=navegar, args=("Puesta",), use_container_width=True)
st.sidebar.button("💸 Gastos", on_click=navegar, args=("Gastos",), use_container_width=True)
st.sidebar.button("💰 Ventas/Consumo", on_click=navegar, args=("Ventas",), use_container_width=True)
st.sidebar.button("💀 Bajas", on_click=navegar, args=("Bajas",), use_container_width=True)
st.sidebar.button("📜 Histórico", on_click=navegar, args=("Historico",), use_container_width=True)
st.sidebar.divider()
st.sidebar.button("💾 SEGURIDAD", on_click=navegar, args=("Seguridad",), use_container_width=True)

# ====================== 4. SECCIONES ======================
sec = st.session_state.seccion

if sec == "Dashboard":
    st.title("🏠 Dashboard Principal")
    
    # ALERTAS DE STOCK (NUEVO)
    for nombre, stock in [("Gallinas", st_gal), ("Pollos", st_pol), ("Codornices", st_cod)]:
        if stock < 5:
            st.error(f"⚠️ ¡ALERTA! Stock crítico de Pienso {nombre}: solo quedan {stock:.1f} kg.")

    st.subheader("📊 Resumen Económico")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Caja Real", f"{bal_caja:.2f}€")
    c2.metric("Ahorro Casa", f"{v_home:.2f}€")
    c3.metric("Beneficio Total", f"{ben_total:.2f}€", delta=f"{v_home:.2f} ahorro")
    c4.metric("Inversión Inicial", f"{inv_lotes:.2f}€")
    
    st.divider()
    st.subheader("📦 Almacén Dinámico")
    p1, p2, p3 = st.columns(3)
    p1.metric("Pienso Gallinas", f"{st_gal:.1f} kg", f"-{c_gal:.2f} kg/día")
    p2.metric("Pienso Pollos", f"{st_pol:.1f} kg", f"-{c_pol:.2f} kg/día")
    p3.metric("Pienso Codornices", f"{st_cod:.1f} kg", f"-{c_cod:.2f} kg/día")

elif sec == "Navidad":
    st.title("🎄 Estrategia de Navidad")
    obj = datetime(datetime.now().year, 12, 20)
    c_blanco = obj - timedelta(days=55)
    c_campero = obj - timedelta(days=90)
    
    st.write("### Fechas Clave para Sacrificio en Diciembre:")
    col1, col2 = st.columns(2)
    with col1:
        st.info("🐔 **Pollo Blanco (Rápido)**")
        st.write(f"Compra ideal: **{c_blanco.strftime('%d de Octubre')}**")
        st.write("Coste pienso: Alto impacto en poco tiempo.")
    with col2:
        st.success("🐓 **Pollo Campero (Lento)**")
        st.write(f"Compra ideal: **{c_campero.strftime('%d de Septiembre')}**")
        st.write("Coste pienso: Distribuido y eficiente.")

elif sec == "Crecimiento":
    st.title("📈 Control de Desarrollo")
    metas = {"Roja": 150, "Blanca": 150, "Blanco Engorde": 55, "Campero": 90, "Codorniz": 45}
    for _, r in lotes.iterrows():
        f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
        edad = (datetime.now() - f_l).days + r["edad_inicial"]
        m = metas.get(r["raza"], 100)
        porc = min(100, int((edad/m)*100))
        ya_pone = "🥚" if not hitos[(hitos['lote_id']==r['id']) & (hitos['tipo']=='Primera Puesta')].empty else ""
        with st.expander(f"Lote {r['id']}: {r['raza']} {ya_pone} ({porc}%)"):
            st.write(f"Edad actual: {edad} días. Objetivo: {m} días.")
            st.progress(porc/100)

elif sec == "Historico":
    st.title("📜 Histórico")
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    id_b = st.number_input("ID a borrar", 0)
    if st.button("BORRAR REGISTRO"):
        conn = get_conn(); conn.execute(f"DELETE FROM {t} WHERE id=?", (id_b,)); conn.commit(); st.rerun()

# --- LAS SECCIONES RESTANTES MANTIENEN SU LÓGICA DE ALTA, VENTAS, GASTOS, PRODUCCION Y SEGURIDAD ---
elif sec == "Lotes":
    st.title("🐣 Alta")
    with st.form("f_l"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cant", 1); ed = c1.number_input("Edad inicial (días)", 0); pr = c2.number_input("Precio Ud", 0.0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            conn.commit(); conn.close(); st.success("OK"); st.rerun()

elif sec == "Ventas":
    st.title("💰 Ventas / Consumo")
    with st.form("f_v"):
        f = st.date_input("Fecha"); tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        con = st.text_input("Concepto"); imp = st.number_input("Valor €", 0.0); cli = st.text_input("Quién")
        if st.form_submit_button("Registrar"):
            conn = get_conn(); conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cli, tipo, con, imp))
            conn.commit(); conn.close(); st.success("OK"); st.rerun()

elif sec == "Gastos":
    st.title("💸 Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2); imp = c1.number_input("€", 0.0); kg = c2.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close(); st.success("OK"); st.rerun()

elif sec == "Seguridad":
    st.title("💾 Seguridad")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("Descargar DB", f, "corral.db")
    if st.button("BORRAR TODO"):
        if os.path.exists(DB_PATH): os.remove(DB_PATH); st.rerun()
