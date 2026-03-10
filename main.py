import streamlit as st
import sqlite3
import pandas as pd
import os
import io
from datetime import datetime
import plotly.express as px

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Tabla de Lotes
    c.execute("""CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
        cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
    # Tabla de Producción Diaria
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    # Tabla de Gastos
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, cantidad REAL)")
    # Tabla de Ventas
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, cantidad REAL)")
    # Tabla de Salud
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT)")
    # Tabla de Bajas
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    # Tabla de Primera Puesta (Hito clave)
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
menu = st.sidebar.selectbox("IR A:", [
    "🏠 Dashboard", 
    "🐣 Alta Animales", 
    "🌟 Registro Primera Puesta", 
    "🥚 Puesta Diaria", 
    "📈 Crecimiento y Madurez", 
    "💸 Gastos", 
    "💰 Ventas", 
    "💉 Salud", 
    "📉 Bajas", 
    "📊 Rentabilidad",
    "💾 SEGURIDAD"
])

# ====================== 3. LÓGICA DE SECCIONES ======================

# --- DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🏠 Dashboard de Control")
    lotes = cargar("lotes")
    bajas = cargar("bajas")
    prod = cargar("produccion")
    gastos = cargar("gastos")
    ventas = cargar("ventas")
    
    total_ani = lotes["cantidad"].sum() if not lotes.empty else 0
    total_bajas = bajas["cantidad"].sum() if not bajas.empty else 0
    aves_vivas = total_ani - total_bajas
    
    beneficio = (ventas["cantidad"].sum() if not ventas.empty else 0) - (gastos["cantidad"].sum() if not gastos.empty else 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aves Vivas", int(aves_vivas))
    c2.metric("Huevos Totales", int(prod["huevos"].sum() if not prod.empty else 0))
    c3.metric("Lotes Activos", len(lotes) if not lotes.empty else 0)
    c4.metric("Beneficio Neto", f"{beneficio:.2f}€")

# --- ALTA ANIMALES ---
elif menu == "🐣 Alta Animales":
    st.title("🐣 Entrada de aves")
    f_llegada = st.date_input("Fecha de llegada")
    especie = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
    
    # Razas dinámicas
    if especie == "Gallinas": razas = ["Blanca", "Roja", "Chocolate"]
    elif especie == "Pollos": razas = ["Blanco Engorde", "Campero"]
    else: razas = ["Codorniz"]
    raza = st.selectbox("Raza", razas)
    
    with st.form("f_alta"):
        c1, c2 = st.columns(2)
        cant = c1.number_input("Cantidad", 1)
        edad = c1.number_input("Edad inicial (días)", 0)
        prec = c2.number_input("Precio ud €", 0.0)
        if st.form_submit_button("✅ Guardar Lote"):
            conn = get_conn()
            conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')",
                         (f_llegada.strftime("%d/%m/%Y"), especie, raza, int(cant), int(edad), prec))
            conn.commit(); conn.close()
            st.success("Lote registrado correctamente"); st.rerun()

# --- REGISTRO PRIMERA PUESTA ---
elif menu == "🌟 Registro Primera Puesta":
    st.title("🌟 Inicio de Producción")
    lotes = cargar("lotes")
    puestas = cargar("primera_puesta")
    if not lotes.empty:
        lotes_sin = lotes[~lotes['id'].isin(puestas['lote_id'])]
        if lotes_sin.empty: st.success("Todos los lotes están en producción.")
        else:
            with st.form("f_p"):
                l_id = st.selectbox("Lote", lotes_sin['id'])
                f_p = st.date_input("Fecha primer huevo")
                if st.form_submit_button("Registrar Hito"):
                    conn = get_conn()
                    conn.execute("INSERT INTO primera_puesta (lote_id, fecha_puesta) VALUES (?,?)", (int(l_id), f_p.strftime("%d/%m/%Y")))
                    conn.commit(); conn.close()
                    st.success("¡Hito guardado!"); st.rerun()
    else: st.warning("No hay lotes.")

# --- PUESTA DIARIA ---
elif menu == "🥚 Puesta Diaria":
    st.title("🥚 Producción Diaria")
    lotes = cargar("lotes")
    if not lotes.empty:
        with st.form("f_puesta"):
            l_id = st.selectbox("ID Lote", lotes['id'])
            f_h = st.date_input("Fecha")
            cant = st.number_input("Huevos recogidos", 1)
            if st.form_submit_button("Anotar Huevos"):
                conn = get_conn()
                conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_h.strftime("%d/%m/%Y"), int(l_id), int(cant)))
                conn.commit(); conn.close()
                st.success("Producción guardada"); st.rerun()

# --- CRECIMIENTO Y MADUREZ ---
elif menu == "📈 Crecimiento y Madurez":
    st.title("📈 Control de Madurez")
    lotes = cargar("lotes")
    puestas = cargar("primera_puesta")
    if not lotes.empty:
        for _, row in lotes.iterrows():
            f_ent = datetime.strptime(row["fecha"], "%d/%m/%Y")
            edad_vida = (datetime.now() - f_ent).days + row["edad_inicial"]
            dato_p = puestas[puestas['lote_id'] == row['id']]
            
            with st.expander(f"Lote {row['id']}: {row['especie']} {row['raza']}"):
                col1, col2 = st.columns(2)
                col1.write(f"🎂 **Edad total:** {edad_vida} días")
                if not dato_p.empty:
                    f_inicio = datetime.strptime(dato_p.iloc[0]['fecha_puesta'], "%d/%m/%Y")
                    dias_prod = (datetime.now() - f_inicio).days
                    col2.write(f"🥚 **Días poniendo:** {dias_prod} días")
                    st.progress(1.0)
                else:
                    meta = 150 if row['especie'] == "Gallinas" else 60
                    porc = min(100, int((edad_vida/meta)*100))
                    col2.write(f"⏳ **Faltan aprox:** {max(0, meta-edad_vida)} días para poner")
                    st.progress(porc/100)
                    st.caption(f"Madurez: {porc}%")

# --- GASTOS / VENTAS / SALUD / BAJAS ---
elif menu in ["💸 Gastos", "💰 Ventas", "💉 Salud", "📉 Bajas"]:
    st.title(f"Registro de {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha")
        if menu in ["💸 Gastos", "💰 Ventas"]:
            con = st.text_input("Concepto"); cant = st.number_input("Importe €", 0.0)
        elif menu == "💉 Salud":
            l = st.number_input("ID Lote", 1); con = st.text_area("Descripción/Tratamiento")
        else: # Bajas
            l = st.number_input("ID Lote", 1); cant = st.number_input("Cantidad", 1); con = st.text_input("Motivo")
            
        if st.form_submit_button("Guardar"):
            conn = get_conn()
            if menu=="💸 Gastos": conn.execute("INSERT INTO gastos (fecha,concepto,cantidad) VALUES (?,?,?)",(f.strftime("%d/%m/%Y"), con, cant))
            elif menu=="💰 Ventas": conn.execute("INSERT INTO ventas (fecha,concepto,cantidad) VALUES (?,?,?)",(f.strftime("%d/%m/%Y"), con, cant))
            elif menu=="💉 Salud": conn.execute("INSERT INTO salud (fecha,lote,descripcion) VALUES (?,?,?)",(f.strftime("%d/%m/%Y"), int(l), con))
            elif menu=="📉 Bajas": conn.execute("INSERT INTO bajas (fecha,lote,cantidad,motivo) VALUES (?,?,?,?)",(f.strftime("%d/%m/%Y"), int(l), int(cant), con))
            conn.commit(); conn.close()
            st.success("Registrado correctamente"); st.rerun()

# --- RENTABILIDAD ---
elif menu == "📊 Rentabilidad":
    st.title("📊 Análisis de Rentabilidad")
    g = cargar("gastos"); v = cargar("ventas")
    if not g.empty or not v.empty:
        df = pd.concat([g.assign(Tipo="Gasto"), v.assign(Tipo="Venta")])
        fig = px.bar(df, x="fecha", y="cantidad", color="Tipo", barmode="group")
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("No hay datos económicos.")

# --- SEGURIDAD ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Gestión de Seguridad")
    st.warning("⚠️ IMPORTANTE: Descarga tu copia antes de cerrar si has hecho muchos cambios.")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 DESCARGAR BASE DE DATOS (.db)", f, "corral_maestro_pro.db")
    
    st.divider()
    subida = st.file_uploader("📤 Restaurar Copia Anterior", type="db")
    if subida:
        with open(DB_PATH, "wb") as f:
            f.write(subida.getbuffer())
        st.success("✅ Datos restaurados. Refresca la página manualmente."); st.balloons()
