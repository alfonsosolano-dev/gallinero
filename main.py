import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import requests
import numpy as np

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
# BLOQUE 1: CONFIGURACIÓN Y MOTOR DE DATOS
# =================================================================
st.set_page_config(page_title="CORRAL IA MASTER PRO V51.0", layout="wide", page_icon="🚜")

DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
        # Parches para columnas de versiones previas
        if n == "gastos":
            for col in ["ilos_pienso REAL", "destinado_a TEXT"]:
                try: c.execute(f"ALTER TABLE gastos ADD COLUMN {col}")
                except: pass
        if n == "ventas":
            for col in ["unidades INTEGER", "ilos_finale REAL", "lote_id INTEGER", "cliente TEXT"]:
                try: c.execute(f"ALTER TABLE ventas ADD COLUMN {col}")
                except: pass
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: INTELIGENCIA (CONSUMO, CLIMA Y PREDICCIÓN)
# =================================================================
CONFIG_IA = {"Roja": 0.110, "Blanca": 0.105, "Mochuela": 0.095, "Blanco Engorde": 0.180, "Campero": 0.140}

def get_weather_current(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

def calcular_balance_pro(gastos, lotes, temp_actual):
    total_comprado = gastos['ilos_pienso'].sum() if not gastos.empty and 'ilos_pienso' in gastos.columns else 0
    consumo_total = 0
    c_hoy = 0
    ajuste_realista = 0.85 # Factor de voracidad reducido 15%
    f_clima = 1.15 if temp_actual > 30 else (1.10 if temp_actual < 10 else 1.0)
    
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_str = r["fecha"]
                fmt = "%d/%m/%Y" if "/" in f_str else "%Y-%m-%d"
                f_lote = datetime.strptime(f_str, fmt)
                dias = (datetime.now() - f_lote).days
                base = CONFIG_IA.get(r['raza'], 0.120) * ajuste_realista
                
                for d in range(dias + 1):
                    edad_d = r["edad_inicial"] + d
                    f_edad = 0.3 if edad_d < 20 else (0.6 if edad_d < 45 else 1.0)
                    consumo_total += base * f_edad * r['cantidad'] * f_clima
                c_hoy += base * r['cantidad'] * f_clima
            except: continue
    return max(0, total_comprado - consumo_total), c_hoy

# =================================================================
# BLOQUE 3: INTERFAZ (MENÚ Y NAVEGACIÓN)
# =================================================================
inicializar_db()
lotes, ventas, prod, gastos = cargar_tabla("lotes"), cargar_tabla("ventas"), cargar_tabla("produccion"), cargar_tabla("gastos")

st.sidebar.title("MENÚ PRINCIPAL (V51.0):")
menu = st.sidebar.radio("", ["🏠 Dashboard", "🥚 Producción", "📈 Crecimiento (IA Visual)", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

with st.sidebar.expander("🔑 Configuración APIs"):
    OPENAI_KEY = st.text_input("OpenAI Key", type="password")
    AEMET_KEY = st.text_input("AEMET Key", type="password")

# --- 🏠 DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🚜 Dashboard Maestro")
    t_actual = get_weather_current(AEMET_KEY)
    stock, choy = calcular_balance_pro(gastos, lotes, t_actual)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c2.metric("🍗 Consumo hoy", f"{choy:.1f} kg", delta=f"{t_actual}°C")
    c3.metric("⏳ Autonomía", f"{int(stock/choy) if choy > 0 else 0} d")
    c4.metric("🥚 Hoy", f"{prod[prod['fecha']==datetime.now().strftime('%d/%m/%Y')]['huevos'].sum()} uds")

    if LinearRegression and not gastos.empty and len(gastos[gastos['ilos_pienso']>0]) >= 3:
        try:
            df_p = gastos[gastos['ilos_pienso']>0].copy()
            df_p['f_dt'] = pd.to_datetime(df_p['fecha'], dayfirst=True)
            df_p['dias_rel'] = (df_p['f_dt'] - df_p['f_dt'].min()).dt.days
            reg = LinearRegression().fit(df_p[['dias_rel']], df_p['ilos_pienso'])
            pred = reg.predict(np.array([[df_p['dias_rel'].max() + 7]]))[0]
            st.info(f"🔮 IA Predictiva: Próxima compra estimada en **{abs(pred):.1f} kg**")
        except: pass

# --- 📈 CRECIMIENTO (IA VISUAL + SUBIDA ARCHIVO) ---
elif menu == "📈 Crecimiento (IA Visual)":
    st.title("📈 Crecimiento (IA Visual)")
    df_fotos = cargar_tabla("fotos")
    if lotes.empty: st.warning("Crea un lote primero.")
    else:
        for _, r in lotes.iterrows():
            with st.expander(f"📋 LOTE {r['id']}: {r['raza']} ({r['especie']})", expanded=True):
                col1, col2 = st.columns([2, 1])
                with col1:
                    f_reciente = df_fotos[df_fotos['lote_id'] == r['id']].tail(1)
                    if not f_reciente.empty:
                        st.image(f_reciente.iloc[0]['imagen'], use_column_width=True)
                    
                    st.divider()
                    t_cam, t_file = st.tabs(["🎥 Cámara", "📁 Archivo"])
                    with t_cam: cam = st.camera_input("Capturar", key=f"c_{r['id']}")
                    with t_file: arc = st.file_uploader("Subir", type=['jpg','png','jpeg'], key=f"a_{r['id']}")
                    
                    foto = cam if cam else arc
                    if foto and st.button(f"Guardar Foto Lote {r['id']}", key=f"b_{r['id']}"):
                        get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                           (r['id'], datetime.now().strftime("%d/%m/%Y"), foto.read())).connection.commit(); st.rerun()
                with col2:
                    st.metric("Total Aves", f"{r['cantidad']} uds")
                    st.metric("Días en Corral", (datetime.now() - datetime.strptime(r['fecha'], "%d/%m/%Y" if "/" in r['fecha'] else "%Y-%m-%d")).days + r['edad_inicial'])
                    if OPENAI_KEY and not f_reciente.empty:
                        q = st.text_input("Consultar IA sobre esta foto:", key=f"q_{r['id']}")
                        if q: st.info("Simulación IA: Procesa con OpenAI...")

# --- 🥚 PRODUCCIÓN ---
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Puesta")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos recogidos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()

# --- 💰 VENTAS ---
elif menu == "💰 Ventas":
    st.title("💰 Ventas y Consumo")
    with st.form("v"):
        tipo = st.radio("Tipo", ["Venta", "Consumo Propio"])
        cli = st.text_input("Cliente / Destino")
        l = st.selectbox("Lote Origen", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades", 1); k = st.number_input("Kg Carne", 0.0); p = st.number_input("Total €", 0.0)
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()

# --- 💸 GASTOS ---
elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Infraestructura", "Otros"])
        dest = st.selectbox("Destinado a", ["General", "Gallinas", "Pollos"])
        con = st.text_input("Concepto"); i = st.number_input("Euros €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)",
                               (f.strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

# --- 🐣 ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Alta de Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad inicial (días)", 0); pr = st.number_input("Precio ud €", 0.0)
        f_a = st.date_input("Fecha entrada")
        if st.form_submit_button("Crear Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f_a.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- 🎄 NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    madurez = {"Blanco Engorde": 55, "Campero": 90}
    for rz, dias in madurez.items():
        f_compra = datetime(2026, 12, 20) - timedelta(days=dias)
        st.warning(f"📌 Para {rz}: Comprar lote el **{f_compra.strftime('%d/%m/%Y')}**")

# --- 📜 HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

# --- 💾 COPIAS ---
elif menu == "💾 Copias":
    st.title("💾 Copias y Excel")
    if st.button("Descargar Backup"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            for t in ["lotes", "gastos", "produccion", "ventas"]: cargar_tabla(t).to_excel(w, sheet_name=t, index=False)
        st.download_button("Guardar Excel", out.getvalue(), "Corral_Backup.xlsx")
    sub = st.file_uploader("Restaurar Excel", type="xlsx")
    if sub and st.button("🚀 Restaurar"):
        data = pd.read_excel(sub, sheet_name=None); conn = get_conn()
        for t, df in data.items(): df.to_sql(t, conn, if_exists='replace', index=False)
        conn.commit(); st.success("Datos restaurados."); st.rerun()
