import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import plotly.express as px

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Tablas base
    c.execute("""CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
        cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS primera_puesta(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER UNIQUE, fecha_puesta TEXT)")
    
    # ARREGLO AUTOMÁTICO DE COLUMNAS (Para evitar el OperationalError)
    try:
        c.execute("ALTER TABLE gastos ADD COLUMN kilos_pienso REAL DEFAULT 0")
    except:
        pass # La columna ya existe
    
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

inicializar_db()

# ====================== 2. CÁLCULOS INTELIGENTES ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); salud = cargar("salud"); bajas = cargar("bajas")

# Stock de pienso estimado
t_kg = gastos["kilos_pienso"].sum() if not gastos.empty else 0
consumo_diario = 0
if not lotes.empty:
    for _, r in lotes.iterrows():
        b_l = bajas[bajas['lote']==r['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas_lote = r['cantidad'] - b_l
        factor = 0.120 if r['especie'] == "Gallinas" else 0.150 if r['especie'] == "Pollos" else 0.030
        consumo_diario += vivas_lote * factor
dias_pienso = (t_kg / consumo_diario) if consumo_diario > 0 else 0

# ====================== 3. MENÚ LATERAL ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard", "🐣 Alta de Lotes", "🥚 Producción", 
    "💸 Gastos e Inventario", "💰 Ventas y Clientes", "💉 Salud y Alertas", "💾 SEGURIDAD"
])

# --- DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock Pienso", f"{dias_pienso:.1f} días")
    
    t_v = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    t_g = gastos['cantidad'].sum() if not gastos.empty else 0
    c2.metric("Balance", f"{(t_v - t_g):.2f}€")
    
    t_h = prod['huevos'].sum() if not prod.empty else 0
    c3.metric("Huevos Totales", int(t_h))
    
    t_a = lotes['cantidad'].sum() if not lotes.empty else 0
    t_b = bajas['cantidad'].sum() if not bajas.empty else 0
    c4.metric("Aves Vivas", int(t_a - t_b))

# --- ALTA DE LOTES ---
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Registro de Lotes")
    f_l = st.date_input("Fecha llegada")
    esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
    razas = {"Gallinas": ["Roja", "Blanca", "Chocolate"], "Pollos": ["Blanco Engorde", "Campero"], "Codornices": ["Codorniz"]}
    rz = st.selectbox("Raza", razas[esp])
    
    with st.form("f_lote"):
        col1, col2 = st.columns(2)
        cant = col1.number_input("Cantidad", 1)
        edad = col1.number_input("Edad inicial (días)", 0)
        prec = col2.number_input("Precio unidad €", 0.0)
        
        if st.form_submit_button("✅ GUARDAR LOTE"):
            conn = get_conn()
            conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')",
                         (f_l.strftime("%d/%m/%Y"), esp, rz, int(cant), int(edad), prec))
            conn.commit(); conn.close()
            st.success(f"✔️ CONFIRMADO: Lote de {cant} {rz} guardado con éxito.")
            st.balloons()

# --- GASTOS E INVENTARIO ---
elif menu == "💸 Gastos e Inventario":
    st.title("💸 Registro de Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Dirigido a:", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Salud", "Otros"])
        con = st.text_input("Detalle del gasto")
        c1, c2 = st.columns(2)
        imp = c1.number_input("Importe Total €", 0.0)
        kg = c2.number_input("Kilos (si es pienso)", 0.0)
        
        if st.form_submit_button("💾 ANOTAR GASTO"):
            conn = get_conn()
            conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)",
                         (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close()
            st.success(f"✔️ CONFIRMADO: Gasto de {imp}€ en '{con}' registrado.")

# --- VENTAS Y CLIENTES ---
elif menu == "💰 Ventas y Clientes":
    st.title("💰 Salida de Productos")
    tipo = st.radio("Tipo:", ["Venta Cliente", "Consumo Propio"])
    with st.form("f_v"):
        f = st.date_input("Fecha")
        cli = st.text_input("Nombre Cliente", "Familia" if tipo=="Consumo Propio" else "")
        prod_v = st.text_input("Producto (ej: 2 docenas)")
        imp = st.number_input("Importe €", 0.0)
        
        if st.form_submit_button("🤝 REGISTRAR VENTA"):
            conn = get_conn()
            conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)",
                         (f.strftime("%d/%m/%Y"), cli, tipo, prod_v, imp))
            conn.commit(); conn.close()
            st.success(f"✔️ CONFIRMADO: Registro de {imp}€ para {cli} guardado.")

# --- SEGURIDAD ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Copia de Seguridad")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 DESCARGAR COPIA (.db)", f, "corral_maestro.db")
    
    up = st.file_uploader("📤 RESTAURAR COPIA ANTERIOR", type="db")
    if up:
        with open(DB_PATH, "wb") as f: f.write(up.getbuffer())
        st.success("✅ Datos restaurados. La aplicación se actualizará."); st.rerun()

# --- PRODUCCION, SALUD, BAJAS ---
else:
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha")
        l_id = st.number_input("ID Lote", 1)
        if "Producción" in menu:
            val = st.number_input("Huevos", 1)
        elif "Salud" in menu:
            desc = st.text_area("Tratamiento"); prox = st.date_input("Próxima dosis")
        else:
            val = st.number_input("Cantidad bajas", 1); mot = st.text_input("Motivo")
            
        if st.form_submit_button("✅ GUARDAR DATOS"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu:
                conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
                msg = f"{val} huevos registrados al lote {l_id}"
            elif "Salud" in menu:
                conn.execute("INSERT INTO salud (fecha, lote, descripcion, proxima_fecha, estado) VALUES (?,?,?,?,'Pendiente')", (f_s, int(l_id), desc, prox.strftime("%d/%m/%Y")))
                msg = f"Tratamiento registrado. Próxima cita: {prox}"
            else:
                conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo) VALUES (?,?,?,?)", (f_s, int(l_id), int(val), mot))
                msg = f"{val} bajas anotadas al lote {l_id}"
            conn.commit(); conn.close()
            st.success(f"✔️ CONFIRMADO: {msg}.")
