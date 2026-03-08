import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import plotly.express as px

# ====================== CONFIGURACIÓN DE PÁGINA ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide")

# ====================== BASE DE DATOS ======================
DB_PATH = "data/corral_maestro_pro.db"

if not os.path.exists("data"):
    os.makedirs("data")

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Lotes
    c.execute("""
    CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        especie TEXT,
        raza TEXT,
        cantidad INTEGER,
        edad_inicial INTEGER,
        precio_ud REAL,
        estado TEXT
    )
    """)
    # Producción huevos
    c.execute("""
    CREATE TABLE IF NOT EXISTS produccion(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        lote INTEGER,
        huevos INTEGER
    )
    """)
    # Gastos
    c.execute("""
    CREATE TABLE IF NOT EXISTS gastos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        concepto TEXT,
        cantidad REAL
    )
    """)
    # Ventas
    c.execute("""
    CREATE TABLE IF NOT EXISTS ventas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        concepto TEXT,
        cantidad REAL
    )
    """)
    # Salud
    c.execute("""
    CREATE TABLE IF NOT EXISTS salud(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        lote INTEGER,
        descripcion TEXT
    )
    """)
    # Bajas
    c.execute("""
    CREATE TABLE IF NOT EXISTS bajas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        lote INTEGER,
        cantidad INTEGER,
        motivo TEXT
    )
    """)
    # Primera puesta
    c.execute("""
    CREATE TABLE IF NOT EXISTS primera_puesta(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lote INTEGER,
        fecha TEXT
    )
    """)
    conn.commit()
    conn.close()

inicializar_db()

