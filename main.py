import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np
import base64
import google.generativeai as genai

# --- PROTECCIÓN DE LIBRERÍAS (Evita pantallas rojas si faltan en GitHub) ---
try:
    from sklearn.linear_model import LinearRegression
    SK_OK = True
except ImportError:
    SK_OK = False

try:
    import plotly.express as px
    PX_OK = True
except ImportError:
    PX_OK = False

# =================================================================
# 1. CONFIGURACIÓN Y MEMORIA DE SESIÓN (Persistencia de Llaves)
# =================================================================
st.set_page_config(page_title="CORRAL OMNI V64", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

# Sistema de "memoria" para que las llaves no se borren al subir fotos
if 'gemini_key_mem' not in st.session_state:
    st.session_state['gemini_key_mem'] = st.secrets.get("GEMINI_KEY", "")
if 'aemet_key_mem' not in st.session_state:
    st.session_state['aemet_key_mem'] = st.secrets.get("AEMET_KEY", "")

# =================================================================
# 2. MOTOR DE DATOS Y TABLAS (V64 Completo)
# =================================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        tablas = {
            "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
            "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT",
            "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT",
            "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, unidades INTEGER",
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
# 3. INTELIGENCIA: CLIMA, CONSUMO Y GEMINI GRATIS
# =================================================================
CONFIG_ESPECIES = {
    "Gallina Roja": 0.110, "Gallina Blanca": 0.105, "Gallina Huevo Verde": 0.115, 
    "Codorniz": 0.025, "Pollo Blanco": 0.180, "Pollo Campero": 0.140
}

def get_clima_cartagena(api_key):
    if not api_key: return 20.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 20.0

def calcular_pienso_real(gastos, lotes, t_actual):
    comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo = 0
    # Parche de voracidad reducido 12% para realismo
    ajuste_realista = 0.88
    # Parche clima: Aumenta consumo 12% si temperatura > 30°C (Cartagena)
    f_clima = 1.12 if t_actual > 30 else 1.0
    
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
                dias = (datetime.now() - f_ini).days
                base = CONFIG_ESPECIES.get(f"{r['especie']} {r['raza']}", 0.100) * ajuste_realista * f_clima
                
                for d in range(dias + 1):
                    edad = r["edad_inicial"] + d
                    # Factor edad: Pollos <25 días comen 40%
                    f_edad = 0.4 if edad < 25 else 1.0
                    consumo += base * f_edad * r['cantidad']
            except: continue
    return max(0, comprado - consumo)

# --- FUNCIÓN IA GRATUITA (Cerebro Gemini V64) ---
def analizar_con_ia_gratis(blob, especie, key):
    if not key or len(key) < 10:
        return "⚠️ Por favor, introduce la Google API Key gratuita en el menú lateral."
    try:
        genai.configure(api_key=key)
        # Usamos gemini-1.5-flash, el modelo rápido y gratuito de Google
        model = genai.GenerativeModel('gemini-1.5-flash')
        img_data = {"mime_type": "image/jpeg", "data": blob}
        response = model.generate_content([f"Actúa como experto avicultor. Analiza estas aves: {especie}. Evalúa su salud, plumaje y crecimiento. Sé breve.", img_data])
        return response.text
    except Exception as e:
        return f"❌ Error de IA: {str(e)}"

# =================================================================
# 4. INTERFAZ Y NAVEGACIÓN (V64 Completo)
# =================================================================
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V64")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

st.sidebar.divider()
st.sidebar.subheader("🔑 Configuración")

# Campos de llaves con persistencia (Session State)
key_gem_in = st.sidebar.text_input("🔑 Google Gemini Key (Gratis)", value=st.session_state['gemini_key_mem'], type="password")
if key_gem_in:
    st.session_state['gemini_key_mem'] = key_gem_in

key_aem_in = st.sidebar.text_input("🌡️ AEMET Key (Cartagena)", value=st.session_state['aemet_key_mem'], type="password")
if key_aem_in:
    st.session_state['aemet_key_mem'] = key_aem_in

# Carga de datos para usar en módulos
lotes = cargar_tabla("lotes")
gastos = cargar_tabla("gastos")
produccion = cargar_tabla("produccion")
ventas = cargar_tabla("ventas")

# --- 🏠 DASHBOARD (ESTILO IMAGE_A968DA.PNG) ---
if menu == "🏠 Dashboard":
    st.title("🏠 Control de Granja V64")
    temp = get_clima_cartagena(st.session_state['aemet_key_mem'])
    stock = calcular_pienso_real(gastos, lotes, temp)
    inversion = gastos['cantidad'].sum() if not gastos.empty else 0.0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💸 Inversión Total", f"{inversion:.2f} €")
    c2.metric("🔋 Stock Pienso", f"{stock:.1f} kg", delta=f"{temp:.1f} °C (Cartagena)")
    c3.metric("🥚 Hoy", f"{produccion[produccion['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()} uds")

    # Alertas
    if stock <= 0: st.error("⚠️ Según tus registros, te has quedado sin pienso.")
    elif stock <= 10: st.warning("⚠️ Stock crítico de pienso. Compra pronto.")

    st.divider()
    col_x, col_y = st.columns(2)
    with col_x:
        st.subheader("📊 Producción por Color/Especie")
        if PX_OK and not produccion.empty:
            fig_prod = px.bar(produccion, x='fecha', y='huevos', color='color_huevo', barmode='group')
            st.plotly_chart(fig_prod, use_container_width=True)
    with col_y:
        st.subheader("🔮 IA Predictiva (Pienso)")
        # Predicción Sklearn
        if SK_OK and not gastos.empty and len(gastos[gastos['ilos_pienso']>0]) >= 3:
            try:
                df_p = gastos[gastos['ilos_pienso']>0].copy()
                df_p['f_dt'] = pd.to_datetime(df_p['fecha'], dayfirst=True)
                df_p['dias_rel'] = (df_p['f_dt'] - df_p['f_dt'].min()).dt.days
                reg = LinearRegression().fit(df_p[['dias_rel']], df_p['ilos_pienso'])
                pred = reg.predict(np.array([[df_p['dias_rel'].max() + 7]]))[0]
                st.info(f"Próxima compra estimada en **{abs(pred):.1f} kg**.")
            except: pass
        else: st.info("Registra al menos 3 gastos de pienso para activar la IA Predictiva.")

# --- 📈 CRECIMIENTO IA (V64 CON PERSISTENCIA) ---
elif menu == "📈 Crecimiento IA":
    st.title("📈 Seguimiento Visual Gemini (Gratis)")
    df_fotos = cargar_tabla("fotos")
    
    # Aviso si no hay llave
    if not st.session_state['gemini_key_mem']:
        st.warning("👈 Por favor, pega tu Google Gemini Key en el menú lateral para analizar las fotos.")
    
    if lotes.empty: st.warning("Añade un lote en 'Alta Lotes' primero.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📷 Lote {r['id']}: {r['especie']} - {r['raza']} (Lote Activo)", expanded=True):
                c_img, c_hist = st.columns([2, 1])
                with c_img:
                    f_reciente = df_fotos[df_fotos['lote_id']==r['id']].tail(1)
                    if not f_reciente.empty: st.image(f_reciente.iloc[0]['imagen'], use_column_width=True)
                    
                    st.divider()
                    t1, t2 = st.tabs(["📸 Cámara", "📁 Archivo"])
                    with t1: img_cam = st.camera_input("Hacer foto", key=f"c_{r['id']}")
                    with t2: img_file = st.file_uploader("Subir foto", type=['jpg','png','jpeg'], key=f"f_{r['id']}")
                    
                    foto_final = img_cam if img_cam else img_file
                    
                    if foto_final and st.button("💾 GUARDAR Y ANALIZAR GRATIS CON GEMINI", key=f"b_{r['id']}"):
                        blob = foto_final.read()
                        with st.spinner("IA de Google analizando aves..."):
                            # Llamada a IA con la llave persistente
                            informe = analizar_con_ia_gratis(blob, f"{r['especie']} {r['raza']}", st.session_state['gemini_key_mem'])
                            
                            # Guardado Binario de Foto y Nota
                            conn = get_conn()
                            conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                         (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), informe))
                            conn.commit()
                            st.success("✅ Foto guardada y analizada.")
                            st.rerun()
                with c_hist:
                    if not f_reciente.empty:
                        st.write("#### Último Informe IA Gemini:")
                        st.info(f_reciente.iloc[0]['nota'])

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Puesta")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote Origen", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color/Tipo de Huevo", ["Normal", "Verde", "Azul", "Codorniz"])
        h = st.number_input("Cantidad Recogida", 1)
        if st.form_submit_button("Registrar Huevos"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", 
                               (f.strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    st.title("💰 Salidas del Corral")
    tb1, tb2 = st.tabs(["Ventas / Consumo", "Bajas (Muertes)"])
    with tb1:
        with st.form("v"):
            tp = st.radio("Tipo", ["Venta", "Consumo Propio"])
            l = st.selectbox("Lote Origen", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("Importe Total €", 0.0)
            if st.form_submit_button("Registrar Salida"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades) VALUES (?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), tp, p, l, u)).connection.commit(); st.rerun()
    with tb2:
        with st.form("b"):
            l_b = st.selectbox("Lote afectado", lotes['id'].tolist() if not lotes.empty else [])
            c_b = st.number_input("Cantidad", 1); m = st.text_input("Motivo de la baja")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), l_b, c_b, m)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Registro de Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Infraestructura", "Otros"])
        dest = st.selectbox("Destinado a", ["General", "Gallinas", "Pollos", "Codornices"])
        con = st.text_input("Concepto (Ej: Saco 25kg)"); i = st.number_input("Euros €", 0.0); kg = st.number_input("Kg Pienso (si aplica)", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (f.strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Registrar Lote de Aves")
    with st.form("alta"):
        esp = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza/Especialidad", list(CONFIG_ESPECIES.keys()))
        cant = st.number_input("Cantidad Inicial", 1); ed = st.number_input("Edad (días)", 0); pr = st.number_input("Precio ud €", 0.0)
        f_e = st.date_input("Fecha de Entrada")
        if st.form_submit_button("Dar de Alta Lote Activo"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (f_e.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Planificación Navidad 2026")
    st.info("Cálculo de fechas de compra para tener los pollos maduros el 20 de Diciembre de 2026.")
    madurez = {"Blanco Engorde": 55, "Campero": 90}
    for rz, d in madurez.items():
        f_c = datetime(2026, 12, 20) - timedelta(days=d)
        st.warning(f"📌 Para pollos **{rz}**: Comprar el lote el día **{f_c.strftime('%d/%m/%Y')}**")

# --- 💾 COPIAS (V64 CON BINARIOS) ---
elif menu == "💾 Copias":
    st.title("💾 Gestión de Base de Datos")
    st.write("⚠️ Para abrir el archivo `.db`, debes usar esta misma App.")
    
    # Descargar DB completa
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar Copia de Seguridad (.db)", f, "corral_master.db")
    
    st.divider()
    nuevo_db = st.file_uploader("Restaurar Base de Datos (.db)", type="db")
    if nuevo_db and st.button("🚀 Restaurar Datos Ahora"):
        with open(DB_PATH, "wb") as f: f.write(nuevo_db.getbuffer())
        st.success("✅ Base de datos restaurada. La App se reiniciará automáticamente."); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Ver tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("Borrar ID", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
