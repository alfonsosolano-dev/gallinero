import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. CONEXIÓN Y REPARACIÓN ESTRUCTURAL ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.40", layout="wide")
conn = sqlite3.connect('corral_v40_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_y_reparar():
    # Creamos las tablas si no existen
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, inicio_puesta_real TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, raza TEXT, tipo_venta TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad REAL)''')
    
    # Asegurar que las columnas nuevas existan en datos viejos
    columnas = [('lotes', 'raza'), ('lotes', 'tipo_engorde'), ('lotes', 'inicio_puesta_real'), 
                ('gastos', 'raza'), ('ventas', 'raza'), ('produccion', 'raza')]
    for tabla, col in columnas:
        try: c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} TEXT")
        except: pass
    conn.commit()

inicializar_y_reparar()

# --- 2. FUNCIONES DE CÁLCULO ---
def cargar_datos(tabla):
    df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
    # IMPORTANTE: Rellenar vacíos de versiones anteriores para que aparezcan
    if 'raza' in df.columns: df['raza'] = df['raza'].fillna("General")
    if 'especie' in df.columns: df['especie'] = df['especie'].fillna("Gallinas")
    return df

# --- 3. MENÚ LATERAL ---
menu = st.sidebar.radio("MENÚ PRINCIPAL", [
    "📦 STOCK ACTUAL", "🥚 PRODUCCIÓN Y RAZAS", "🍗 CONTROL DE ENGORDE", 
    "💰 VENTAS", "💸 GASTOS", "🐣 NUEVOS LOTES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN DATOS"
])

# --- 4. PESTAÑA: STOCK ACTUAL ---
if menu == "📦 STOCK ACTUAL":
    st.title("📦 Inventario en Tiempo Real")
    df_l = cargar_datos('lotes')
    df_v = cargar_datos('ventas')
    df_p = cargar_datos('produccion')
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🐥 Animales en Corral")
        # Stock = Entradas (Lotes Activos) - Ventas de Carne
        animales = []
        for raza in df_l[df_l['estado']=='Activo']['raza'].unique():
            ent = df_l[(df_l['raza']==raza) & (df_l['estado']=='Activo')]['cantidad'].sum()
            sal = df_v[(df_v['raza']==raza) & (df_v['producto'].str.contains("Pollo|Carne|Vivo", case=False, na=False))]['cantidad'].sum()
            animales.append({"Raza": raza, "Vivos": int(ent - sal)})
        st.table(pd.DataFrame(animales))

    with col2:
        st.subheader("🥚 Stock de Huevos")
        huevos = []
        for raza in ["Blanca", "Roja", "Chocolate", "General"]:
            prod = df_p[df_p['raza']==raza]['cantidad'].sum()
            vent = df_v[(df_v['raza']==raza) & (df_v['producto'].str.contains("Huevo", case=False, na=False))]['cantidad'].sum()
            huevos.append({"Clase": f"Huevos {raza}", "Stock": int(prod - vent)})
        st.table(pd.DataFrame(huevos))

# --- 5. PESTAÑA: PRODUCCIÓN Y RAZAS ---
elif menu == "🥚 PRODUCCIÓN Y RAZAS":
    st.title("🥚 Producción por Variedad")
    with st.form("p"):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate", "General"])
        can = st.number_input("Cantidad Huevos", min_value=1)
        if st.form_submit_button("Guardar"):
            c.execute("INSERT INTO produccion (fecha, especie, raza, cantidad) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), "Gallinas", rz, can))
            conn.commit(); st.rerun()
    
    df_p = cargar_datos('produccion')
    if not df_p.empty:
        fig = px.bar(df_p.groupby('raza')['cantidad'].sum().reset_index(), x='raza', y='cantidad', color='raza', title="Total Huevos por Raza")
        st.plotly_chart(fig)

# --- 6. PESTAÑA: CONTROL DE ENGORDE ---
elif menu == "🍗 CONTROL DE ENGORDE":
    st.title("🍗 Ciclo de Engorde (Diferenciado)")
    df_l = cargar_datos('lotes')
    df_pollos = df_l[(df_l['especie']=='Pollos') & (df_l['estado']=='Activo')]
    
    for _, row in df_pollos.iterrows():
        f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
        dias = (datetime.now() - f_ent).days
        ciclo = 60 if "Blanco" in (row['tipo_engorde'] or "") else 110
        progreso = min(1.0, dias/ciclo)
        
        st.write(f"**Lote {row['id']}: {row['raza']}** ({row['tipo_engorde']})")
        st.progress(progreso)
        st.write(f"Edad: {dias} días | Falta para sacrificio: {max(0, ciclo-dias)} días")
        st.divider()

# --- 7. PESTAÑA: VENTAS Y GASTOS (CON MEMORIA DE DATOS) ---
elif menu == "💰 VENTAS":
    st.title("💰 Salidas y Ventas")
    df_l = cargar_datos('lotes')
    with st.form("v"):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", df_l['raza'].unique())
        pro = st.text_input("Producto", value="Huevos")
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total €")
        if st.form_submit_button("Registrar"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, tipo_venta) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, can, tot, rz, "Externa"))
            conn.commit(); st.rerun()
    st.dataframe(cargar_datos('ventas').sort_values('id', ascending=False))

elif menu == "💸 GASTOS":
    st.title("💸 Gastos y Pienso")
    df_l = cargar_datos('lotes')
    with st.form("g"):
        f = st.date_input("Fecha")
        rz = st.selectbox("Asignar a Raza", ["General"] + list(df_l['raza'].unique()))
        cat = st.selectbox("Categoría", ["Pienso", "Animales", "Salud", "Infraestructura"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe €")
        if st.form_submit_button("Guardar"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit(); st.rerun()
    st.dataframe(cargar_datos('gastos').sort_values('id', ascending=False))

# --- 8. PESTAÑA: NUEVOS LOTES ---
elif menu == "🐣 NUEVOS LOTES":
    st.title("🐣 Entrada de Aves")
    with st.form("l"):
        f = st.date_input("Fecha Entrada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        rz = st.text_input("Raza (Blanca, Roja, Chocolate, Campero...)")
        tipo = st.selectbox("Tipo Engorde (Solo Pollos)", ["N/A", "Blanco (Rápido)", "Campero (Lento)"])
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud")
        if st.form_submit_button("Dar de Alta"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, tipo, can, pre, 'Activo'))
            conn.commit(); st.rerun()
    st.dataframe(cargar_datos('lotes'))

# --- 9. PLANIFICACIÓN NAVIDAD Y ADMIN ---
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación Campaña Navidad")
    f_nav = datetime(datetime.now().year, 12, 20)
    st.info(f"Objetivo: {f_nav.strftime('%d/%m/%Y')}")
    st.warning(f"Compra CAMPEROS antes de: {(f_nav - timedelta(days=110)).strftime('%d/%m/%Y')}")
    st.success(f"Compra BLANCOS antes de: {(f_nav - timedelta(days=60)).strftime('%d/%m/%Y')}")

elif menu == "🛠️ ADMIN DATOS":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar_datos(t)
    st.dataframe(df)
    id_del = st.number_input("ID a borrar", min_value=0)
    if st.button("Eliminar"):
        c.execute(f"DELETE FROM {t} WHERE id={id_del}")
        conn.commit(); st.rerun()
