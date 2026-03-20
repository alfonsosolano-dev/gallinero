import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np
import base64
import google.generativeai as genai

# --- PROTECCIÓN DE LIBRERÍAS ---
try:
    from sklearn.linear_model import LinearRegression
    SK_OK = True
except:
    SK_OK = False

try:
    import plotly.express as px
    PX_OK = True
except:
    PX_OK = False

# --- CONFIGURACIÓN DE LLAVES (SECRETS) ---
GEMINI_KEY = st.secrets.get("GEMINI_KEY", "")
AEMET_KEY = st.secrets.get("AEMET_KEY", "")

# --- INICIALIZACIÓN DE LA APP ---
st.set_page_config(page_title="CORRAL OMNI V62", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        tablas = [
            "lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)",
            "produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER, color_huevo TEXT)",
            "gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT)",
            "ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, unidades INTEGER)",
            "bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT)",
            "fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)"
        ]
        for t in tablas:
            c.execute(f"CREATE TABLE IF NOT EXISTS {t}")
    conn.close()

# --- NUEVA FUNCIÓN DE IA (CORREGIDA PARA EVITAR EL ERROR NOTFOUND) ---
def analizar_con_gemini_v62(blob, especie, api_key):
    if not api_key:
        return "⚠️ Por favor, introduce la Gemini Key en el menú lateral."
    
    try:
        genai.configure(api_key=api_key)
        # Usamos la versión más estable del modelo
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # Formateamos la imagen correctamente para la nueva versión de la API
        img_part = {"mime_type": "image/jpeg", "data": blob}
        prompt = f"Actúa como experto avicultor. Analiza estas aves de la especie {especie}. Evalúa su salud, plumaje y desarrollo. Sé breve."
        
        # Generar contenido
        response = model.generate_content([prompt, img_part])
        return response.text
    except Exception as e:
        # Si falla el 'flash-latest', probamos con el 'flash' estándar
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([f"Analiza estas aves {especie}", {"mime_type": "image/jpeg", "data": blob}])
            return response.text
        except:
            return f"❌ Error de conexión con Google: {str(e)}. Verifica que tu API Key sea correcta y tengas activada la facturación gratuita en Google AI Studio."

# --- INTERFAZ Y NAVEGACIÓN ---
inicializar_db()
st.sidebar.title("🚜 CORRAL OMNI V62")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento IA", "🥚 Producción", "💰 Ventas/Bajas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if not GEMINI_KEY: GEMINI_KEY = st.sidebar.text_input("🔑 Gemini Key", type="password")
if not AEMET_KEY: AEMET_KEY = st.sidebar.text_input("🌡️ AEMET Key", type="password")

def cargar(t): return pd.read_sql(f"SELECT * FROM {t}", get_conn())
lotes, gastos, produccion = cargar("lotes"), cargar("gastos"), cargar("produccion")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🏠 Control de Granja")
    # (Resto del código del dashboard igual que la v61...)
    st.info("Sistema listo. Selecciona una opción del menú.")

# --- 📈 CRECIMIENTO IA (ESTA ES LA PARTE QUE FALLABA) ---
elif menu == "📈 Crecimiento IA":
    st.header("📈 Análisis Visual con IA")
    df_f = cargar("fotos")
    if lotes.empty:
        st.warning("Crea un lote primero en 'Alta Lotes'.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📸 {r['especie']} {r['raza']} (ID: {r['id']})", expanded=True):
                col_i, col_d = st.columns([2, 1])
                with col_i:
                    f_db = df_f[df_f['lote_id']==r['id']].tail(1)
                    if not f_db.empty: st.image(f_db.iloc[0]['imagen'], use_column_width=True)
                    
                    sub = st.file_uploader("Subir nueva foto", type=['jpg','png','jpeg'], key=f"f{r['id']}")
                    if sub and st.button("💾 Analizar Crecimiento", key=f"b{r['id']}"):
                        blob = sub.read()
                        with st.spinner("Conectando con Google Gemini..."):
                            informe = analizar_con_gemini_v62(blob, r['especie'], GEMINI_KEY)
                            
                            if "❌ Error" not in informe:
                                conn = get_conn()
                                conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                             (r['id'], datetime.now().strftime("%d/%m/%Y"), sqlite3.Binary(blob), informe))
                                conn.commit()
                                st.success("✅ Análisis guardado.")
                                st.rerun()
                            else:
                                st.error(informe)
                with col_d:
                    if not f_db.empty:
                        st.write("### 🤖 Informe IA:")
                        st.info(f_db.iloc[0]['nota'])

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Huevos")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        col = st.selectbox("Color", ["Normal", "Verde", "Azul", "Codorniz"])
        h = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos, color_huevo) VALUES (?,?,?,?)", (f.strftime("%d/%m/%Y"), l, h, col)).connection.commit(); st.rerun()

# (El resto de módulos: Ventas, Gastos, Navidad, Alta Lotes, Copias y Histórico se mantienen igual que en la v61)
# --- 💰 VENTAS/BAJAS ---
elif menu == "💰 Ventas/Bajas":
    st.title("💰 Salidas y Bajas")
    t1, t2 = st.tabs(["Ventas", "Bajas"])
    with t1:
        with st.form("v"):
            tipo = st.radio("Tipo", ["Venta", "Consumo"])
            l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            u = st.number_input("Unidades", 1); p = st.number_input("Euros €", 0.0)
            if st.form_submit_button("Vender"):
                get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades) VALUES (?,?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), tipo, p, l, u)).connection.commit(); st.rerun()
    with t2:
        with st.form("b"):
            l_b = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
            c_b = st.number_input("Cantidad", 1); m = st.text_input("Motivo")
            if st.form_submit_button("Registrar Baja"):
                get_conn().execute("INSERT INTO bajas (fecha, lote_id, cantidad, motivo) VALUES (?,?,?,?)", 
                                   (datetime.now().strftime("%d/%m/%Y"), l_b, c_b, m)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Aves", "Infraestructura"])
        dest = st.selectbox("Destinatario", ["Gallinas", "Pollos", "Codornices", "General"])
        con = st.text_input("Concepto"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (f.strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    m = {"Blanco Engorde": 55, "Campero": 90}
    for rz, d in m.items():
        f_c = datetime(2026, 12, 20) - timedelta(days=d)
        st.warning(f"🍗 **{rz}**: Comprar el lote el **{f_c.strftime('%d/%m/%Y')}**")

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Registrar Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallina", "Codorniz", "Pollo"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Huevo Verde", "Campero", "Blanco"])
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad (días)", 0); p = st.number_input("Precio ud", 0.0)
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?, 'Activo')", 
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), p)).connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Copias de Seguridad")
    with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar .db", f, "corral_master.db")
    sub = st.file_uploader("Subir .db", type="db")
    if sub and st.button("🚀 Restaurar"):
        with open(DB_PATH, "wb") as f: f.write(sub.getbuffer())
        st.success("Hecho."); st.rerun()

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
