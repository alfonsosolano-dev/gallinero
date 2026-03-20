import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.express as px
import google.generativeai as genai
import io

# --- 1. CONFIGURACIÓN Y MOTOR DE DATOS ---
st.set_page_config(page_title="CORRAL OMNI V89", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial_semanas INTEGER, precio_ud REAL, estado TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, kg_vendidos REAL, unidades INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)")
        
        # REPARACIÓN DE COLUMNAS (Script Antifallos)
        cols = [i[1] for i in c.execute("PRAGMA table_info(lotes)").fetchall()]
        if 'especie' not in cols: c.execute("ALTER TABLE lotes ADD COLUMN especie TEXT DEFAULT 'Gallina'")
        if 'edad_inicial_semanas' not in cols: c.execute("ALTER TABLE lotes ADD COLUMN edad_inicial_semanas INTEGER DEFAULT 0")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- 2. DICCIONARIO IA Y CONSEJOS ---
CONFIG_IA = {
    "Roja (Lohman)": {"puesta": 0.9, "cons": 0.120, "consejo": "Alta puesta. Ojo con el calcio."},
    "Blanca (Leghorn)": {"puesta": 0.85, "cons": 0.115, "consejo": "Vuelan mucho. Vallado alto."},
    "Broiler": {"madurez": 55, "cons": 0.210, "consejo": "Crecimiento rápido. Ojo patas."},
    "Campero": {"madurez": 90, "cons": 0.150, "consejo": "Sabor top. Necesita campo."},
    "Codorniz": {"madurez": 45, "cons": 0.035, "consejo": "Maduración ultra rápida."}
}

# --- 3. LOGICA DE NAVEGACIÓN ---
inicializar_db()
lotes, gastos, ventas, bajas, produccion = cargar("lotes"), cargar("gastos"), cargar("ventas"), cargar("bajas"), cargar("produccion")

st.sidebar.title("🚜 CORRAL OMNI V89")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "🔮 Predicción Pro", "📸 Crecimiento y Fotos", "🐣 Alta Lotes", "🥚 Producción", "💰 Finanzas", "🎄 Plan Navidad", "💾 Backup", "📜 Histórico"])

# --- DASHBOARD (KPIs Reales) ---
if menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control Maestro")
    inv = gastos['cantidad'].sum() if not gastos.empty else 0
    caja = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Inversión", f"{inv:.2f} €")
    c2.metric("📈 Caja Real", f"{caja:.2f} €")
    c3.metric("🏠 Ahorro Casa", f"{ahorro:.2f} €")
    c4.metric("📊 Balance", f"{(caja + ahorro - inv):.2f} €")
    
    if not produccion.empty:
        st.subheader("📈 Tendencia de Puesta (Últimos 15 registros)")
        st.line_chart(produccion.tail(15).set_index('fecha')['huevos'])

# --- CRECIMIENTO Y FOTOS (Recuperado) ---
elif menu == "📸 Crecimiento y Fotos":
    st.title("📸 Control Visual y Edad")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']} ({r['especie']})", expanded=True):
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
            edad_dias = (datetime.now() - f_lote).days + (r["edad_inicial_semanas"] * 7)
            st.info(f"📅 Edad Actual: {edad_dias} días | {CONFIG_IA.get(r['raza'], {}).get('consejo', 'Sin consejos.')}")
            
            img = st.camera_input(f"Foto Lote {r['id']}", key=f"cam_{r['id']}")
            if img:
                if st.button(f"Guardar Foto {r['id']}"):
                    get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                       (r['id'], datetime.now().strftime("%d/%m/%Y"), img.read())).connection.commit()
                    st.success("Foto guardada con éxito.")

# --- PLAN NAVIDAD (Recuperado) ---
elif menu == "🎄 Plan Navidad":
    st.title("🎄 Planificador Navidad 2026")
    st.write("Calculando fechas de compra para estar listos el 20 de Diciembre:")
    f_obj = datetime(2026, 12, 20)
    for raza, info in CONFIG_IA.items():
        if "madurez" in info:
            f_compra = f_obj - timedelta(days=info['madurez'])
            st.success(f"📌 **{raza}**: Debes comprarlos el **{f_compra.strftime('%d/%m/%Y')}**")

