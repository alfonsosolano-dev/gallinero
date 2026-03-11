import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V8", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_y_reparar_db():
    conn = get_conn()
    c = conn.cursor()
    # 1. Crear tablas base si no existen
    c.execute("""CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
        cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    
    # 2. INTENTO DE REPARACIÓN FORZADA DE COLUMNA
    try:
        c.execute("ALTER TABLE gastos ADD COLUMN kilos_pienso REAL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        # Si da error es porque ya existe o la tabla está bloqueada
        pass
    
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

# Ejecutar inicialización
inicializar_y_reparar_db()

# ====================== 2. CARGA Y CÁLCULOS ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas")

# Stock Pienso
t_kg = gastos["kilos_pienso"].sum() if "kilos_pienso" in gastos.columns else 0
consumo_diario = 0
if not lotes.empty:
    for _, r in lotes.iterrows():
        b_l = bajas[bajas['lote']==r['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas = r['cantidad'] - b_l
        f = 0.120 if r['especie'] == "Gallinas" else 0.150 if r['especie'] == "Pollos" else 0.030
        consumo_diario += vivas * f
dias_pienso = (t_kg / consumo_diario) if consumo_diario > 0 else 0

# ====================== 3. INTERFAZ ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard Elite", "🐣 Alta de Lotes", "📈 Crecimiento y Vejez", 
    "🥚 Producción Diaria", "💸 Gastos e Inventario", "💰 Ventas y Clientes", 
    "💉 Salud y Alertas", "📜 Histórico y Borrar", "💾 SEGURIDAD"
])

# --- GASTOS CON CONTROL DE ERRORES MEJORADO ---
if menu == "💸 Gastos e Inventario":
    st.title("💸 Registro de Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Infraestructura", "Salud", "Otros"])
        con = st.text_input("Concepto")
        c1, c2 = st.columns(2)
        imp = c1.number_input("Importe €", 0.0)
        kg = c2.number_input("Kilos (si es pienso)", 0.0)
        
        if st.form_submit_button("💾 GUARDAR GASTO"):
            try:
                conn = get_conn()
                conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)",
                             (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
                conn.commit(); conn.close()
                st.success(f"✔️ CONFIRMADO: Gasto de {imp}€ anotado."); st.rerun()
            except sqlite3.OperationalError:
                st.error("⚠️ Error de base de datos. Ve a la sección 'SEGURIDAD' y usa el botón de REPARACIÓN TOTAL.")

# --- SECCIÓN SEGURIDAD CON REPARADOR ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Seguridad y Mantenimiento")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Copias de Seguridad")
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR BASE DE DATOS", f, "corral.db")
        up = st.file_uploader("📤 RESTAURAR COPIA", type="db")
        if up:
            with open(DB_PATH, "wb") as f: f.write(up.getbuffer())
            st.success("Copia restaurada."); st.rerun()
            
    with col2:
        st.subheader("Reparación Crítica")
        st.warning("Si te da error al guardar gastos, pulsa aquí:")
        if st.button("🔥 REINICIAR BASE DE DATOS (Borrara todo)"):
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                st.success("Base de datos borrada. Refresca la página para crear la nueva.")
                st.rerun()

# --- RESTO DE SECCIONES IGUAL QUE ANTES (ALTA, CRECIMIENTO, HISTÓRICO...) ---
elif menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control")
    c1, c2, c3, c4 = st.columns(4)
    t_v = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    t_g = gastos['cantidad'].sum() if not gastos.empty else 0
    t_ah = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    t_h = prod['huevos'].sum() if not prod.empty else 0
    c1.metric("Stock Pienso", f"{dias_pienso:.1f} d"); c2.metric("Balance", f"{(t_v - t_g):.2f}€")
    c3.metric("Ahorro Casa", f"{t_ah:.2f}€"); c4.metric("Huevos", int(t_h))

elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Crecimiento")
    config_r = {"Roja": 140, "Blanca": 155, "Chocolate": 170, "Blanco Engorde": 45, "Campero": 90, "Codorniz": 42}
    if lotes.empty: st.info("Sin lotes.")
    else:
        for _, r in lotes.iterrows():
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_l).days + r["edad_inicial"]
            meta = config_r.get(r["raza"], 150)
            with st.expander(f"Lote {r['id']}: {r['raza']}"):
                st.progress(min(100, int((edad/meta)*100))/100)
                st.write(f"Edad: {edad} días")

elif menu == "📜 Histórico y Borrar":
    st.title("📜 Histórico")
    t_sel = st.selectbox("Tabla:", ["produccion", "gastos", "ventas", "salud", "bajas", "lotes"])
    df_h = cargar(t_sel); st.dataframe(df_h, use_container_width=True)
    id_b = st.number_input("ID a borrar", min_value=1, step=1)
    if st.button("❌ BORRAR"):
        if id_b in df_h['id'].values: eliminar_reg(t_sel, id_b); st.rerun()

elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Alta")
    with st.form("f_a"):
        f_ll = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cant.", 1); ed = c1.number_input("Edad i.", 0)
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, estado) VALUES (?,?,?,?,?,'Activo')", (f_ll.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed)))
            conn.commit(); conn.close(); st.success("✔️ CONFIRMADO."); st.rerun()

elif menu == "💰 Ventas y Clientes":
    st.title("💰 Ventas")
    tipo = st.radio("Tipo:", ["Venta Cliente", "Consumo Propio"])
    with st.form("f_v"):
        f = st.date_input("Fecha"); cli = st.text_input("Quién", "Familia" if tipo=="Consumo Propio" else "")
        prod_v = st.text_input("Producto"); imp = st.number_input("€", 0.0)
        if st.form_submit_button("🤝 REGISTRAR"):
            conn = get_conn(); conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cli, tipo, prod_v, imp))
            conn.commit(); conn.close(); st.success("✔️ CONFIRMADO."); st.rerun()

else: # Producción, Salud
    st.title(f"Registro: {menu}")
    with st.form("f_o"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1)
        if "Producción" in menu: val = st.number_input("Huevos", 1)
        elif "Salud" in menu: desc = st.text_area("Tratamiento"); prox = st.date_input("Próxima")
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
            elif "Salud" in menu: conn.execute("INSERT INTO salud (fecha, lote, descripcion, proxima_fecha, estado) VALUES (?,?,?,?,'Pendiente')", (f_s, int(l_id), desc, prox.strftime("%d/%m/%Y")))
            conn.commit(); conn.close(); st.success("✔️ CONFIRMADO."); st.rerun()
