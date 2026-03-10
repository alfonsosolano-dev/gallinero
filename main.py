import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import plotly.express as px

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
        cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS primera_puesta(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER UNIQUE, fecha_puesta TEXT)")
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

inicializar_db()

# ====================== 2. LÓGICA DE INTELIGENCIA (CÁLCULOS) ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); salud = cargar("salud"); bajas = cargar("bajas")

# Cálculo de Aves Vivas
t_altas = lotes["cantidad"].sum() if not lotes.empty else 0
t_bajas = bajas["cantidad"].sum() if not bajas.empty else 0
vivas = t_altas - t_bajas

# Cálculo de Stock de Pienso Estimado
t_kilos_comprados = gastos["kilos_pienso"].sum() if not gastos.empty else 0
# Estimación consumo: Gallina (120g/día), Pollo (150g/día), Codorniz (30g/día)
consumo_diario_est = 0
if not lotes.empty:
    for _, r in lotes.iterrows():
        b_lote = bajas[bajas['lote']==r['id']]['cantidad'].sum() if not bajas.empty else 0
        actuales = r['cantidad'] - b_lote
        if r['especie'] == "Gallinas": consumo_diario_est += actuales * 0.120
        elif r['especie'] == "Pollos": consumo_diario_est += actuales * 0.150
        else: consumo_diario_est += actuales * 0.030

dias_pienso = (t_kilos_comprados / consumo_diario_est) if consumo_diario_est > 0 else 0

# ====================== 3. MENÚ LATERAL ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard Elite", "🐣 Gestión de Lotes", "🥚 Producción", 
    "💸 Gastos e Inventario", "💰 Ventas y Clientes", "💉 Salud y Alertas", "💾 SEGURIDAD"
])

# --- DASHBOARD ELITE ---
if menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control Inteligente")
    
    # Métricas Principales
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aves Activas", int(vivas))
    c2.metric("Stock Pienso (Días)", f"{dias_pienso:.1f} d", delta="- Consumo diario" if dias_pienso < 5 else None, delta_color="inverse")
    
    t_v = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    t_g = gastos['cantidad'].sum() if not gastos.empty else 0
    c3.metric("Balance Económico", f"{(t_v - t_g):.2f}€")
    
    t_h = prod['huevos'].sum() if not prod.empty else 0
    coste_h = (t_g / t_h) if t_h > 0 else 0
    c4.metric("Coste Real x Huevo", f"{coste_h:.3f}€")

    # Alertas Sanitarias Próximas
    st.subheader("🗓️ Próximas Tareas Sanitarias")
    if not salud.empty:
        hoy = datetime.now().date()
        salud['fecha_dt'] = pd.to_datetime(salud['proxima_fecha'], format='%d/%m/%Y').dt.date
        pendientes = salud[salud['fecha_dt'] >= hoy].sort_values('fecha_dt')
        if not pendientes.empty:
            for _, s in pendientes.head(3).iterrows():
                st.warning(f"🔔 {s['fecha_dt']}: {s['descripcion']} (Lote {s['lote']})")
        else: st.info("No hay tareas pendientes.")

    # Top Clientes
    if not ventas.empty:
        st.subheader("🏆 Mejores Clientes")
        top_c = ventas[ventas['tipo_venta']=='Venta Cliente'].groupby('cliente')['cantidad'].sum().sort_values(ascending=False).head(3)
        st.table(top_c)

# --- GESTIÓN DE LOTES (INCLUYE CRECIMIENTO) ---
elif menu == "🐣 Gestión de Lotes":
    st.title("🐣 Control de Lotes y Crecimiento")
    tab1, tab2 = st.tabs(["Nuevo Lote", "Estado y Madurez"])
    
    with tab1:
        f_ll = st.date_input("Fecha llegada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        razas = {"Gallinas": ["Roja", "Blanca", "Chocolate"], "Pollos": ["Blanco Engorde", "Campero"], "Codornices": ["Codorniz"]}
        rz = st.selectbox("Raza", razas[esp])
        with st.form("f_l"):
            c1, c2 = st.columns(2)
            cant = c1.number_input("Cantidad", 1); edad = c1.number_input("Edad inicial días", 0)
            prec = c2.number_input("Precio ud €", 0.0)
            if st.form_submit_button("Registrar"):
                conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f_ll.strftime("%d/%m/%Y"), esp, rz, int(cant), int(edad), prec))
                conn.commit(); conn.close(); st.success("OK"); st.rerun()

    with tab2:
        config_r = {"Roja": 140, "Blanca": 155, "Chocolate": 170, "Blanco Engorde": 45, "Campero": 90, "Codorniz": 42}
        if not lotes.empty:
            for _, r in lotes.iterrows():
                edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
                meta = config_r.get(r["raza"], 150)
                st.write(f"**Lote {r['id']} ({r['raza']})**: {edad} días")
                st.progress(min(100, int((edad/meta)*100))/100)

# --- GASTOS E INVENTARIO (CONTROL DE SACOS) ---
elif menu == "💸 Gastos e Inventario":
    st.title("💸 Registro de Gastos y Pienso")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Salud", "Otros"])
        con = st.text_input("Concepto (Ej: Saco 25kg)")
        col1, col2 = st.columns(2)
        imp = col1.number_input("Importe Total €", 0.0)
        kg = col2.number_input("Kilos (si es pienso)", 0.0)
        if st.form_submit_button("Guardar Gasto"):
            conn = get_conn(); conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close(); st.success("Anotado"); st.rerun()

# --- VENTAS Y CLIENTES ---
elif menu == "💰 Ventas y Clientes":
    st.title("💰 Registro de Ventas")
    tipo = st.radio("Destino:", ["Venta Cliente", "Consumo Propio"])
    with st.form("f_v"):
        f = st.date_input("Fecha")
        cli = st.text_input("Cliente / Quién", "Consumo Propio" if tipo=="Consumo Propio" else "")
        con = st.text_input("Producto (Ej: 3 docenas)")
        imp = st.number_input("Importe €", 0.0)
        if st.form_submit_button("Registrar Venta"):
            conn = get_conn(); conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cli, tipo, con, imp))
            conn.commit(); conn.close(); st.success("Venta guardada"); st.rerun()

# --- SEGURIDAD ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Copia de Seguridad")
    st.warning("Descarga siempre el archivo antes de cerrar para no perder tus datos.")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR BASE DE DATOS (.db)", f, "mi_corral.db")
    up = st.file_uploader("📤 RESTAURAR COPIA", type="db")
    if up:
        with open(DB_PATH, "wb") as f: f.write(up.getbuffer())
        st.success("Datos restaurados correctamente."); st.rerun()

# --- OTROS REGISTROS (PRODUCCION, SALUD, BAJAS) ---
else:
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1)
        if "Producción" in menu: valor = st.number_input("Huevos recogidos", 1)
        elif "Salud" in menu: 
            desc = st.text_area("Tratamiento"); prox = st.date_input("Próxima cita")
        else: # Bajas
            valor = st.number_input("Cantidad bajas", 1); mot = st.text_input("Motivo")
            
        if st.form_submit_button("Guardar"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(valor)))
            elif "Salud" in menu: conn.execute("INSERT INTO salud (fecha, lote, descripcion, proxima_fecha, estado) VALUES (?,?,?,?,'Pendiente')", (f_s, int(l_id), desc, prox.strftime("%d/%m/%Y")))
            elif "Bajas" in menu: conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo) VALUES (?,?,?,?)", (f_s, int(l_id), int(valor), mot))
            conn.commit(); conn.close(); st.success("Registrado"); st.rerun()