# --- BACKUP (Recuperado) ---
elif menu == "💾 Backup":
    st.title("💾 Copias de Seguridad")
    arch = st.file_uploader("Restaurar desde Excel", type=["xlsx"])
    if arch and st.button("🚀 RESTAURAR TODO"):
        data = pd.read_excel(arch, sheet_name=None)
        conn = get_conn()
        for t, df in data.items():
            if t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
                conn.execute(f"DELETE FROM {t}")
                df.to_sql(t, conn, if_exists='append', index=False)
        conn.commit()
        st.success("Base de datos restaurada correctamente."); st.rerun()

# --- PREDICCIÓN PRO (Actualizada) ---
elif menu == "🔮 Predicción Pro":
    st.title("🔮 Futuro del Corral (30 días)")
    fechas = [(datetime.now()+timedelta(days=i)).strftime("%d/%m") for i in range(30)]
    h_vals, c_vals = [], []
    for i in range(30):
        h_d, c_d = 0, 0
        for _, l in lotes.iterrows():
            f_a = datetime.strptime(l["fecha"], "%d/%m/%Y" if "/" in l["fecha"] else "%Y-%m-%d")
            edad_sem = l["edad_inicial_semanas"] + ((datetime.now() - f_a).days + i) / 7
            vivos = l['cantidad'] - (bajas[bajas['lote_id']==l['id']]['cantidad'].sum() if not bajas.empty else 0)
            if "Gallina" in l['especie']: h_d += (CONFIG_IA.get(l['raza'], {"puesta": 0.8})['puesta']) * vivos if edad_sem > 18 else 0
            else: c_d += (0.4 * edad_sem) * vivos
        h_vals.append(h_d); c_vals.append(c_d)
    
    st.subheader("🥚 Huevos Diarios")
    st.plotly_chart(px.line(x=fechas, y=h_vals), use_container_width=True)
    st.subheader("⚖️ Kilos Carne")
    st.plotly_chart(px.area(x=fechas, y=c_vals, color_discrete_sequence=['red']), use_container_width=True)

# --- ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Registro de Aves")
    with st.form("alta"):
        esp = st.selectbox("Especie", ["Gallina", "Pollo (Carne)", "Codorniz"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()) + ["Otras"])
        cant = st.number_input("Cantidad", 1)
        sem = st.number_input("Semanas de vida", 0)
        pr = st.number_input("Precio/ud €", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial_semanas, precio_ud, estado) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(sem), pr, "Activo")).connection.commit()
            st.rerun()

# --- FINANZAS (Venta vs Consumo Propio) ---
elif menu == "💰 Finanzas":
    t1, t2 = st.tabs(["💸 Gastos", "🛒 Ventas/Salidas"])
    with t1:
        with st.form("g"):
            cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Medicina", "Infraestructura"])
            imp = st.number_input("Importe €", 0.0)
            kg = st.number_input("Kg Pienso", 0.0)
            if st.form_submit_button("Guardar Gasto"):
                get_conn().execute("INSERT INTO gastos (fecha, categoria, cantidad, kilos_pienso) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), cat, imp, kg)).connection.commit(); st.rerun()
    with t2:
        with st.form("v"):
            tipo = st.radio("Tipo de Salida", ["Venta Cliente", "Consumo Propio"])
            l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            imp = st.number_input("Valor/Importe €", 0.0)
            u = st.number_input("Unidades (Huevos/Aves)", 0)
            if st.form_submit_button("Registrar Salida"):
                get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, unidades) VALUES (?,?,?,?,?,?)",
                                   (datetime.now().strftime("%d/%m/%Y"), "General", tipo, imp, l, u)).connection.commit(); st.rerun()

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    tab = st.selectbox("Tabla", ["lotes", "produccion", "gastos", "ventas", "bajas", "fotos"])
    df = cargar(tab)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        idx = st.number_input("ID a borrar", int(df['id'].min()))
        if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {tab} WHERE id={idx}").connection.commit(); st.rerun()
