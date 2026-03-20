import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np
import base64

# --- IMPORTACIONES PROTEGIDAS ---
try:
    from sklearn.linear_model import LinearRegression
except ImportError:
    LinearRegression = None

try:
    import plotly.express as px
except ImportError:
    px = None

# =================================================================
# BLOQUE 1: CONFIGURACIÓN Y MOTOR DE DATOS (V54.0)
# =================================================================
st.set_page_config(page_title="CORRAL IA MASTER PRO V54.0", layout="wide", page_icon="🥚")

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
        # Parches de columnas críticas
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
# BLOQUE 2: INTELIGENCIA DE CONSUMO Y CLIMA
# =================================================================
CONFIG_ESPECIES = {
    "Gallina Roja": 0.110, "Gallina Blanca": 0.105, "Gallina Huevo Verde": 0.115, 
    "Codorniz Japónica": 0.025, "Pollo Blanco Engorde": 0.180, "Pollo Campero": 0.140
}

def get_weather_cartagena(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

def calcular_pienso_real(gastos, lotes, t_actual):
    comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    ajuste = 0.85 # Voracidad reducida para realismo
    f_clima = 1.15 if t_actual > 30 else (1.10 if t_actual < 10 else 1.0)
    
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * ajuste * f_clima
                for d in range(dias + 1):
                    edad = r["edad_inicial"] + d
                    f_edad = 0.3 if edad < 20 else (0.7 if edad < 45 else 1.0)
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, comprado - consumo)

# =================================================================
# BLOQUE 3: IA VISUAL EVOLUTIVA
# =================================================================
def analizar_evolucion(foto_act, foto_prev_blob, dias, especie, api_key):
    if not api_key: return "Sin API Key."
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    img_b64 = base64.b64encode(foto_act).decode('utf-8')
    prompt = f"Analiza estas {especie}. Han pasado {dias} días desde la última foto. Evalúa crecimiento y salud."
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt},
                      {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}]
        )
        return res.choices[0].message.content
    except Exception as e: return f"Error IA: {e}"

# =================================================================
# BLOQUE 4: INTERFAZ Y NAVEGACIÓN
# =================================================================
inicializar_db()
lotes, gastos, produccion, ventas = cargar_tabla("lotes"), cargar_tabla("gastos"), cargar_tabla("produccion"), cargar_tabla("ventas")

st.sidebar.title("🚜 CORRAL IA V54")
menu = st.sidebar.radio("", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Puesta", "💸 Gastos", "🐣 Alta Aves", "💰 Ventas", "🎄 Navidad", "📜 Histórico", "💾 Copias"])
OPENAI_KEY = st.sidebar.text_input("OpenAI Key", type="password")
AEMET_KEY = st.sidebar.text_input("AEMET Key (Cartagena)", type="password")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🚜 Panel General")
    temp = get_weather_cartagena(AEMET_KEY)
    stock = calcular_pienso_real(gastos, lotes, temp)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c2.metric("🌡️ Temp Cartagena", f"{temp:.1f} °C")
    c3.metric("🥚 Puesta Total", f"{produccion['huevos'].sum() if not produccion.empty else 0} uds")

    if px and not produccion.empty:
        st.subheader("📊 Producción por Especie/Color")
        fig = px.bar(produccion, x='fecha', y='huevos', color='color_huevo', title="Evolución de Puesta")
        st.plotly_chart(fig, use_container_width=True)

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.title("📈 Seguimiento Visual Evolutivo")
    if lotes.empty: st.warning("No hay aves registradas.")
    else:
        df_fotos = cargar_tabla("fotos")
        for _, r in lotes.iterrows():
            with st.expander(f"📸 {r['especie']} {r['raza']} (Lote {r['id']})", expanded=True):
                c_img, c_hist = st.columns([2, 1])
                with c_img:
                    t1, t2 = st.tabs(["🎥 Cámara", "📁 Galería"])
                    with t1: cam = st.camera_input("Foto", key=f"c_{r['id']}")
                    with t2: arc = st.file_uploader("Archivo", type=['jpg','png','jpeg'], key=f"a_{r['id']}")
                    
                    foto = cam if cam else arc
                    if foto and st.button("💾 Guardar y Analizar", key=f"b_{r['id']}"):
                        blob = foto.read()
                        # Buscar previa para comparar
                        prev = df_fotos[df_fotos['lote_id']==r['id']].tail(1)
                        dias = (datetime.now() - datetime.strptime(prev.iloc[0]['fecha'], "%d/%m/%Y")).days if not prev.empty else 0
                        
                        nota = analizar_evolucion(blob, None, dias, r['especie'], OPENAI_KEY)
                        
                        conn = get_conn()
                        conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                     (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), nota))
                        conn.commit(); st.success("Análisis completado."); st.rerun()
                with c_hist:
                    hist = df_fotos[df_fotos['lote_id']==r['id']].tail(3)
                    for i, h in hist.iterrows():
                        st.image(h['imagen'], caption=f"{h['fecha']}")
                        if h['nota']: st.caption(f"IA: {h['nota'][:100]}...")

# --- 🥚 PUESTA ---
elif menu == "🥚 Puesta":
    st.title("🥚 Registro de Huevos")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Tipo/Color", ["Normal", "Verde (Araucana)", "Azul", "Codorniz"])
        cant = st.number_input("Cantidad", 1)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", 
                               (f.strftime("%d/%m/%Y"), l, cant, col)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Otros"])
        dest = st.selectbox("Destinado a", ["General", "Gallinas", "Pollos", "Codornices"])
        con = st.text_input("Concepto"); i = st.number_input("Euros €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (f.strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🐣 ALTA AVES ---
elif menu == "🐣 Alta Aves":
    st.title("🐣 Registrar Aves")
    with st.form("alta"):
        esp = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Huevo Verde", "Campero", "Blanco Engorde", "Codorniz Japónica"])
        cant = st.number_input("Cantidad", 1); edad = st.number_input("Edad (días)", 0); f_e = st.date_input("Fecha")
        if st.form_submit_button("Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, estado) VALUES (?,?,?,?,?,'Activo')", 
                               (f_e.strftime("%d/%m/%Y"), esp, rz, int(cant), int(edad))).connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Backup")
    with open(DB_PATH, "rb") as f:
        st.download_button("📥 Bajar Base de Datos (.db)", f, "corral_master.db")
    sub = st.file_uploader("Subir Backup", type="db")
    if sub and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.success("Listo."); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("Borrar ID", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
