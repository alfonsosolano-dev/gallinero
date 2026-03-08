import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.46", layout="wide")
conn = sqlite3.connect('corral_v46_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_v46():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    
    # Inserción automática del gasto de material 21 Feb si no existe
    c.execute("SELECT COUNT(*) FROM gastos WHERE concepto LIKE '%Material%'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                  ('21/02/2026', 'Compra Material Inicial', 100.0, 'Infraestructura', 'General'))
    conn.commit()

inicializar_v46()

def cargar(tabla):
    try:
        df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
        return df
    except: return pd.DataFrame()

# --- MENÚ ---
menu = st.sidebar.radio("MENÚ", ["📊 RENTABILIDAD", "🍗 CRECIMIENTO", "💸 GASTOS", "💰 VENTAS", "🥚 PUESTA", "🐣 ALTA ANIMALES", "🛠️ ADMIN"])

# --- SECCIÓN: GASTOS (DESBLOQUEADA) ---
if menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    df_l = cargar('lotes')
    # Si no hay lotes, permitimos "General" o escribir la raza
    opciones_rz = ["General"] + (df_l['raza'].unique().tolist() if not df_l.empty else [])
    
    with st.form("f_gasto", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        cat = col2.selectbox("Categoría", ["Pienso Pollos", "Pienso Gallinas", "Pienso Codornices", "Infraestructura", "Animales", "Salud"])
        rz = st.selectbox("Asignar a Raza:", opciones_rz)
        con = st.text_input("Concepto (Ej: Saco 25kg)")
        imp = st.number_input("Importe (€)", min_value=0.0, step=0.01)
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit(); st.rerun()
    st.subheader("Historial de Gastos")
    st.dataframe(cargar('gastos'), use_container_width=True)

# --- SECCIÓN: PUESTA (DESBLOQUEADA) ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Diario de Puesta")
    with st.form("f_puesta", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        rz = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate", "Azules", "Codorniz"])
        can = st.number_input("Cantidad de Huevos", min_value=1)
        if st.form_submit_button("✅ ANOTAR"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); st.rerun()
    st.subheader("Historial de Producción")
    df_p = cargar('produccion')
    if not df_p.empty:
        cmap = {"Chocolate": "#5D4037", "Roja": "#C62828", "Blanca": "#F5F5F5", "Azules": "#81D4FA", "Codorniz": "#BDBDBD"}
        st.plotly_chart(px.bar(df_p, x='fecha', y='cantidad', color='raza', color_discrete_map=cmap))

# --- SECCIÓN: ALTA ANIMALES (SIEMPRE ABIERTA) ---
elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Registro de Nuevos Lotes")
    with st.form("f_lote"):
        f = st.date_input("Fecha adquisición")
        esp = st.selectbox("Especie", ["Pollos", "Gallinas", "Codornices"])
        rz_sel = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate", "Campero", "Codorniz Japónica", "OTRA"])
        rz_nueva = st.text_input("Si elegiste 'OTRA', escribe el nombre:")
        raza_f = rz_nueva if rz_sel == "OTRA" else rz_sel
        tipo = st.selectbox("Tipo/Uso", ["N/A", "Engorde Rápido", "Engorde Lento", "Puesta"])
        e_ini = st.number_input("Edad al comprar (días)", value=15)
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud €")
        if st.form_submit_button("✅ DAR DE ALTA"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", 
                      (f_s, esp, raza_f, tipo, e_ini, can, pre, 'Activo'))
            # Auto-gasto de compra
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                      (f_s, f"Compra {can} {raza_f}", can*pre, "Animales", raza_f))
            conn.commit(); st.rerun()
    st.dataframe(cargar('lotes'))

# --- SECCIÓN: RENTABILIDAD (CON COSTE POR POLLO/AVE) ---
elif menu == "📊 RENTABILIDAD":
    st.title("💰 Rentabilidad y Coste por Animal")
    df_l = cargar('lotes'); df_g = cargar('gastos')
    if not df_l.empty:
        datos_coste = []
        for _, lote in df_l[df_l['estado']=='Activo'].iterrows():
            c_compra = lote['cantidad'] * lote['precio_ud']
            c_pienso = df_g[(df_g['raza'] == lote['raza']) & (df_g['categoria'].str.contains('Pienso'))]['importe'].sum()
            total = c_compra + c_pienso
            coste_ud = total / lote['cantidad']
            datos_coste.append({"Lote": f"{lote['especie']} {lote['raza']}", "Inversión": f"{total:.2f}€", "Coste por Animal": f"{coste_ud:.2f}€"})
        st.table(pd.DataFrame(datos_coste))
    else: st.info("Registra un lote para ver los costes.")

# --- SECCIONES: CRECIMIENTO, VENTAS, ADMIN (RESTAURADAS) ---
elif menu == "💰 VENTAS":
    st.title("💰 Salidas")
    with st.form("v"):
        f = st.date_input("Fecha")
        pro = st.selectbox("Producto", ["Huevos", "Pollo Vivo", "Canal/Carne"])
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total Cobrado €")
        if st.form_submit_button("Guardar"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, can, tot, "General"))
            conn.commit(); st.rerun()
    st.dataframe(cargar('ventas'))

elif menu == "🛠️ ADMIN":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(t)
    st.dataframe(df)
    id_d = st.number_input("ID a borrar", min_value=0)
    if st.button("BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id=?", (id_d,))
        conn.commit(); st.rerun()
