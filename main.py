import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V12", layout="wide", page_icon="🐓")
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
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, perdida_estimada REAL)")
    
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

# ====================== 2. CARGA Y CÁLCULOS DETALLADOS ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas")

# --- LÓGICA DE PIENSO POR ESPECIE ---
# Separamos los kilos comprados por categoría
def obtener_kg_por_cat(categoria):
    if gastos.empty: return 0
    return gastos[gastos['categoria'] == categoria]['kilos_pienso'].sum()

kg_gallinas = obtener_kg_por_cat("Pienso Gallinas")
kg_pollos = obtener_kg_por_cat("Pienso Pollos")
kg_codornices = obtener_kg_por_cat("Pienso Codornices")

# Cálculo de consumo diario por especie
cons_gallinas = 0; cons_pollos = 0; cons_codornices = 0

if not lotes.empty:
    for _, r in lotes.iterrows():
        f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
        edad = (datetime.now() - f_l).days + (r["edad_inicial"] if r["edad_inicial"] else 0)
        b_l = bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas = max(0, r['cantidad'] - b_l)
        
        if r['especie'] == "Gallinas":
            cons_gallinas += vivas * 0.120
        elif r['especie'] == "Codornices":
            cons_codornices += vivas * 0.030
        elif r['especie'] == "Pollos":
            f_p = 0.050 if edad < 14 else 0.120 if edad < 30 else 0.180
            cons_pollos += vivas * f_p

# Días restantes por especie
stock_gal = (kg_gallinas / cons_gallinas) if cons_gallinas > 0 else 0
stock_pol = (kg_pollos / cons_pollos) if cons_pollos > 0 else 0
stock_cod = (kg_codornices / cons_codornices) if cons_codornices > 0 else 0

# ====================== 3. INTERFAZ ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard Elite", "🐣 Alta de Lotes", "📈 Crecimiento y Vejez", 
    "🥚 Producción Diaria", "💸 Gastos e Inventario", "💰 Ventas y Clientes", 
    "💀 Registro de Bajas", "📜 Histórico y Borrar", "💾 SEGURIDAD"
])

# --- DASHBOARD DESGLOSADO ---
if menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control Detallado")
    
    st.subheader("📦 Stock de Pienso y Consumo por Especie")
    col_g, col_p, col_c = st.columns(3)
    
    with col_g:
        st.info("🐔 GALLINAS")
        st.metric("Stock", f"{stock_gal:.1f} días")
        st.write(f"Consumo: {cons_gallinas:.2f} kg/día")
        st.write(f"Almacén: {kg_gallinas:.1f} kg")

    with col_p:
        st.warning("🐥 POLLOS")
        st.metric("Stock", f"{stock_pol:.1f} días")
        st.write(f"Consumo: {cons_pollos:.2f} kg/día")
        st.write(f"Almacén: {kg_pollos:.1f} kg")

    with col_c:
        st.success("🐦 CODORNICES")
        st.metric("Stock", f"{stock_cod:.1f} días")
        st.write(f"Consumo: {cons_codornices:.2f} kg/día")
        st.write(f"Almacén: {kg_codornices:.1f} kg")

    st.divider()
    st.subheader("💰 Balance Económico General")
    c1, c2, c3 = st.columns(3)
    t_v = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    t_g = gastos['cantidad'].sum() if not gastos.empty else 0
    t_ah = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    perdida_bajas = bajas["perdida_estimada"].sum() if "perdida_estimada" in bajas.columns else 0
    
    c1.metric("Balance (Ventas - Gastos)", f"{(t_v - t_g):.2f}€")
    c2.metric("Ahorro Consumo Propio", f"{t_ah:.2f}€")
    c3.metric("Pérdida por Bajas", f"{perdida_bajas:.2f}€", delta_color="inverse")

