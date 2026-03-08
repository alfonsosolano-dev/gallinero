import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime
import plotly.express as px

# ----------------------------
# CONFIG
# ----------------------------

st.set_page_config(page_title="Corral Maestro PRO", layout="wide")

DB_PATH = "data/corral_maestro.db"

# ----------------------------
# CREAR CARPETA DATA
# ----------------------------

if not os.path.exists("data"):
    os.makedirs("data")

# ----------------------------
# CONEXION DB
# ----------------------------

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ----------------------------
# ACTUALIZAR BASE DE DATOS
# ----------------------------

def inicializar_db():

    conn = get_conn()
    c = conn.cursor()

    # TABLA LOTES
    c.execute("""
    CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        especie TEXT,
        raza TEXT,
        tipo_engorde TEXT,
        edad_inicial INTEGER DEFAULT 0,
        cantidad INTEGER,
        precio_ud REAL,
        estado TEXT,
        usuario TEXT
    )
    """)

    # TABLA PUESTA
    c.execute("""
    CREATE TABLE IF NOT EXISTS puesta(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        huevos INTEGER
    )
    """)

    # TABLA GASTOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS gastos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        concepto TEXT,
        cantidad REAL
    )
    """)

    # TABLA VENTAS
    c.execute("""
    CREATE TABLE IF NOT EXISTS ventas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        concepto TEXT,
        cantidad REAL
    )
    """)

    # TABLA SALUD
    c.execute("""
    CREATE TABLE IF NOT EXISTS salud(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        lote INTEGER,
        descripcion TEXT
    )
    """)

    # TABLA PRIMERA PUESTA
    c.execute("""
    CREATE TABLE IF NOT EXISTS primera_puesta(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lote INTEGER,
        fecha TEXT
    )
    """)

    # ---- ACTUALIZAR COLUMNAS SI FALTAN

    columnas = [col[1] for col in c.execute("PRAGMA table_info(lotes)")]

    if "edad_inicial" not in columnas:
        c.execute("ALTER TABLE lotes ADD COLUMN edad_inicial INTEGER DEFAULT 0")

    if "usuario" not in columnas:
        c.execute("ALTER TABLE lotes ADD COLUMN usuario TEXT")

    conn.commit()
    conn.close()


inicializar_db()

# ----------------------------
# LOGIN SIMPLE
# ----------------------------

if "usuario" not in st.session_state:
    st.session_state.usuario = "admin"

# ----------------------------
# MENU
# ----------------------------

menu = st.sidebar.selectbox(
    "MENÚ",
    [
        "Dashboard",
        "Rentabilidad",
        "Crecimiento",
        "Puesta",
        "Gastos",
        "Ventas",
        "Alta Animales",
        "Salud",
        "Navidad",
        "Administración"
    ]
)

conn = get_conn()
c = conn.cursor()

# ----------------------------
# DASHBOARD
# ----------------------------

if menu == "Dashboard":

    st.title("🏠 Dashboard")

    lotes = pd.read_sql("SELECT * FROM lotes", conn)
    huevos = pd.read_sql("SELECT * FROM puesta", conn)
    gastos = pd.read_sql("SELECT * FROM gastos", conn)
    ventas = pd.read_sql("SELECT * FROM ventas", conn)

    col1, col2, col3 = st.columns(3)

    col1.metric("Animales totales", lotes["cantidad"].sum() if not lotes.empty else 0)
    col2.metric("Huevos registrados", huevos["huevos"].sum() if not huevos.empty else 0)
    col3.metric("Beneficio",
                (ventas["cantidad"].sum() if not ventas.empty else 0)
                -
                (gastos["cantidad"].sum() if not gastos.empty else 0)
                )

# ----------------------------
# ALTA ANIMALES
# ----------------------------

if menu == "Alta Animales":

    st.title("🐣 Entrada de Animales")

    fecha = st.date_input("Fecha")
    especie = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])

    if especie == "Gallinas":
        raza = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate"])

    elif especie == "Pollos":
        raza = st.selectbox("Raza", ["Blanco engorde", "Campero"])

    else:
        raza = st.selectbox("Raza", ["Codorniz común"])

    cantidad = st.number_input("Cantidad", 1, 1000)
    edad = st.number_input("Edad inicial (días)", 0, 500)
    precio = st.number_input("Precio por unidad €")

    if st.button("Guardar lote"):

        c.execute(
            """
            INSERT INTO lotes
            (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado, usuario)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                fecha.strftime("%d/%m/%Y"),
                especie,
                raza,
                "N/A",
                edad,
                cantidad,
                precio,
                "Activo",
                st.session_state.usuario
            )
        )

        conn.commit()

        st.success("Lote guardado")

# ----------------------------
# PUESTA
# ----------------------------

if menu == "Puesta":

    st.title("🥚 Registro de Huevos")

    fecha = st.date_input("Fecha")
    huevos = st.number_input("Huevos", 0, 1000)

    if st.button("Guardar puesta"):

        c.execute(
            "INSERT INTO puesta (fecha,huevos) VALUES (?,?)",
            (fecha.strftime("%d/%m/%Y"), huevos)
        )

        conn.commit()

        st.success("Registro guardado")

# ----------------------------
# CRECIMIENTO + PRIMERA PUESTA
# ----------------------------

if menu == "Crecimiento":

    st.title("📈 Crecimiento")

    lotes = pd.read_sql("SELECT * FROM lotes", conn)

    if not lotes.empty:

        lote = st.selectbox("Seleccionar lote", lotes["id"])

        fecha = st.date_input("Primera puesta manual")

        if st.button("Guardar primera puesta"):

            c.execute(
                "INSERT INTO primera_puesta (lote,fecha) VALUES (?,?)",
                (lote, fecha.strftime("%d/%m/%Y"))
            )

            conn.commit()

            st.success("Primera puesta registrada")

# ----------------------------
# RENTABILIDAD
# ----------------------------

if menu == "Rentabilidad":

    st.title("📊 Rentabilidad")

    gastos = pd.read_sql("SELECT * FROM gastos", conn)
    ventas = pd.read_sql("SELECT * FROM ventas", conn)

    if not gastos.empty and not ventas.empty:

        gastos_total = gastos["cantidad"].sum()
        ventas_total = ventas["cantidad"].sum()

        beneficio = ventas_total - gastos_total

        st.metric("Beneficio total", f"{beneficio} €")

# ----------------------------
# GRAFICA BENEFICIOS
# ----------------------------

    df = pd.concat([
        gastos.assign(tipo="gasto"),
        ventas.assign(tipo="venta")
    ])

    if not df.empty:

        graf = px.histogram(df, x="fecha", y="cantidad", color="tipo")

        st.plotly_chart(graf)

# ----------------------------
# SALUD
# ----------------------------

if menu == "Salud":

    st.title("💉 Salud")

    fecha = st.date_input("Fecha")
    lote = st.number_input("Lote")
    desc = st.text_area("Descripción")

    if st.button("Guardar evento salud"):

        c.execute(
            "INSERT INTO salud (fecha,lote,descripcion) VALUES (?,?,?)",
            (fecha.strftime("%d/%m/%Y"), lote, desc)
        )

        conn.commit()

        st.success("Evento registrado")
