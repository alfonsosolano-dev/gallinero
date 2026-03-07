import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.27.0 - SOLUCIÓN FINAL", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

# --- RECONSTRUCCIÓN ESTRUCTURAL (MIGRACIÓN SEGURA) ---
def reconstruir_tablas():
    # Diccionario con la estructura perfecta que queremos
    estructuras = {
        'lotes': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL DEFAULT 0.0, estado TEXT DEFAULT "Activo"',
        'gastos': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT DEFAULT "General"',
        'ventas': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT DEFAULT "Externa"',
        'produccion': 'id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL'
    }

    for tabla, definicion in estructuras.items():
        # 1. Verificamos si la tabla existe
        c.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{tabla}'")
        if c.fetchone()[0] == 1:
            # 2. Si existe, miramos si tiene todas las columnas
            c.execute(f"PRAGMA table_info({tabla})")
            columnas_actuales = [info[1] for info in c.fetchall()]
            columnas_objetivo = [col.split()[0] for col in definicion.split(', ')]
            
            # Si falta alguna columna, reconstruimos
            if not all(elem in columnas_actuales for elem in columnas_objetivo):
                # Creamos tabla temporal con estructura nueva
                c.execute(f"CREATE TABLE {tabla}_backup ({definicion})")
                # Copiamos solo las columnas que ya existían
                cols_comunes = ", ".join([col for col in columnas_actuales if col in columnas_objetivo])
                if cols_comunes:
                    c.execute(f"INSERT INTO {tabla}_backup ({cols_comunes}) SELECT {cols_comunes} FROM {tabla}")
                # Borramos vieja y renombramos
                c.execute(f"DROP TABLE {tabla}")
                c.execute(f"ALTER TABLE {tabla}_backup RENAME TO {tabla}")
        else:
            # 3. Si no existe, la creamos de cero
            c.execute(f"CREATE TABLE {tabla} ({definicion})")
    
    conn.commit()

reconstruir_tablas()

# --- INTERFAZ ---
st.sidebar.title("🚜 Gestión Corral v27.0")
menu = st.sidebar.radio("IR A:", ["📈 CONTABILIDAD Y ESPECIE", "💰 VENTAS (CLIENTES)", "🥚 PRODUCCIÓN", "💸 GASTOS", "🐣 LOTES", "🛠️ DATOS"])

# --- 1. CONTABILIDAD (POR PESTAÑAS) ---
if menu == "📈 CONTABILIDAD Y ESPECIE":
    st.title("📈 Análisis de Rendimiento Real")
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    df_g = pd.read_sql("SELECT * FROM gastos", conn)
    df_p = pd.read_sql("SELECT * FROM produccion", conn)
    
    t_gen, t_gal, t_pol, t_cod = st.tabs(["🌎 GENERAL", "🐔 GALLINAS", "🍗 POLLOS", "🐦 CODORNICES"])
    
    with t_gen:
        ing = df_v[df_v['tipo_venta'] == 'Externa']['total'].sum() if not df_v.empty else 0
        gas = df_g['importe'].sum() if not df_g.empty else 0
        st.columns(3)[0].metric("BALANCE NETO", f"{round(ing - gas, 2)} €", delta=f"{round(ing, 2)} € Ingresos")
        st.subheader("🛠️ Gastos de Infraestructura")
        st.dataframe(df_g[df_g['especie'] == 'General'], use_container_width=True)

    def pestaña_especie(nombre, color):
        v = df_v[df_v['especie'] == nombre] if not df_v.empty else pd.DataFrame()
        g = df_g[df_g['especie'] == nombre] if not df_g.empty else pd.DataFrame()
        p = df_p[df_p['especie'] == nombre] if not df_p.empty else pd.DataFrame()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingresos", f"{round(v[v['tipo_venta']=='Externa']['total'].sum(), 2) if not v.empty else 0} €")
        c2.metric("Gastos", f"{round(g['importe'].sum(), 2) if not g.empty else 0} €")
        c3.metric("Casa", f"{int(v[v['tipo_venta']=='Consumo Propio']['cantidad'].sum()) if not v.empty else 0} uds")
        
        if not p.empty:
            p['fecha_dt'] = pd.to_datetime(p['fecha'], format='%d/%m/%Y', errors='coerce')
            st.plotly_chart(px.line(p.sort_values('fecha_dt'), x='fecha_dt', y='cantidad', title=f"Producción {nombre}", color_discrete_sequence=[color]), use_container_width=True)

    with t_gal: pestaña_especie("Gallinas", "orange")
    with t_pol: pestaña_especie("Pollos", "red")
    with t_cod: pestaña_especie("Codornices", "blue")

# --- 5. LOTES (FIXED) ---
elif menu == "🐣 LOTES":
    st.title("🐣 Entrada de Animales")
    with st.form("fl"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f_s, f"Compra {can} {esp}", can*pre, "Animales", esp))
            conn.commit(); st.success("Lote guardado.")

# --- SECCIONES RESTANTES ---
elif menu == "💰 VENTAS (CLIENTES)":
    with st.form("fv"):
        f = st.date_input("Fecha"); tipo = st.selectbox("Tipo", ["Externa", "Consumo Propio"]); esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        cli = st.text_input("Cliente", value="Particular" if tipo == "Externa" else "Casa")
        pro = st.text_input("Producto", value="Huevos" if esp != "Pollos" else "Carne")
        can = st.number_input("Cantidad", min_value=1); tot = st.number_input("Total €")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO ventas (fecha, cliente, producto, cantidad, total, especie, tipo_venta) VALUES (?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), cli, pro, can, tot, esp, tipo))
            conn.commit(); st.success("Venta OK")

elif menu == "🥚 PRODUCCIÓN":
    with st.form("fp"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices"]); can = st.number_input("Cantidad")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), esp, can))
            conn.commit(); st.success("OK")

elif menu == "💸 GASTOS":
    with st.form("fg"):
        f = st.date_input("Fecha"); esp = st.selectbox("Asignar a", ["General", "Gallinas", "Pollos", "Codornices"])
        cat = st.selectbox("Cat.", ["Pienso", "Infraestructura", "Otros"]); con = st.text_input("Concepto"); imp = st.number_input("Importe €")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, esp))
            conn.commit(); st.success("OK")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