# --- CRECIMIENTO CON PORCENTAJE ---
elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Estado de Desarrollo")
    config_r = {"Roja": 140, "Blanca": 155, "Chocolate": 170, "Blanco Engorde": 45, "Campero": 90, "Codorniz": 42}
    
    if lotes.empty:
        st.info("No hay lotes registrados.")
    else:
        for _, r in lotes.iterrows():
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_l).days + r["edad_inicial"]
            meta = config_r.get(r["raza"], 150)
            porcentaje = min(100, int((edad/meta)*100))
            
            with st.expander(f"Lote {r['id']}: {r['raza']} - {porcentaje}%"):
                col1, col2 = st.columns([3, 1])
                col1.progress(porcentaje / 100)
                col2.write(f"**{porcentaje}%**")
                st.write(f"🎂 Edad: **{edad} días** | Meta madurez: {meta} días")
                if edad > 700: st.error("⚠️ Alerta de vejez detectada.")

# --- SECCIÓN GASTOS (CATEGORÍAS ESPECÍFICAS) ---
elif menu == "💸 Gastos e Inventario":
    st.title("💸 Registro de Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Salud", "Otros"])
        con = st.text_input("Concepto")
        c1, c2 = st.columns(2)
        imp = c1.number_input("Importe €", 0.0)
        kg = c2.number_input("Kilos (si es pienso)", 0.0)
        if st.form_submit_button("💾 GUARDAR GASTO"):
            conn = get_conn()
            conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)",
                         (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close()
            st.success("✔️ Registrado correctamente."); st.rerun()

# --- LAS DEMÁS SECCIONES (HISTÓRICO, SEGURIDAD, ALTA, BAJAS) SE MANTIENEN IGUAL QUE LA V11 ---
# (Omitidas en este bloque por brevedad, pero presentes en tu main.py)
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Alta de Lotes")
    with st.form("f_a"):
        f_ll = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cant.", 1); ed = c1.number_input("Edad i.", 0); pr = c2.number_input("Precio Ud. €", 0.0)
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f_ll.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            conn.commit(); conn.close(); st.success("✔️ Guardado."); st.rerun()

elif menu == "💀 Registro de Bajas":
    st.title("💀 Registro de Bajas")
    if lotes.empty: st.warning("No hay lotes.")
    else:
        with st.form("f_baja"):
            f = st.date_input("Fecha"); l_id = st.selectbox("Lote ID", lotes['id'].tolist())
            cant_b = st.number_input("Cantidad", 1); mot = st.text_input("Motivo")
            if st.form_submit_button("💾 REGISTRAR"):
                lote_sel = lotes[lotes['id'] == l_id].iloc[0]
                perdida = cant_b * (lote_sel['precio_ud'] if lote_sel['precio_ud'] else 0)
                conn = get_conn(); conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo, perdida_estimada) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(cant_b), mot, perdida))
                conn.commit(); conn.close(); st.error(f"Baja registrada. Pérdida: {perdida}€"); st.rerun()

elif menu == "📜 Histórico y Borrar":
    st.title("📜 Histórico"); t_sel = st.selectbox("Tabla:", ["produccion", "gastos", "ventas", "salud", "bajas", "lotes"])
    df_h = cargar(t_sel); st.dataframe(df_h, use_container_width=True)
    id_b = st.number_input("ID a borrar", 1)
    if st.button("❌ BORRAR"): eliminar_reg(t_sel, id_b); st.rerun()

elif menu == "💾 SEGURIDAD":
    st.title("💾 Mantenimiento")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR DB", f, "corral.db")
    if st.button("🔥 REINICIAR"):
        if os.path.exists(DB_PATH): os.remove(DB_PATH); st.rerun()

else: # Producción / Ventas
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1)
        if "Producción" in menu: val = st.number_input("Huevos", 1)
        elif "Ventas" in menu: cli = st.text_input("Quién"); pr = st.text_input("Prod"); val = st.number_input("€")
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
            elif "Ventas" in menu: conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", (f_s, cli, "Venta Cliente", pr, val))
            conn.commit(); conn.close(); st.success("✔️ Hecho."); st.rerun()
