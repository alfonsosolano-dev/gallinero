import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import plotly.express as px

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO v4", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Lotes: Datos de origen
    c.execute("""CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
        cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
    # Producción: Registro diario de huevos
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    # Gastos: Pienso, medicinas, etc.
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, cantidad REAL)")
    # Ventas: Ingresos por huevos o animales
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, cantidad REAL)")
    # Salud: Vacunas y tratamientos con recordatorio
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT)")
    # Bajas: Control de mortalidad
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    # Primera Puesta: Hito de inicio de producción
    c.execute("CREATE TABLE IF NOT EXISTS primera_puesta(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER UNIQUE, fecha_puesta TEXT)")
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

inicializar_db()

# ====================== 2. MENÚ LATERAL ======================
st.sidebar.title("🐓 CORRAL PRO")
menu = st.sidebar.selectbox("SECCIÓN:", [
    "🏠 Dashboard Inteligente", 
    "🐣 Alta de Lotes", 
    "🌟 Registro Primera Puesta", 
    "🥚 Puesta Diaria", 
    "📈 Crecimiento y Vejez", 
    "💸 Gastos (Pienso/Otros)", 
    "💰 Ventas", 
    "💉 Salud y Vacunas", 
    "📉 Bajas", 
    "💾 SEGURIDAD"
])

# ====================== 3. LÓGICA DE SECCIONES ======================

# --- DASHBOARD PRO ---
if menu == "🏠 Dashboard Inteligente":
    st.title("🏠 Panel de Control y Rentabilidad")
    lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos"); ventas = cargar("ventas"); bajas = cargar("bajas")
    
    vivas = (lotes["cantidad"].sum() if not lotes.empty else 0) - (bajas["cantidad"].sum() if not bajas.empty else 0)
    t_huevos = prod["huevos"].sum() if not prod.empty else 0
    t_gastos = gastos["cantidad"].sum() if not gastos.empty else 0
    t_ventas = ventas["cantidad"].sum() if not ventas.empty else 0
    beneficio = t_ventas - t_gastos
    coste_huevo = (t_gastos / t_huevos) if t_huevos > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aves en Corral", int(vivas))
    c2.metric("Huevos Totales", int(t_huevos))
    c3.metric("Beneficio Neto", f"{beneficio:.2f}€")
    c4.metric("Coste por Huevo", f"{coste_huevo:.3f}€")

    if not gastos.empty or not ventas.empty:
        df_eco = pd.concat([gastos.assign(Tipo="Gasto"), ventas.assign(Tipo="Venta")])
        st.plotly_chart(px.bar(df_eco, x="fecha", y="cantidad", color="Tipo", barmode="group", title="Balance Económico"), use_container_width=True)

# --- ALTA ANIMALES ---
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Entrada de Aves")
    f_llegada = st.date_input("Fecha de llegada")
    especie = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
    
    # Razas específicas según lo hablado
    if especie == "Gallinas": razas = ["Roja", "Blanca", "Chocolate"]
    elif especie == "Pollos": razas = ["Blanco Engorde", "Campero"]
    else: razas = ["Codorniz"]
    raza = st.selectbox("Raza", razas)
    
    with st.form("f_alta"):
        c1, c2 = st.columns(2)
        cant = c1.number_input("Cantidad", 1)
        edad = c1.number_input("Edad inicial (días)", 0)
        prec = c2.number_input("Precio unidad €", 0.0)
        if st.form_submit_button("✅ GUARDAR NUEVO LOTE"):
            conn = get_conn()
            conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')",
                         (f_llegada.strftime("%d/%m/%Y"), especie, raza, int(cant), int(edad), prec))
            conn.commit(); conn.close()
            st.success("Lote registrado"); st.rerun()

# --- CRECIMIENTO Y VEJEZ (LÓGICA POR RAZA) ---
elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Ciclo de Vida y Alertas de Raza")
    lotes = cargar("lotes"); puestas = cargar("primera_puesta")
    
    # DICCIONARIO MAESTRO DE TIEMPOS
    config = {
        "Roja": {"meta": 140, "vejez": 700, "info": "Ponedora industrial precoz"},
        "Blanca": {"meta": 155, "vejez": 750, "info": "Ponedora eficiente (Leghorn)"},
        "Chocolate": {"meta": 170, "vejez": 800, "info": "Raza rústica persistente"},
        "Blanco Engorde": {"meta": 45, "vejez": 60, "info": "Crecimiento rápido cárnico"},
        "Campero": {"meta": 90, "vejez": 120, "info": "Crecimiento lento calidad"},
        "Codorniz": {"meta": 42, "vejez": 365, "info": "Ciclo rápido"}
    }
    
    if lotes.empty: st.info("No hay lotes.")
    else:
        for _, r in lotes.iterrows():
            f_e = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_e).days + r["edad_inicial"]
            conf = config.get(r["raza"], {"meta": 150, "vejez": 730, "info": "Estándar"})
            
            with st.expander(f"Lote {r['id']}: {r['especie']} {r['raza']}"):
                col1, col2 = st.columns(2)
                col1.write(f"🎂 Edad: **{edad} días**")
                col1.caption(f"ℹ️ {conf['info']}")
                
                # Alertas
                if edad > conf["vejez"]:
                    col2.error(f"⚠️ VEJEZ/SACRIFICIO: Superados los {conf['vejez']} días.")
                elif edad >= conf["meta"]:
                    col2.success(f"✅ FASE PRODUCTIVA (Meta: {conf['meta']} días)")
                
                prog = min(100, int((edad / conf["meta"]) * 100))
                st.progress(prog/100)
                st.write(f"Desarrollo: **{prog}%**")

# --- SEGURIDAD ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Gestión de Datos (Backup)")
    st.info("Para evitar pérdida de datos en Streamlit Cloud, descarga tu copia .db tras cada sesión.")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 DESCARGAR COPIA ACTUAL", f, "corral_maestro_pro.db")
    
    st.divider()
    subida = st.file_uploader("📤 RESTAURAR COPIA", type="db")
    if subida:
        with open(DB_PATH, "wb") as f: f.write(subida.getbuffer())
        st.success("✅ Datos restaurados. Refresca la página."); st.rerun()

# --- RESTO DE REGISTROS ---
else:
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha")
        if "Primera Puesta" in menu:
            l = st.number_input("ID Lote", 1); cant = 0; con = "Primera Puesta"
        elif "Puesta Diaria" in menu:
            l = st.number_input("ID Lote", 1); cant = st.number_input("Huevos", 1); con = "Puesta"
        elif "Gastos" in menu or "Ventas" in menu:
            con = st.text_input("Concepto (Ej: Saco Pienso)"); cant = st.number_input("Euros", 0.0)
        elif "Salud" in menu:
            l = st.number_input("ID Lote", 1); con = st.text_area("Tratamiento"); f_prox = st.date_input("Próxima dosis")
        else: # Bajas
            l = st.number_input("ID Lote", 1); cant = st.number_input("Cantidad", 1); con = st.text_input("Motivo")
            
        if st.form_submit_button("💾 GUARDAR"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Primera Puesta" in menu:
                conn.execute("INSERT OR REPLACE INTO primera_puesta (lote_id, fecha_puesta) VALUES (?,?)", (int(l), f_s))
            elif "Puesta Diaria" in menu:
                conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l), int(cant)))
            elif "Gastos" in menu:
                conn.execute("INSERT INTO gastos (fecha, concepto, cantidad) VALUES (?,?,?)", (f_s, con, cant))
            elif "Ventas" in menu:
                conn.execute("INSERT INTO ventas (fecha, concepto, cantidad) VALUES (?,?,?)", (f_s, con, cant))
            elif "Salud" in menu:
                conn.execute("INSERT INTO salud (fecha, lote, descripcion, proxima_fecha) VALUES (?,?,?,?)", (f_s, int(l), con, f_prox.strftime("%d/%m/%Y")))
            elif "Bajas" in menu:
                conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo) VALUES (?,?,?,?)", (f_s, int(l), int(cant), con))
            conn.commit(); conn.close(); st.success("Registrado"); st.rerun()
