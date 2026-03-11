import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V11", layout="wide", page_icon="🐓")
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
    
    # Parche progresivo de columnas
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

# ====================== 2. CARGA Y CÁLCULOS ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas")

# --- CONSUMO DINÁMICO Y PÉRDIDAS ---
t_kg_comprados = gastos["kilos_pienso"].sum() if "kilos_pienso" in gastos.columns else 0
consumo_diario_total = 0
perdida_total_bajas = bajas["perdida_estimada"].sum() if "perdida_estimada" in bajas.columns else 0

if not lotes.empty:
    for _, r in lotes.iterrows():
        f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
        edad = (datetime.now() - f_l).days + (r["edad_inicial"] if r["edad_inicial"] else 0)
        b_l = bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas = max(0, r['cantidad'] - b_l)
        
        # Factor Consumo
        if r['especie'] == "Gallinas": factor = 0.120
        elif r['especie'] == "Codornices": factor = 0.030
        elif r['especie'] == "Pollos":
            factor = 0.050 if edad < 14 else 0.120 if edad < 30 else 0.180
        else: factor = 0.100
        consumo_diario_total += vivas * factor

dias_pienso = (t_kg_comprados / consumo_diario_total) if consumo_diario_total > 0 else 0

# ====================== 3. INTERFAZ ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard Elite", "🐣 Alta de Lotes", "📈 Crecimiento y Vejez", 
    "🥚 Producción Diaria", "💸 Gastos e Inventario", "💰 Ventas y Clientes", 
    "💀 Registro de Bajas", "💉 Salud y Alertas", "📜 Histórico y Borrar", "💾 SEGURIDAD"
])

# --- DASHBOARD ACTUALIZADO ---
if menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control")
    c1, c2, c3, c4 = st.columns(4)
    t_v = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    t_g = gastos['cantidad'].sum() if not gastos.empty else 0
    t_ah = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    c1.metric("Stock Pienso", f"{dias_pienso:.1f} d")
    c2.metric("Balance Ventas", f"{(t_v - t_g):.2f}€")
    c3.metric("Ahorro Casa", f"{t_ah:.2f}€")
    c4.metric("Pérdida Bajas", f"{perdida_total_bajas:.2f}€", delta_color="inverse")
    
    st.info(f"📊 Consumo actual: {consumo_diario_total:.2f} kg/día. Huevos totales: {int(prod['huevos'].sum() if not prod.empty else 0)}")

# --- REGISTRO DE BAJAS CON CÁLCULO DE PÉRDIDA ---
elif menu == "💀 Registro de Bajas":
    st.title("💀 Registro de Bajas")
    if lotes.empty: st.warning("No hay lotes para registrar bajas.")
    else:
        with st.form("f_baja"):
            f = st.date_input("Fecha"); l_id = st.selectbox("Lote afectado (ID)", lotes['id'].tolist())
            cant_b = st.number_input("Cantidad de bajas", 1); mot = st.text_input("Motivo")
            
            if st.form_submit_button("💾 REGISTRAR BAJA"):
                # Calcular pérdida basada en el precio_ud del lote
                lote_sel = lotes[lotes['id'] == l_id].iloc[0]
                precio_u = lote_sel['precio_ud'] if lote_sel['precio_ud'] else 0
                perdida = cant_b * precio_u
                
                conn = get_conn()
                conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo, perdida_estimada) VALUES (?,?,?,?,?)",
                             (f.strftime("%d/%m/%Y"), int(l_id), int(cant_b), mot, perdida))
                conn.commit(); conn.close()
                st.error(f"Registrado: {cant_b} bajas. Pérdida económica: {perdida:.2f}€"); st.rerun()

# --- LAS DEMÁS SECCIONES SE MANTIENEN IGUAL (ALTA, GASTOS, SEGURIDAD...) ---
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Alta de Lotes")
    with st.form("f_a"):
        f_ll = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cant.", 1); ed = c1.number_input("Edad i.", 0); pr = c2.number_input("Precio Ud. €", 0.0)
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f_ll.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            conn.commit(); conn.close(); st.success("✔️ Guardado."); st.rerun()

elif menu == "💸 Gastos e Inventario":
    st.title("💸 Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Infraestructura", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2); imp = c1.number_input("€", 0.0); kg = c2.number_input("Kilos", 0.0)
        if st.form_submit_button("💾 GUARDAR"):
            conn = get_conn(); conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close(); st.success("✔️ Anotado."); st.rerun()

elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Crecimiento")
    config_r = {"Roja": 140, "Blanca": 155, "Chocolate": 170, "Blanco Engorde": 45, "Campero": 90, "Codorniz": 42}
    for _, r in lotes.iterrows():
        f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
        edad = (datetime.now() - f_l).days + r["edad_inicial"]
        meta = config_r.get(r["raza"], 150)
        with st.expander(f"Lote {r['id']}: {r['raza']}"):
            st.progress(min(100, int((edad/meta)*100))/100); st.write(f"Edad: {edad} días")

elif menu == "📜 Histórico y Borrar":
    st.title("📜 Histórico"); t_sel = st.selectbox("Tabla:", ["produccion", "gastos", "ventas", "salud", "bajas", "lotes"])
    df_h = cargar(t_sel); st.dataframe(df_h, use_container_width=True)
    id_b = st.number_input("ID a borrar", 1); 
    if st.button("❌ BORRAR"): eliminar_reg(t_sel, id_b); st.rerun()

elif menu == "💾 SEGURIDAD":
    st.title("💾 Mantenimiento")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR DB", f, "corral.db")
    if st.button("🔥 REINICIAR"):
        if os.path.exists(DB_PATH): os.remove(DB_PATH); st.rerun()

else: # Producción / Salud / Ventas
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1)
        if "Producción" in menu: val = st.number_input("Huevos", 1)
        elif "Salud" in menu: d = st.text_area("Tratamiento"); p = st.date_input("Próxima")
        elif "Ventas" in menu: cli = st.text_input("Quién"); pr = st.text_input("Prod"); val = st.number_input("€")
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
            elif "Salud" in menu: conn.execute("INSERT INTO salud (fecha, lote, descripcion, proxima_fecha, estado) VALUES (?,?,?,?,'Pendiente')", (f_s, int(l_id), d, p.strftime("%d/%m/%Y")))
            conn.commit(); conn.close(); st.success("✔️ Hecho."); st.rerun()
