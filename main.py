import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL IA ELITE V18", layout="wide", page_icon="🤖")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_y_migrar_db():
    conn = get_conn()
    c = conn.cursor()
    # Tablas base
    c.execute("CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, kilos_finales REAL, unidades INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, perdida_estimada REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS hitos(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT)")
    
    # MIGRACIÓN: Añadir columnas si no existen (Sin borrar datos)
    columnas_ventas = [col[1] for col in c.execute("PRAGMA table_info(ventas)")]
    if "unidades" not in columnas_ventas:
        c.execute("ALTER TABLE ventas ADD COLUMN unidades INTEGER DEFAULT 1")
    if "kilos_finales" not in columnas_ventas:
        c.execute("ALTER TABLE ventas ADD COLUMN kilos_finales REAL DEFAULT 0")
        
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

inicializar_y_migrar_db()

# ====================== 2. MOTOR DE IA BIOLÓGICA ======================
lotes = cargar("lotes"); gastos = cargar("gastos"); ventas = cargar("ventas")
bajas = cargar("bajas"); hitos = cargar("hitos"); produccion = cargar("produccion")

# Parámetros IA: Madurez y Consumo
DICC_IA = {
    "Roja": {"puesta_dias": 145, "cons_adulto": 0.120},
    "Blanca": {"puesta_dias": 140, "cons_adulto": 0.115},
    "Chocolate": {"puesta_dias": 160, "cons_adulto": 0.130},
    "Mochuela (Pintada)": {"puesta_dias": 210, "cons_adulto": 0.100},
    "Blanco Engorde": {"madurez_dias": 55, "cons_adulto": 0.210},
    "Campero": {"madurez_dias": 90, "cons_adulto": 0.150},
    "Codorniz": {"puesta_dias": 45, "cons_adulto": 0.035}
}

def obtener_consumo_diario(raza, edad_dias):
    base = DICC_IA.get(raza, {"cons_adulto": 0.110})
    ca = base.get("cons_adulto", 0.110)
    if edad_dias < 30: return ca * 0.4
    if edad_dias < 90: return ca * 0.75
    return ca

def calc_stock(cat, esp):
    kg_c = gastos[gastos['categoria'] == cat]['kilos_pienso'].sum() if not gastos.empty else 0
    cons_tot = 0
    if not lotes.empty:
        for _, r in lotes[lotes['especie'] == esp].iterrows():
            vivas = max(0, r['cantidad'] - (bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0))
            dias = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days
            for d in range(dias + 1):
                cons_tot += vivas * obtener_consumo_diario(r["raza"], r["edad_inicial"] + d)
    return max(0, kg_c - cons_tot)

# ====================== 3. INTERFAZ Y NAVEGACIÓN ======================
st.sidebar.title("🤖 CORRAL IA V18")
seccion = st.sidebar.radio("SISTEMA:", [
    "🏠 Dashboard", "📈 IA Crecimiento", "🥚 Producción", "💰 Ventas", 
    "🎄 IA Navidad", "🐣 Alta Inteligente", "💸 Gastos", "📜 Histórico", "💾 EXPORTAR/SEGURIDAD"
])

if seccion == "🏠 Dashboard":
    st.title("🏠 Panel de Control Inteligente")
    s_gal = calc_stock("Pienso Gallinas", "Gallinas")
    s_pol = calc_stock("Pienso Pollos", "Pollos")
    s_cod = calc_stock("Pienso Codornices", "Codornices")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Stock Gallinas", f"{s_gal:.2f} kg")
    c2.metric("Stock Pollos", f"{s_pol:.2f} kg")
    c3.metric("Stock Codornices", f"{s_cod:.2f} kg")
    
    st.divider()
    # Resumen de producción semanal
    if not produccion.empty:
        st.subheader("📊 Producción de Huevos (Últimos registros)")
        st.line_chart(produccion.set_index('fecha')['huevos'])