# ====================== FUNCIONES AUXILIARES ======================
def cargar(tabla):
    conn = get_conn()
    try:
        return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def registrar_lote(fecha, especie, raza, cantidad, edad, precio):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    INSERT INTO lotes (fecha,especie,raza,cantidad,edad_inicial,precio_ud,estado)
    VALUES (?,?,?,?,?,?,?)""",
    (fecha, especie, raza, cantidad, edad, precio, "Activo"))
    conn.commit()
    conn.close()

def registrar_produccion(fecha, lote, huevos):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO produccion (fecha,lote,huevos) VALUES (?,?,?)",(fecha,lote,huevos))
    conn.commit()
    conn.close()

def registrar_gasto(fecha, concepto, cantidad):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO gastos (fecha,concepto,cantidad) VALUES (?,?,?)",(fecha,concepto,cantidad))
    conn.commit()
    conn.close()

def registrar_venta(fecha, concepto, cantidad):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO ventas (fecha,concepto,cantidad) VALUES (?,?,?)",(fecha,concepto,cantidad))
    conn.commit()
    conn.close()

def registrar_baja(fecha, lote, cantidad, motivo):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO bajas (fecha,lote,cantidad,motivo) VALUES (?,?,?,?)",(fecha,lote,cantidad,motivo))
    conn.commit()
    conn.close()

def registrar_salud(fecha, lote, descripcion):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO salud (fecha,lote,descripcion) VALUES (?,?,?)",(fecha,lote,descripcion))
    conn.commit()
    conn.close()

def primera_puesta(lote, fecha):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO primera_puesta (lote,fecha) VALUES (?,?)",(lote,fecha))
    conn.commit()
    conn.close()

# ====================== MENÚ LATERAL ======================
st.sidebar.title("🐓 CORRAL MAESTRO PRO")
menu = st.sidebar.selectbox("MENÚ",[
    "Dashboard",
    "Alta Animales",
    "Puesta",
    "Crecimiento",
    "Gastos",
    "Ventas",
    "Salud",
    "Bajas",
    "Rentabilidad"
])

# ====================== DASHBOARD ======================
if menu=="Dashboard":
    st.title("🏠 Dashboard")
    lotes = cargar("lotes")
    produccion = cargar("produccion")
    gastos = cargar("gastos")
    ventas = cargar("ventas")
    bajas = cargar("bajas")

    total_animales = lotes["cantidad"].sum() if not lotes.empty else 0
    total_huevos = produccion["huevos"].sum() if not produccion.empty else 0
    total_gasto = gastos["cantidad"].sum() if not gastos.empty else 0
    total_venta = ventas["cantidad"].sum() if not ventas.empty else 0
    beneficio = total_venta - total_gasto

    col1,col2,col3,col4,col5 = st.columns(5)
    col1.metric("Animales", total_animales)
    col2.metric("Huevos", total_huevos)
    col3.metric("Ventas €", total_venta)
    col4.metric("Gastos €", total_gasto)
    col5.metric("Beneficio €", beneficio)

# ====================== ALTA DE ANIMALES ======================
elif menu=="Alta Animales":
    st.title("🐣 Entrada de animales")
    fecha = st.date_input("Fecha")
    especie = st.selectbox("Especie", ["Gallinas","Pollos","Codornices"])
    if especie=="Gallinas":
        raza = st.selectbox("Raza", ["Blanca","Roja","Chocolate"])
    elif especie=="Pollos":
        raza = st.selectbox("Raza", ["Blanco Engorde","Campero"])
    else:
        raza = st.selectbox("Raza", ["Codornices"])
    cantidad = st.number_input("Cantidad",1,1000)
    edad = st.number_input("Edad inicial días",0,500)
    precio = st.number_input("Precio unidad €")
    if st.button("Guardar lote"):
        registrar_lote(fecha.strftime("%d/%m/%Y"),especie,raza,cantidad,edad,precio)
        st.success("✅ Lote guardado correctamente")

# ====================== PUESTA ======================
elif menu=="Puesta":
    st.title("🥚 Registro de huevos")
    lotes = cargar("lotes")
    if not lotes.empty:
        lote = st.selectbox("Lote", lotes["id"])
        fecha = st.date_input("Fecha")
        huevos = st.number_input("Huevos",0,1000)
        if st.button("Guardar producción"):
            registrar_produccion(fecha.strftime("%d/%m/%Y"), lote, huevos)
            st.success("✅ Producción guardada correctamente")
    else:
        st.info("No hay lotes disponibles para registrar producción.")

# ====================== CRECIMIENTO ======================
elif menu=="Crecimiento":
    st.title("📈 Crecimiento / Madurez")
    lotes = cargar("lotes")
    if not lotes.empty:
        for _, row in lotes.iterrows():
            fecha_ent = datetime.strptime(row["fecha"], "%d/%m/%Y")
            edad_actual = (datetime.now() - fecha_ent).days + row["edad_inicial"]
            meta = 140 if row["especie"]=="Gallinas" else 95 if "Campero" in row["raza"] else 60
            prog = min(1.0, edad_actual/meta)
            with st.expander(f"{row['especie']} {row['raza']} - {edad_actual} días"):
                st.progress(prog)
                if prog>=0.8:
                    st.warning("⚠️ Reposición próxima")

# ====================== GASTOS ======================
elif menu=="Gastos":
    st.title("💸 Registrar gasto")
    fecha = st.date_input("Fecha")
    concepto = st.text_input("Concepto")
    cantidad = st.number_input("Importe €",0.0)
    if st.button("Guardar gasto"):
        registrar_gasto(fecha.strftime("%d/%m/%Y"), concepto, cantidad)
        st.success("✅ Gasto guardado correctamente")

# ====================== VENTAS ======================
elif menu=="Ventas":
    st.title("💰 Registrar venta")
    fecha = st.date_input("Fecha")
    concepto = st.text_input("Concepto venta")
    cantidad = st.number_input("Ingreso €",0.0)
    if st.button("Guardar venta"):
        registrar_venta(fecha.strftime("%d/%m/%Y"), concepto, cantidad)
        st.success("✅ Venta guardada correctamente")

# ====================== SALUD ======================
elif menu=="Salud":
    st.title("💉 Evento sanitario")
    lotes = cargar("lotes")
    if not lotes.empty:
        lote = st.selectbox("Lote", lotes["id"])
        fecha = st.date_input("Fecha")
        descripcion = st.text_area("Descripción")
        if st.button("Guardar evento"):
            registrar_salud(fecha.strftime("%d/%m/%Y"), lote, descripcion)
            st.success("✅ Evento sanitario guardado")
    else:
        st.info("No hay lotes disponibles")

# ====================== BAJAS ======================
elif menu=="Bajas":
    st.title("📉 Registrar bajas")
    lotes = cargar("lotes")
    if not lotes.empty:
        lote = st.selectbox("Lote", lotes["id"])
        fecha = st.date_input("Fecha")
        cantidad = st.number_input("Cantidad",1)
        motivo = st.text_input("Motivo")
        if st.button("Registrar baja"):
            registrar_baja(fecha.strftime("%d/%m/%Y"), lote, cantidad, motivo)
            st.success("✅ Baja registrada")
    else:
        st.info("No hay lotes disponibles")

# ====================== RENTABILIDAD ======================
elif menu=="Rentabilidad":
    st.title("📊 Rentabilidad")
    gastos = cargar("gastos")
    ventas = cargar("ventas")
    beneficio = (ventas["cantidad"].sum() if not ventas.empty else 0) - (gastos["cantidad"].sum() if not gastos.empty else 0)
    st.metric("Beneficio total €", beneficio)
    df = pd.concat([gastos.assign(tipo="Gasto"), ventas.assign(tipo="Venta")])
    if not df.empty:
        fig = px.bar(df,x="fecha",y="cantidad",color="tipo")
        st.plotly_chart(fig)
