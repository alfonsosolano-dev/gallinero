import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np
import base64
import google.generativeai as genai

# --- FIX DE LIBRERÍAS (Para evitar errores de pantalla roja) ---
try:
    from sklearn.linear_model import LinearRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# =================================================================
# 1. BASE DE DATOS PROFESIONAL
# =================================================================
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Tablas con todas las columnas de tu Excel y capturas
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# 2. MOTOR DE INTELIGENCIA (IA + CLIMA + PIENSO)
# =================================================================
CONFIG_ESPECIES = {
    "Gallina Roja": 0.110, "Gallina Blanca": 0.105, "Gallina Huevo Verde": 0.115, 
    "Codorniz": 0.025, "Pollo Blanco": 0.180, "Pollo Campero": 0.140
}

def get_clima(api_key):
    if not api_key: return 20.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        return float(requests.get(r["datos"], timeout=5).json()[-1]["ta"])
    except: return 20.0

def calcular_pienso_real(gastos, lotes, t_actual):
    comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    f_clima = 1.12 if t_actual > 30 else 1.0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * 0.88 * f_clima
                for d in range(dias + 1):
                    f_edad = 0.4 if (r["edad_inicial"] + d) < 25 else 1.0
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, comprado - consumo)

# =================================================================
# 3. INTERFAZ (MENÚS E IZQUIERDA)
# =================================================================
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V58")
menu = st.sidebar.radio("", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

GEMINI_KEY = st.sidebar.text_input("🔑 Gemini Key", type="password")
AEMET_KEY = st.sidebar.text_input("🌡️ AEMET Key", type="password")

lotes, gastos, produccion, ventas = cargar_tabla("lotes"), cargar_tabla("gastos"), cargar_tabla("produccion"), cargar_tabla("ventas")

# --- 🏠 DASHBOARD (ESTILO CAPTURA IMAGE_A968DA.PNG) ---
if menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control")
    temp = get_clima(AEMET_KEY)
    stock = calcular_pienso_real(gastos, lotes, temp)
    inversion = gastos['cantidad'].sum() if not gastos.empty else 0.0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💸 Inversión Total", f"{inversion:.2f} €")
    c2.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c3.metric("⏳ Autonomía", f"{int(stock/2) if stock > 0 else 0} días")

    if stock <= 0:
        st.error("⚠️ Según tus compras y el tiempo de los lotes, no debería quedar pienso.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📊 Gastos por Destinatario")
        if not gastos.empty:
            st.bar_chart(gastos.groupby('destinado_a')['cantidad'].sum())
    with col_b:
        st.subheader("🥚 Producción Reciente")
        if not produccion.empty:
            st.line_chart(produccion.set_index('fecha')['huevos'])

# --- 📈 CRECIMIENTO IA ---
elif menu == "📈 Crecimiento IA":
    st.title("📈 Análisis de Aves con Gemini")
    df_f = cargar_tabla("fotos")
    for _, r in lotes.iterrows():
        with st.expander(f"📸 {r['especie']} {r['raza']} (ID: {r['id']})"):
            c_iz, c_de = st.columns([2, 1])
            with c_iz:
                prev = df_f[df_f['lote_id']==r['id']].tail(1)
                if not prev.empty: st.image(prev.iloc[0]['imagen'])
                img = st.file_uploader("Subir evolución", type=['jpg','png','jpeg'], key=f"f{r['id']}")
                if img and st.button("Analizar con IA", key=f"b{r['id']}"):
                    blob = img.read()
                    genai.configure(api_key=GEMINI_KEY)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    res = model.generate_content([f"Analiza estas {r['especie']}. Salud y peso.", {"mime_type": "image/jpeg", "data": blob}])
                    get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                 (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), res.text)).connection.commit(); st.rerun()
            with c_de:
                if not prev.empty: st.info(prev.iloc[0]['nota'])

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Huevos")
    with st.form("p"):
        f = st.date_input("Fecha")
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color", ["Normal", "Verde", "Azul", "Codorniz"])
        h = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (f.strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    st.title("💰 Salidas del Corral")
    tab_v, tab_b = st.tabs(["Ventas/Consumo", "Bajas (Muertes)"])
    with tab_v:
        with st.form("v"):
            tipo = st.radio("Tipo", ["Venta", "Consumo Propio"])
            l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("Total €", 0.0)
            if st.form_submit_button("Registrar Venta"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades) VALUES (?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), tipo, p, l, u)).connection.commit(); st.rerun()
    with tab_b:
        with st.form("b"):
            l_b = st.selectbox("Lote afectado", lotes['id'].tolist() if not lotes.empty else [])
            c_b = st.number_input("Cantidad", 1); mot = st.text_input("Motivo")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), l_b, c_b, mot)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Registro de Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Medicina", "Infraestructura", "Otros"])
        dest = st.selectbox("Destinatario", ["Gallinas", "Pollos", "Codornices", "General"])
        con = st.text_input("Concepto (Ej: Saco 25kg)"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso (si aplica)", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (f.strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Gestión de Datos")
    st.write("Usa el archivo `.db` para restaurar todo en otro dispositivo.")
    with open(DB_PATH, "rb") as f:
        st.download_button("📥 Descargar Copia de Seguridad", f, "corral_master.db")
    
    sub = st.file_uploader("Subir Copia (.db)", type="db")
    if sub and st.button("🚀 Restaurar Ahora"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.success("Base de datos restaurada con éxito."); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Planificación Navidad 2026")
    st.info("Cálculo basado en 20 de Diciembre como fecha límite.")
    madurez = {"Blanco Engorde": 55, "Campero": 90}
    for rz, d in madurez.items():
        f_c = datetime(2026, 12, 20) - timedelta(days=d)
        st.warning(f"🍗 **{rz}**: Debes comprar el lote el día **{f_c.strftime('%d/%m/%Y')}**")

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Registrar Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Huevo Verde", "Campero", "Blanco"])
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad inicial (días)", 0)
        pr = st.number_input("Precio ud €", 0.0)
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Ver tabla:", ["lotes", "gastos", "produccion", "ventas", "bajas"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