elif seccion == "📈 IA Crecimiento":
    st.title("📈 Predicción de Madurez y Puesta")
    for _, r in lotes.iterrows():
        edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
        info = DICC_IA.get(r["raza"], {"puesta_dias": 150, "madurez_dias": 90})
        
        meta = info.get("puesta_dias") if "puesta_dias" in info else info.get("madurez_dias")
        porc = min(100, int((edad/meta)*100))
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**Lote {r['id']} - {r['raza']}** ({edad} días)")
            st.progress(porc/100)
        with col2:
            if porc < 100:
                faltan = meta - edad
                f_estimada = datetime.now() + timedelta(days=faltan)
                st.warning(f"Puesta/Venta: {f_estimada.strftime('%d/%m/%Y')}")
            else:
                st.success("¡Lote Maduro!")

elif seccion == "🥚 Producción":
    st.title("🥚 Gestión de Producción")
    tab1, tab2 = st.tabs(["Registrar", "Histórico de Puesta"])
    with tab1:
        with st.form("f_p"):
            f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            cant = st.number_input("Huevos", 1)
            if st.form_submit_button("Guardar"):
                get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l_id, cant)).connection.commit(); st.rerun()
    with tab2:
        st.dataframe(produccion, use_container_width=True)

elif seccion == "💰 Ventas":
    st.title("💰 Ventas y Margen IA")
    with st.form("f_v"):
        c1, c2, c3 = st.columns(3)
        f = c1.date_input("Fecha"); l_id = c2.selectbox("Lote Origen", lotes['id'].tolist() if not lotes.empty else [])
        t_v = c3.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        
        col_a, col_b, col_c = st.columns(3)
        uds = col_a.number_input("Unidades", 1)
        kgs = col_b.number_input("Kilos Totales", 0.0)
        precio = col_c.number_input("Precio Total €", 0.0)
        
        cli = st.text_input("Cliente"); conc = st.text_input("Concepto")
        if st.form_submit_button("Registrar Venta"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad, lote_id, kilos_finales, unidades) VALUES (?,?,?,?,?,?,?,?)", 
                               (f.strftime("%d/%m/%Y"), cli, t_v, conc, precio, int(l_id), kgs, uds)).connection.commit(); st.rerun()

elif seccion == "🎄 IA Navidad":
    st.title("🎄 Asesor Inteligente de Navidad")
    st.info("La IA calcula el momento óptimo de compra para llegar al 20 de diciembre con el peso ideal.")
    for raza in ["Blanco Engorde", "Campero"]:
        info = DICC_IA[raza]
        f_obj = datetime(datetime.now().year, 12, 20)
        f_compra = f_obj - timedelta(days=info['madurez_dias'])
        # Cálculo de consumo total
        cons_est = info['madurez_dias'] * info['cons_adulto'] * 0.8 # Factor medio
        
        st.subheader(f"Plan para {raza}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Fecha de Compra", f_compra.strftime("%d/%m"))
        c2.metric("Días de Engorde", info['madurez_dias'])
        c3.metric("Pienso est. /ave", f"{cons_est:.2f} kg")

elif seccion == "🐣 Alta Inteligente":
    st.title("🐣 Alta de Lotes con IA")
    with st.form("f_a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza (IA Detect)", ["Roja", "Blanca", "Chocolate", "Mochuela (Pintada)", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cant", 1); ed = c2.number_input("Edad inicial", 0); pr = c3.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

elif seccion == "💾 EXPORTAR/SEGURIDAD":
    st.title("💾 Gestión de Datos y Excel")
    
    # BOTÓN DE EXPORTACIÓN A EXCEL
    if st.button("📊 GENERAR EXCEL DE TODOS LOS REGISTROS"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for t in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                df = cargar(t)
                df.to_excel(writer, sheet_name=t, index=False)
        st.download_button(label="📥 Descargar Excel", data=output.getvalue(), file_name=f"corral_ia_{datetime.now().strftime('%Y%m%d')}.xlsx")

    st.divider()
    if st.button("🔥 BORRAR BASE DE DATOS"):
        if os.path.exists(DB_PATH): os.remove(DB_PATH); st.rerun()

# --- Secciones simplificadas de Gastos e Histórico ---
elif seccion == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Cat", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("€", 0.0); kg = st.number_input("Kg", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

elif seccion == "📜 Histórico":
    st.title("📜 Histórico")
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    st.dataframe(cargar(t), use_container_width=True)
