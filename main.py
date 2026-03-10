import streamlit as st
import sqlite3
import pd
import os
from datetime import datetime

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V6", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_y_reparar_db():
    conn = get_conn()
    c = conn.cursor()
    # Creación de tablas si no existen
    c.execute("""CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
        cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS primera_puesta(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER UNIQUE, fecha_puesta TEXT)")
    
    # --- REPARACIÓN DE EMERGENCIA ---
    # Esto soluciona el OperationalError añadiendo la columna si no existe
    try:
        c.execute("ALTER TABLE gastos ADD COLUMN kilos_pienso REAL DEFAULT 0")
        conn.commit()
    except:
        pass # La columna ya existía
    
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

# ====================== 2. LÓGICA DE CÁLCULOS ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas")

# Stock de Pienso
t_kg = gastos["kilos_pienso"].sum() if not gastos.empty else 0
consumo_diario_est = 0
if not lotes.empty:
    for _, r in lotes.iterrows():
        b_l = bajas[bajas['lote']==r['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas = r['cantidad'] - b_l
        factor = 0.120 if r['especie'] == "Gallinas" else 0.150 if r['especie'] == "Pollos" else 0.030
        consumo_diario_est += vivas * factor
dias_pienso = (t_kg / consumo_diario_est) if consumo_diario_est > 0 else 0

# ====================== 3. MENÚ LATERAL ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard Elite", "🐣 Alta de Lotes", "📈 Crecimiento y Vejez", 
    "🥚 Producción Diaria", "💸 Gastos e Inventario", "💰 Ventas y Clientes", 
    "💉 Salud y Alertas", "📜 Histórico y Borrar", "💾 SEGURIDAD"
])

# --- DASHBOARD ---
if menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control")
    c1, c2, c3, c4 = st.columns(4)
    t_v = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    t_g = gastos['cantidad'].sum() if not gastos.empty else 0
    t_ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    t_h = prod['huevos'].sum() if not prod.empty else 0
    
    c1.metric("Stock Pienso", f"{dias_pienso:.1f} d")
    c2.metric("Balance Real", f"{(t_v - t_g):.2f}€")
    c3.metric("Ahorro Casa", f"{t_ahorro:.2f}€")
    c4.metric("Huevos Totales", int(t_h))

# --- CRECIMIENTO (SIEMPRE VISIBLE) ---
elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Desarrollo por Raza")
    if lotes.empty: st.info("Registra un lote para ver su progreso.")
    else:
        config_r = {"Roja": 140, "Blanca": 155, "Chocolate": 170, "Blanco Engorde": 45, "Campero": 90, "Codorniz": 42}
        for _, r in lotes.iterrows():
            f_llegada = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_llegada).days + r["edad_inicial"]
            meta = config_r.get(r["raza"], 150)
            with st.expander(f"Lote {r['id']}: {r['raza']}"):
                st.write(f"🎂 Edad: {edad} días")
                prog = min(100, int((edad/meta)*100))
                st.progress(prog/100)
                st.write(f"Progreso a madurez: {prog}%")

# --- GASTOS (CON REPARACIÓN CONFIRMADA) ---
elif menu == "💸 Gastos e Inventario":
    st.title("💸 Registro de Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Infraestructura", "Otros"])
        con = st.text_input("Concepto")
        c1, c2 = st.columns(2)
        imp = c1.number_input("Importe €", 0.0)
        kg = c2.number_input("Kilos (si es pienso)", 0.0)
        if st.form_submit_button("💾 GUARDAR GASTO"):
            conn = get_conn()
            conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)",
                         (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close()
            st.success(f"✔️ CONFIRMADO: {con} guardado correctamente."); st.rerun()

# --- HISTÓRICO Y BORRADO ---
elif menu == "📜 Histórico y Borrar":
    st.title("📜 Histórico")
    t_sel = st.selectbox("Tabla:", ["produccion", "gastos", "ventas", "salud", "bajas", "lotes"])
    df_h = cargar(t_sel)
    st.dataframe(df_h, use_container_width=True)
    id_b = st.number_input("ID a borrar", min_value=1, step=1)
    if st.button("❌ ELIMINAR REGISTRO"):
        if id_b in df_h['id'].values:
            eliminar_reg(t_sel, id_b); st.error("Registro borrado."); st.rerun()

# --- SEGURIDAD ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Backup")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR .db", f, "corral.db")
    up = st.file_uploader("📤 RESTAURAR", type="db")
    if up:
        with open(DB_PATH, "wb") as f: f.write(up.getbuffer())
        st.success("Copia restaurada."); st.rerun()

# --- RESTO DE REGISTROS ---
else:
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1)
        if "Producción" in menu: val = st.number_input("Huevos", 1)
        elif "Alta" in menu:
            esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
            rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
            cant = st.number_input("Cantidad", 1); edad_i = st.number_input("Edad inicial días", 0)
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
            elif "Alta" in menu: conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, estado) VALUES (?,?,?,?,?,'Activo')", (f_s, esp, rz, int(cant), int(edad_i)))
            conn.commit(); conn.close(); st.success("✔️ CONFIRMADO."); st.rerun()
