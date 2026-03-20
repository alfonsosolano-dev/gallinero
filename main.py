import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.express as px
import google.generativeai as genai
import io

# --- 1. CONFIGURACIÓN Y MOTOR DE DATOS (Fiel a V31.0) ---
st.set_page_config(page_title="CORRAL OMNI V90", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        # Estructura idéntica a tu V31 + mejoras de compatibilidad
        c.execute("CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS bajas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS fotos (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT)")
    conn.commit()

def cargar(t):
    try: return pd.read_sql(f"SELECT * FROM {t}", get_conn())
    except: return pd.DataFrame()

# --- 2. INTELIGENCIA DE RAZAS (Tu CONFIG_IA de V31) ---
CONFIG_IA = {
    "Roja": {"puesta": 0.9, "cons": 0.120, "consejo": "Alta puesta. Ojo con el calcio."},
    "Blanca": {"puesta": 0.85, "cons": 0.115, "consejo": "Vuelan mucho. Vallado alto."},
    "Mochuela": {"puesta": 0.80, "cons": 0.100, "consejo": "Rústica y resistente."},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210, "consejo": "Crecimiento rápido. Ojo patas."},
    "Campero": {"madurez": 90, "cons": 0.150, "consejo": "Sabor top. Necesita campo."}
}

# --- 3. NAVEGACIÓN Y VISTAS ---
inicializar_db()
lotes, gastos, ventas, bajas, produccion = cargar("lotes"), cargar("gastos"), cargar("ventas"), cargar("bajas"), cargar("produccion")

st.sidebar.title("🚜 CORRAL OMNI V90")
menu = st.sidebar.radio("MENÚ", ["🏠 Dashboard", "📈 Crecimiento e IA", "🥚 Producción", "💰 Ventas", "💸 Gastos", "💀 Bajas", "🎄 Navidad", "🐣 Alta Lotes", "💾 Copias/Backup", "📜 Histórico"])

# --- DASHBOARD (KPIs de tu imagen) ---
if menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control Maestro")
    
    # Cálculos para los contadores
    inv = gastos['cantidad'].sum() if not gastos.empty else 0
    caja = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Huevos Totales", int(produccion['huevos'].sum()) if not produccion.empty else 0)
    c2.metric("Caja Real", f"{caja:.2f} €")
    c3.metric("Ahorro Casa", f"{ahorro:.2f} €")
    c4.metric("Inversión", f"{inv:.2f} €")

    st.divider()
    if not produccion.empty:
        st.subheader("📈 Tendencia de Puesta")
        st.line_chart(produccion.tail(15).set_index('fecha')['huevos'])

# --- CRECIMIENTO E IA (Con Cámara de V31) ---
elif menu == "📈 Crecimiento e IA":
    st.title("📈 Control de Lotes y Fotos")
    if lotes.empty: st.warning("No hay lotes registrados.")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']} ({r['especie']})", expanded=True):
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y" if "/" in r["fecha"] else "%Y-%m-%d")
            edad = (datetime.now() - f_lote).days + r["edad_inicial"]
            st.write(f"📅 **Edad:** {edad} días | **Consejo:** {CONFIG_IA.get(r['raza'], {}).get('consejo', 'Seguimiento estándar.')}")
            
            # Cámara y Notas
            col_cam, col_nota = st.columns(2)
            with col_cam:
                img = st.camera_input(f"Capturar Lote {r['id']}", key=f"cam_{r['id']}")
            with col_nota:
                nota = st.text_area("Nota sobre el estado", key=f"nota_{r['id']}")
                if img and st.button(f"Guardar Foto y Nota {r['id']}"):
                    get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)", 
                                       (r['id'], datetime.now().strftime("%d/%m/%Y"), img.read(), nota)).connection.commit()
                    st.success("Registro visual guardado.")

# --- BAJAS (Recuperado) ---
elif menu == "💀 Bajas":
    st.title("💀 Registro de Bajas")
    with st.form("f_b"):
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        cant = st.number_input("Cantidad de bajas", 1)
        mot = st.text_input("Motivo")
        if st.form_submit_button("Registrar Baja"):
            get_conn().execute("INSERT INTO bajas (fecha, lote, cantidad, motivo) VALUES (?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), l, int(cant), mot)).connection.commit(); st.rerun()

# --- VENTAS (Diferenciando Cliente vs Casa) ---
elif menu == "💰 Ventas":
    st.title("💰 Salida de Productos")
    with st.form("f_v"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote de origen", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1)
        k = c2.number_input("Kg (ilos_finale)", 0.0)
        p = c3.number_input("Total €", 0.0)
        cli = st.text_input("Cliente / Destino")
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()

# --- COPIAS Y BACKUP (Fiel a V31) ---
elif menu == "💾 Copias/Backup":
    st.title("💾 Gestión de Datos (Excel)")
    arch = st.file_uploader("Subir Backup Excel para restaurar", type=["xlsx"])
    if arch and st.button("🚀 RESTAURAR BASE DE DATOS"):
        data = pd.read_excel(arch, sheet_name=None)
        conn = get_conn()
        for t, df in data.items():
            if t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
                conn.execute(f"DELETE FROM {t}")
                df.to_sql(t, conn, if_exists='append', index=False)
        conn.commit()
        st.success("Restauración completada."); st.rerun()
    
    # Botón para descargar actual (opcional pero recomendado)
    if st.button("Generar enlace de descarga (Próximamente)"):
        st.info("Función en desarrollo: Usa el Excel que ya tienes como base.")

# --- ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Alta de Lotes")
    with st.form("f_a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices", "Patos/Pavos"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()) + ["Otras"])
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad", 1)
        ed = c2.number_input("Edad inicial (Días)", 0)
        pr = c3.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha de entrada")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- NAVIDAD ---
elif menu == "🎄 Navidad":
    st.title("🎄 Planificador Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    for raza, info in CONFIG_IA.items():
        if "madurez" in info:
            f_compra = f_obj - timedelta(days=info['madurez'])
            st.success(f"📌 **{raza}**: Comprar el **{f_compra.strftime('%d/%m/%Y')}**")

# --- HISTÓRICO Y GASTOS (Resto de funciones) ---
elif menu == "💸 Gastos":
    with st.form("f_g"):
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Medicina", "Otros"])
        imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kg (ilos_pienso)", 0.0)
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, cantidad, ilos_pienso) VALUES (?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cat, imp, kg)).connection.commit(); st.rerun()

elif menu == "🥚 Producción":
    with st.form("f_p"):
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos", 1)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (datetime.now().strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()

elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "fotos"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        id_del = st.number_input("ID a borrar", int(df['id'].min()))
        if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={id_del}").connection.commit(); st.rerun()
