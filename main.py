import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

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
    
    try: c.execute("ALTER TABLE gastos ADD COLUMN kilos_pienso REAL DEFAULT 0")
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

inicializar_db()

# ====================== 2. DATOS PARA CÁLCULOS ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); salud = cargar("salud"); bajas = cargar("bajas")

# --- LÓGICA DE STOCK DE PIENSO ---
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
    "🏠 Dashboard Elite", "🐣 Alta de Lotes", "🌟 Primera Puesta", "🥚 Producción", 
    "💸 Gastos e Inventario", "💰 Ventas y Clientes", "📈 Crecimiento y Vejez", 
    "💉 Salud y Alertas", "📜 Histórico y Borrar", "💾 SEGURIDAD"
])

# --- DASHBOARD ---
if menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control Inteligente")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock Pienso", f"{dias_pienso:.1f} días")
    
    t_v = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    t_g = gastos['cantidad'].sum() if not gastos.empty else 0
    c2.metric("Balance Ventas", f"{(t_v - t_g):.2f}€")
    
    t_ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    c3.metric("Ahorro Casa", f"{t_ahorro:.2f}€")
    
    t_h = prod['huevos'].sum() if not prod.empty else 0
    coste_h = (t_g / t_h) if t_h > 0 else 0
    c4.metric("Coste x Huevo", f"{coste_h:.3f}€")

# --- ALTA DE LOTES ---
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Registro de Lotes")
    with st.form("f_l"):
        f_ll = st.date_input("Fecha llegada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        razas_d = {"Gallinas": ["Roja", "Blanca", "Chocolate"], "Pollos": ["Blanco Engorde", "Campero"], "Codornices": ["Codorniz"]}
        rz = st.selectbox("Raza", razas_d[esp])
        cant = st.number_input("Cantidad", 1); edad = st.number_input("Edad inicial (días)", 0)
        prec = st.number_input("Precio ud €", 0.0)
        if st.form_submit_button("✅ GUARDAR LOTE"):
            conn = get_conn()
            conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f_ll.strftime("%d/%m/%Y"), esp, rz, int(cant), int(edad), prec))
            conn.commit(); conn.close(); st.success("CONFIRMADO: Lote guardado."); st.rerun()

# --- CRECIMIENTO Y VEJEZ (LOGICA POR RAZA) ---
elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Ciclo de Vida por Raza")
    config_r = {
        "Roja": {"meta": 140, "vejez": 700}, "Blanca": {"meta": 155, "vejez": 750},
        "Chocolate": {"meta": 170, "vejez": 800}, "Blanco Engorde": {"meta": 45, "vejez": 60},
        "Campero": {"meta": 90, "vejez": 120}, "Codorniz": {"meta": 42, "vejez": 365}
    }
    for _, r in lotes.iterrows():
        edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
        conf = config_r.get(r["raza"], {"meta": 150, "vejez": 730})
        with st.expander(f"Lote {r['id']}: {r['raza']}"):
            st.write(f"🎂 Edad: {edad} días")
            if edad > conf["vejez"]: st.error(f"⚠️ Alerta Vejez/Sacrificio ({conf['vejez']} días)")
            st.progress(min(100, int((edad/conf["meta"])*100))/100)

# --- GASTOS E INVENTARIO ---
elif menu == "💸 Gastos e Inventario":
    st.title("💸 Gastos y Pienso")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Dirigido a:", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Salud", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kilos (si es pienso)", 0.0)
        if st.form_submit_button("💾 GUARDAR GASTO"):
            conn = get_conn()
            conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close(); st.success("CONFIRMADO: Gasto registrado."); st.rerun()

# --- VENTAS Y CLIENTES ---
elif menu == "💰 Ventas y Clientes":
    st.title("💰 Ventas y Consumo Propio")
    tipo = st.radio("Tipo:", ["Venta Cliente", "Consumo Propio"])
    with st.form("f_v"):
        f = st.date_input("Fecha"); cli = st.text_input("Cliente/Quién", "Familia" if tipo=="Consumo Propio" else "")
        prod_v = st.text_input("Producto"); imp = st.number_input("Precio/Valor €", 0.0)
        if st.form_submit_button("🤝 REGISTRAR"):
            conn = get_conn()
            conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cli, tipo, prod_v, imp))
            conn.commit(); conn.close(); st.success("CONFIRMADO: Venta guardada."); st.rerun()

# --- HISTÓRICO Y BORRADO ---
elif menu == "📜 Histórico y Borrar":
    st.title("📜 Histórico de Datos")
    t_sel = st.selectbox("Tabla:", ["produccion", "gastos", "ventas", "salud", "bajas", "lotes"])
    df_h = cargar(t_sel)
    st.dataframe(df_h, use_container_width=True)
    id_b = st.number_input("ID a borrar", min_value=1, step=1)
    if st.button("❌ BORRAR REGISTRO"):
        if id_b in df_h['id'].values:
            eliminar_reg(t_sel, id_b); st.error("Eliminado."); st.rerun()

# --- SEGURIDAD ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Backup")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR .db", f, "corral.db")
    up = st.file_uploader("📤 RESTAURAR", type="db")
    if up:
        with open(DB_PATH, "wb") as f: f.write(up.getbuffer())
        st.success("Restaurado."); st.rerun()

# --- OTROS (PRODUCCIÓN, SALUD, BAJAS, PRIMERA PUESTA) ---
else:
    st.title(f"Registro: {menu}")
    with st.form("f_o"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1)
        if "Puesta" in menu: f_p = st.date_input("Fecha primer huevo")
        elif "Producción" in menu or "Puesta Diaria" in menu: val = st.number_input("Huevos", 1)
        elif "Salud" in menu: d = st.text_area("Tratamiento"); p = st.date_input("Próxima")
        else: val = st.number_input("Cantidad", 1); mot = st.text_input("Motivo")
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Puesta" in menu: conn.execute("INSERT OR REPLACE INTO primera_puesta (lote_id, fecha_puesta) VALUES (?,?)", (int(l_id), f_p.strftime("%d/%m/%Y")))
            elif "Producción" in menu or "Puesta Diaria" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
            elif "Salud" in menu: conn.execute("INSERT INTO salud (fecha, lote, descripcion, proxima_fecha, estado) VALUES (?,?,?,?,'Pendiente')", (f_s, int(l_id), d, p.strftime("%d/%m/%Y")))
            else: conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo) VALUES (?,?,?,?)", (f_s, int(l_id), int(val), mot))
            conn.commit(); conn.close(); st.success("CONFIRMADO."); st.rerun()
