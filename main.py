import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- 1. CONEXIÓN Y REPARACIÓN ---
conn = sqlite3.connect('corral_v38_final.db', check_same_thread=False)
c = conn.cursor()

def asegurar_columnas():
    tablas = {
        'lotes': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT',
        'gastos': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, raza TEXT',
        'ventas': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, raza TEXT, tipo_venta TEXT',
        'produccion': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad REAL'
    }
    for tabla, cols in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {tabla} ({cols})")
        # Forzar columna raza en todas
        try: c.execute(f"ALTER TABLE {tabla} ADD COLUMN raza TEXT")
        except: pass
    conn.commit()

asegurar_columnas()

# --- 2. NAVEGACIÓN ---
st.sidebar.title("🍀 CORRAL V.39.2")
menu = st.sidebar.radio("IR A:", ["💸 GASTOS", "💰 VENTAS", "📊 RENTABILIDAD", "🐣 LOTES", "🛠️ DATOS"])

# --- 3. PESTAÑA GASTOS (CORREGIDA) ---
if menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    
    # Formulario
    df_l = pd.read_sql("SELECT DISTINCT raza FROM lotes", conn)
    lista_razas = ["General"] + df_l['raza'].dropna().tolist()
    
    with st.form("nuevo_gasto"):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        rz = col2.selectbox("Asignar a Raza", lista_razas)
        cat = st.selectbox("Categoría", ["Pienso", "Animales", "Salud", "Limpieza", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0, step=0.1)
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit()
            st.success("Gasto guardado")
            st.rerun()

    st.divider()
    st.subheader("Histórico de Gastos")
    df_g = pd.read_sql("SELECT * FROM gastos ORDER BY id DESC", conn)
    if not df_g.empty:
        df_g['raza'] = df_g['raza'].fillna("Sin Asignar") # Rellena huecos antiguos
        st.dataframe(df_g, use_container_width=True)
    else:
        st.info("No hay gastos registrados aún.")

# --- 4. PESTAÑA VENTAS (CORREGIDA) ---
elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    
    df_l = pd.read_sql("SELECT DISTINCT raza FROM lotes", conn)
    lista_razas_v = df_l['raza'].dropna().tolist()
    
    with st.form("nueva_venta"):
        f_v = st.date_input("Fecha")
        rz_v = st.selectbox("Raza del Producto", lista_razas_v if lista_razas_v else ["Blanca", "Roja"])
        pro = st.text_input("Producto (Huevos, Pollo, etc.)")
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total (€)", min_value=0.0)
        if st.form_submit_button("✅ REGISTRAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, tipo_venta) VALUES (?,?,?,?,?,?)",
                      (f_v.strftime('%d/%m/%Y'), pro, can, tot, rz_v, "Externa"))
            conn.commit()
            st.rerun()

    st.divider()
    df_v = pd.read_sql("SELECT * FROM ventas ORDER BY id DESC", conn)
    if not df_v.empty:
        df_v['raza'] = df_v['raza'].fillna("Sin Asignar")
        st.dataframe(df_v, use_container_width=True)

# --- 5. LOTES (PARA QUE HAYA RAZAS) ---
elif menu == "🐣 LOTES":
    st.title("🐣 Lotes Activos")
    with st.form("l"):
        f = st.date_input("Entrada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        raza = st.text_input("Raza (Ej: Blanca, Roja, Campero)")
        can = st.number_input("Cantidad", min_value=1)
        if st.form_submit_button("Añadir"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), esp, raza, can, 'Activo'))
            conn.commit()
            st.rerun()
    st.dataframe(pd.read_sql("SELECT * FROM lotes", conn))

# --- 6. DATOS (BORRADO) ---
elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["gastos", "ventas", "lotes", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t}", conn)
    st.write(f"Datos en {t}:")
    st.dataframe(df)
    id_borrar = st.number_input("ID a eliminar", min_value=0)
    if st.button("Eliminar"):
        c.execute(f"DELETE FROM {t} WHERE id={id_borrar}")
        conn.commit()
        st.rerun()
