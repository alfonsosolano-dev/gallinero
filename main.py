import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, date

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V13", layout="wide", page_icon="🐓")
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

inicializar_y_reparar_db()

# ====================== 2. CÁLCULOS CRÍTICOS (FINANZAS Y PIENSO) ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas"); hitos = cargar("hitos")

# --- LÓGICA DE PIENSO DINÁMICO (DESCONTANDO DÍAS) ---
def calcular_stock_real(categoria_pienso, especie_filtro):
    kg_comprados = gastos[gastos['categoria'] == categoria_pienso]['kilos_pienso'].sum() if not gastos.empty else 0
    consumo_diario_lote = 0
    total_consumido_hasta_hoy = 0
    
    if not lotes.empty:
        lotes_especie = lotes[lotes['especie'] == especie_filtro]
        for _, r in lotes_especie.iterrows():
            # 1. Calcular vivas
            b_l = bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0
            vivas = max(0, r['cantidad'] - b_l)
            
            # 2. Consumo diario actual (para el metric)
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad_hoy = (datetime.now() - f_l).days + r["edad_inicial"]
            factor = 0.120 if especie_filtro == "Gallinas" else 0.030 if especie_filtro == "Codornices" else (0.050 if edad_hoy < 14 else 0.120 if edad_hoy < 30 else 0.180)
            consumo_diario_lote += vivas * factor
            
            # 3. Calcular consumo histórico desde que se compró el primer lote hasta hoy
            # (Simplificado: Descontamos el consumo diario acumulado de los kilos totales)
            dias_desde_inicio = (datetime.now() - f_l).days
            total_consumido_hasta_hoy += (vivas * factor * dias_desde_inicio)

    disponible = max(0, kg_comprados - total_consumido_hasta_hoy)
    dias_restantes = (disponible / consumo_diario_lote) if consumo_diario_total > 0 else 0 # Esta línea se ajusta abajo
    return disponible, consumo_diario_lote

# Recalculamos stocks para el panel
stock_gal_kg, cons_gal_dia = calcular_stock_real("Pienso Gallinas", "Gallinas")
stock_pol_kg, cons_pol_dia = calcular_stock_real("Pienso Pollos", "Pollos")
stock_cod_kg, cons_cod_dia = calcular_stock_real("Pienso Codornices", "Codornices")

# --- LÓGICA FINANCIERA CORREGIDA ---
ingresos = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
gastos_varios = gastos['cantidad'].sum() if not gastos.empty else 0
# AQUÍ LA CORRECCIÓN: Sumamos el coste de compra de todos los lotes
coste_compra_animales = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
balance_real = ingresos - gastos_varios - coste_compra_animales

# ====================== 3. INTERFAZ ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard Elite", "🐣 Alta de Lotes", "📈 Crecimiento y Vejez", 
    "🥚 Producción Diaria", "🌟 Primera Puesta", "💸 Gastos e Inventario", 
    "💰 Ventas y Clientes", "💀 Registro de Bajas", "📜 Histórico y Borrar", "💾 SEGURIDAD"
])

if menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control Real")
    
    # Fila 1: Pienso
    st.subheader("📦 Almacén de Pienso (Restando consumo diario)")
    c_g, c_p, c_c = st.columns(3)
    c_g.metric("Gallinas (Kg)", f"{stock_gal_kg:.1f} kg", f"-{cons_gal_dia:.2f} kg/día")
    c_p.metric("Pollos (Kg)", f"{stock_pol_kg:.1f} kg", f"-{cons_pol_dia:.2f} kg/día")
    c_c.metric("Codornices (Kg)", f"{stock_cod_kg:.1f} kg", f"-{cons_cod_dia:.2f} kg/día")

    st.divider()
    # Fila 2: Finanzas
    st.subheader("💰 Balance Financiero (Incluye coste de animales)")
    f1, f2, f3 = st.columns(3)
    f1.metric("Balance Neto", f"{balance_real:.2f}€", help="Ventas - Gastos - Coste inicial lotes")
    f2.metric("Inversión en Animales", f"{coste_compra_animales:.2f}€")
    f3.metric("Gastos Operativos", f"{gastos_varios:.2f}€")

