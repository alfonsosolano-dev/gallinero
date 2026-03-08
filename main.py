import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. NÚCLEO Y REPARACIÓN DE DATOS ---
st.set_page_config(page_title="CORRAL PRO V.42.1", layout="wide")
conn = sqlite3.connect('corral_v42_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_v42():
    # Estructura completa de tablas
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL)''')
    
    # Inserción del gasto de Material (21 Feb - 100€) si no existe
    c.execute("SELECT COUNT(*) FROM gastos WHERE concepto LIKE '%Material%'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                  ('21/02/2026', 'Compra Material y Equipamiento', 100.0, 'Infraestructura', 'General'))
    conn.commit()

inicializar_v42()

# --- 2. MOTOR DE CÁLCULO ---
def cargar(tabla):
    df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
    if 'raza' in df.columns: df['raza'] = df['raza'].fillna("General")
    return df

def info_biologica(f_ent_str, edad_ini, tipo_e, esp):
    f_ent = datetime.strptime(f_ent_str, '%d/%m/%Y')
    dias_en_casa = (datetime.now() - f_ent).days
    edad_total = dias_en_casa + int(edad_ini or 0)
    # Metas: Blanco (60), Campero (110), Puesta (140)
    meta = 60 if "Blanco" in (tipo_e or "") else (110 if esp == 'Pollos' else 140)
    return edad_total, meta, min(1.0, edad_total/meta)

# --- 3. INTERFAZ ---
menu = st.sidebar.radio("PANEL DE CONTROL", ["📊 ESTADO Y RENTABILIDAD", "🍗 CRECIMIENTO", "🥚 PUESTA", "🐣 ALTA AVES", "💸 GASTOS/VENTAS", "🛠️ ADMIN"])

# --- 4. RENTABILIDAD Y STOCK ---
if menu == "📊 ESTADO Y RENTABILIDAD":
    st.title("📊 Resumen Económico y Stock")
    df_g = cargar('gastos'); df_v = cargar('ventas'); df_l = cargar('lotes')
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Inversión (Material + Aves)", f"{df_g['importe'].sum()} €")
    m2.metric("Ventas Acumuladas", f"{df_v['total'].sum()} €")
    m3.metric("Balance Neto", f"{df_v['total'].sum() - df_g['importe'].sum()} €", delta_color="normal")

    st.divider()
    col_izq, col_der = st.columns(2)
    with col_izq:
        st.subheader("🐥 Aves en el Corral")
        st.table(df_l[df_l['estado']=='Activo'].groupby('raza')['cantidad'].sum())
    with col_der:
        st.subheader("💰 Gastos por Categoría")
        fig_g = px.pie(df_g, values='importe', names='categoria', hole=.3)
        st.plotly_chart(fig_g, use_container_width=True)

# --- 5. CRECIMIENTO (CON EL LOTE DEL 21 FEB) ---
elif menu == "🍗 CRECIMIENTO":
    st.title("📈 Control de Edad y Madurez")
    df_l = cargar('lotes')
    for _, row in df_l[df_l['estado']=='Activo'].iterrows():
        edad, meta, prog = info_biologica(row['fecha'], row['edad_inicial'], row['tipo_engorde'], row['especie'])
        with st.expander(f"Lote {row['id']}: {row['raza']} - {edad} días de vida", expanded=True):
            st.progress(prog)
            if edad >= meta: st.error("🎯 OBJETIVO ALCANZADO")
            else: st.info(f"Faltan {meta-edad} días para el objetivo ({meta} días).")

# --- 6. ALTA DE AVES (PARA TU REGISTRO DEL 21 FEB) ---
elif menu == "🐣 ALTA AVES":
    st.title("🐣 Registro de Lotes")
    st.info("Nota: Para los animales comprados el 21 de febrero, usa esa fecha y pon 15 en 'Edad al comprar'.")
    with st.form("nuevo_lote"):
        f = st.date_input("Fecha de adquisición")
        esp = st.selectbox("Especie", ["Pollos", "Gallinas"])
        rz = st.text_input("Raza (Blanca, Roja, Campero, Chocolate...)")
        tipo = st.selectbox("Tipo Engorde (Solo Pollos)", ["N/A", "Blanco (Rápido)", "Campero (Lento)"])
        e_ini = st.number_input("Edad al comprar (días)", value=15)
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud €")
        if st.form_submit_button("✅ REGISTRAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)",
                      (f_s, esp, rz, tipo, e_ini, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                      (f_s, f"Compra {can} {rz}", can*pre, "Animales", rz))
            conn.commit(); st.success("Lote registrado"); st.rerun()

# --- 7. PUESTA (CHOCOLATE READY) ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Producción de Huevos")
    with st.form("f_puesta"):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate", "General"])
        can = st.number_input("Cantidad", min_value=1)
        if st.form_submit_button("Anotar"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), rz, can))
            conn.commit(); st.rerun()
    
    df_p = cargar('produccion')
    if not df_p.empty:
        # Colores personalizados: Chocolate = Marrón
        color_map = {"Chocolate": "#5D4037", "Roja": "#C62828", "Blanca": "#F5F5F5", "General": "#FFA000"}
        fig_p = px.bar(df_p, x='fecha', y='cantidad', color='raza', color_discrete_map=color_map, title="Evolución de Puesta")
        st.plotly_chart(fig_p)

# (VENTAS y ADMIN mantienen la estructura de gestión de tablas)
