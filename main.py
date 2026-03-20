import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np
import base64
import google.generativeai as genai

# --- IMPORTACIONES PROTEGIDAS ---
try:
    from sklearn.linear_model import LinearRegression
except ImportError:
    LinearRegression = None

# =================================================================
# BLOQUE 1: CONFIGURACIÓN Y BASE DE DATOS
# =================================================================
st.set_page_config(page_title="CORRAL IA OMNI V57", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
        # Parches de columnas
        if n == "produccion":
            try: c.execute("ALTER TABLE produccion ADD COLUMN color_huevo TEXT")
            except: pass
        if n == "gastos":
            for col in ["ilos_pienso REAL", "destinado_a TEXT"]:
                try: c.execute(f"ALTER TABLE gastos ADD COLUMN {col}")
                except: pass
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: MOTOR DE INTELIGENCIA (CLIMA + CONSUMO + IA)
# =================================================================
CONFIG_ESPECIES = {
    "Gallina Roja": 0.110, "Gallina Blanca": 0.105, "Gallina Huevo Verde": 0.115, 
    "Codorniz Japónica": 0.025, "Pollo Blanco Engorde": 0.180, "Pollo Campero": 0.140
}

def get_clima_cartagena(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

def calcular_pienso_pro(gastos, lotes, t_actual):
    comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    f_clima = 1.15 if t_actual > 30 else (1.10 if t_actual < 10 else 1.0)
    
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * 0.85 * f_clima
                for d in range(dias + 1):
                    edad = r["edad_inicial"] + d
                    f_edad = 0.3 if edad < 20 else (0.7 if edad < 45 else 1.0)
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, comprado - consumo)

# =================================================================
# BLOQUE 3: INTERFAZ Y MENÚS
# =================================================================
inicializar_db()
lotes, gastos, produccion, ventas = cargar_tabla("lotes"), cargar_tabla("gastos"), cargar_tabla("produccion"), cargar_tabla("ventas")

st.sidebar.title("🚜 CORRAL OMNI V57")
menu = st.sidebar.radio("", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])
GEMINI_KEY = st.sidebar.text_input("🔑 Google Gemini Key", type="password")
AEMET_KEY = st.sidebar.text_input("🌡️ AEMET Key", type="password")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🚜 Dashboard General")
    temp = get_clima_cartagena(AEMET_KEY)
    stock = calcular_pienso_pro(gastos, lotes, temp)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c2.metric("🌡️ Cartagena", f"{temp:.1f} °C")
    c3.metric("🥚 Hoy", f"{produccion[produccion['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()} uds")
    c4.metric("🦅 Aves Activas", f"{int(lotes['cantidad'].sum()) if not lotes.empty else 0}")

    if LinearRegression and not gastos.empty and len(gastos[gastos['ilos_pienso']>0]) >= 3:
        try:
            df_p = gastos[gastos['ilos_pienso']>0].copy()
            df_p['f_dt'] = pd.to_datetime(df_p['fecha'], dayfirst=True)
            df_p['dias_rel'] = (df_p['f_dt'] - df_p['f_dt'].min()).dt.days
            reg = LinearRegression().fit(df_p[['dias_rel']], df_p['ilos_pienso'])
            pred = reg.predict(np.array([[df_p['dias_rel'].max() + 7]]))[0]
            st.info(f"🔮 IA Predictiva: Próxima compra estimada en **{abs(pred):.1f} kg**")
        except: pass

# --- 📈 CRECIMIENTO IA (DISEÑO IMAGE_0.PNG) ---
elif menu == "📈 Crecimiento IA":
    st.title("📈 Seguimiento Visual Gemini")
    df_fotos = cargar_tabla("fotos")
    if lotes.empty: st.warning("Crea un lote primero.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📷 {r['especie']} {r['raza']} (Lote {r['id']})", expanded=True):
                col_izq, col_der = st.columns([2, 1])
                with col_izq:
                    prev = df_fotos[df_fotos['lote_id']==r['id']].tail(1)
                    if not prev.empty: st.image(prev.iloc[0]['imagen'], use_column_width=True)
                    t1, t2 = st.tabs(["🎥 Cámara", "📁 Archivo"])
                    with t1: cam = st.camera_input("Foto", key=f"c_{r['id']}")
                    with t2: arc = st.file_uploader("Subir", type=['jpg','png','jpeg'], key=f"f_{r['id']}")
                    foto = cam if cam else arc
                    if foto and st.button("💾 Analizar con Gemini", key=f"b_{r['id']}"):
                        blob = foto.read()
                        genai.configure(api_key=GEMINI_KEY)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        res = model.generate_content([f"Analiza estas aves: {r['especie']}. Salud y plumaje.", {"mime_type": "image/jpeg", "data": blob}])
                        conn = get_conn()
                        conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                     (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), res.text))
                        conn.commit(); st.rerun()
                with col_der:
                    st.metric("Total Aves", f"{r['cantidad']}")
                    if not prev.empty: st.info(f"Informe IA: {prev.iloc[0]['nota']}")

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Puesta")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color/Tipo", ["Normal", "Verde", "Azul", "Codorniz"])
        h = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (f.strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS ---
elif menu == "💰 Ventas":
    st.title("💰 Ventas y Salidas")
    with st.form("v"):
        tipo = st.radio("Tipo", ["Venta", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades", 1); k = st.number_input("Kg Carne", 0.0); p = st.number_input("Total €", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), tipo, p, l, k, u)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Otros"])
        dest = st.selectbox("Destinado a", ["General", "Gallinas", "Pollos", "Codornices"])
        con = st.text_input("Concepto"); i = st.number_input("€", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    madurez = {"Blanco Engorde": 55, "Campero": 90}
    for rz, d in madurez.items():
        f_c = datetime(2026, 12, 20) - timedelta(days=d)
        st.warning(f"📌 Para {rz}: Comprar lote el **{f_c.strftime('%d/%m/%Y')}**")

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Registrar Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", list(CONFIG_ESPECIES.keys()))
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad (días)", 0)
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, estado) VALUES (?,?,?,?,?, 'Activo')", 
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed))).connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Backup")
    with open(DB_PATH, "rb") as f:
        st.download_button("📥 Descargar .DB (Fotos incluidas)", f, "corral_master.db")
    sub = st.file_uploader("Subir .DB", type="db")
    if sub and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.success("Restaurado."); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