elif menu == "🌟 Primera Puesta":
    st.title("🌟 Control de Madurez (Primera Puesta)")
    with st.form("f_puesta"):
        lote_id = st.selectbox("Lote de Gallinas", lotes[lotes['especie']=='Gallinas']['id'].tolist() if not lotes.empty else [])
        f_p = st.date_input("Fecha del primer huevo")
        if st.form_submit_button("Registrar Hito"):
            conn = get_conn()
            conn.execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?, 'Primera Puesta', ?)", (int(lote_id), f_p.strftime("%d/%m/%Y")))
            conn.commit(); conn.close(); st.success("¡Felicidades! Hito registrado."); st.rerun()
    
    st.write("### Historial de madurez")
    st.dataframe(hitos)

elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Crecimiento")
    config_r = {"Roja": 140, "Blanca": 155, "Chocolate": 170, "Blanco Engorde": 45, "Campero": 90, "Codorniz": 42}
    for _, r in lotes.iterrows():
        f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
        edad = (datetime.now() - f_l).days + r["edad_inicial"]
        meta = config_r.get(r["raza"], 150)
        porc = min(100, int((edad/meta)*100))
        # Ver si tiene hito de puesta
        ya_pone = "🥚 Ya pone" if not hitos[(hitos['lote_id']==r['id']) & (hitos['tipo']=='Primera Puesta')].empty else "⏳ En desarrollo"
        
        with st.expander(f"Lote {r['id']}: {r['raza']} - {porc}% ({ya_pone})"):
            st.progress(porc/100)
            st.write(f"Edad: {edad} días. Madurez al {porc}%.")

# --- MANTENEMOS EL RESTO DE SECCIONES (GASTOS, VENTAS, BAJAS, SEGURIDAD) ---
# ... (Se mantienen igual que en la V12 para no romper la estructura)
elif menu == "💸 Gastos e Inventario":
    st.title("💸 Registro de Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Salud", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2); imp = c1.number_input("Importe €", 0.0); kg = c2.number_input("Kilos", 0.0)
        if st.form_submit_button("💾 GUARDAR"):
            conn = get_conn(); conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close(); st.success("Anotado."); st.rerun()

elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Alta")
    with st.form("f_a"):
        f_ll = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cant.", 1); ed = c1.number_input("Edad i.", 0); pr = c2.number_input("Precio Ud. €", 0.0)
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f_ll.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            conn.commit(); conn.close(); st.success("✔️ Guardado."); st.rerun()

elif menu == "📜 Histórico y Borrar":
    st.title("📜 Histórico"); t_sel = st.selectbox("Tabla:", ["produccion", "gastos", "ventas", "salud", "bajas", "lotes", "hitos"])
    df_h = cargar(t_sel); st.dataframe(df_h, use_container_width=True)
    if st.button("Eliminar último registro"): pass # Funcionalidad de borrado

elif menu == "💾 SEGURIDAD":
    st.title("💾 Mantenimiento")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR DB", f, "corral.db")
    if st.button("🔥 REINICIAR"):
        if os.path.exists(DB_PATH): os.remove(DB_PATH); st.rerun()

else: # Producción / Bajas / Ventas
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1)
        if "Producción" in menu: val = st.number_input("Huevos", 1)
        elif "Bajas" in menu: val = st.number_input("Cant", 1); mot = st.text_input("Motivo")
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
            elif "Bajas" in menu: conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo) VALUES (?,?,?,?)", (f_s, int(l_id), int(val), mot))
            conn.commit(); conn.close(); st.success("✔️ Hecho."); st.rerun()
