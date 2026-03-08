import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.43", layout="wide")
conn = sqlite3.connect('corral_v43_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_sistema():
    # Creación de todas las tablas necesarias
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
                  tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, 
                  edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, 
                  importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, 
                  cantidad INTEGER, total REAL, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL)''')
    
    # Gasto automático del material de febrero (100€)
    c.execute("SELECT COUNT(*) FROM gastos WHERE concepto LIKE '%Material%'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                  ('21/02/2026', 'Compra Material y Equipamiento Inicial', 100.0, 'Infraestructura', 'General'))
    conn.commit()

inicializar_sistema()

# --- 2. FUNCIONES DE CARGA Y CÁLCULO ---
def cargar_tabla(tabla):
    try:
        df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
        if 'raza' in df.columns: df['raza'] = df['raza'].fillna("General")
        return df
    except: return pd.DataFrame()

def calcular_madurez(f_ent_str, edad_ini, tipo_e, esp):
    f_ent = datetime.strptime(f_ent_str, '%d/%m/%Y')
    dias_corral = (datetime.now() - f_ent).days
    edad_total = dias_corral + int(edad_ini or 0)
    # Metas: Blanco (60d), Campero (110d), Gallina Puesta (140d)
    meta = 60 if "Blanco" in (tipo_e or "") else (110 if esp == "Pollos" else 140)
    return edad_total, meta, min(1.0, edad_total/meta)

# --- 3. MENÚ LATERAL ---
menu = st.sidebar.radio("MENÚ PRINCIPAL", 
    ["📊 RESUMEN GENERAL", "🍗 CONTROL CRECIMIENTO", "🥚 PRODUCCIÓN HUEVOS", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🛠️ ADMIN DATOS"])

# --- 4. SECCIÓN: RESUMEN GENERAL ---
if menu == "📊 RESUMEN GENERAL":
    st.title("📊 Resumen del Corral")
    df_g = cargar_tabla('gastos'); df_v = cargar_tabla('ventas')
    col1, col2, col3 = st.columns(3)
    col1.metric("Inversión Total", f"{df_g['importe'].sum()} €")
    col2.metric("Ventas Totales", f"{df_v['total'].sum()} €")
    col3.metric("Balance", f"{df_v['total'].sum() - df_g['importe'].sum()} €")
    
    st.divider()
    st.subheader("Gráfico de Gastos por Categoría")
    if not df_g.empty:
        st.plotly_chart(px.pie(df_g, values='importe', names='categoria', hole=0.3))

# --- 5. SECCIÓN: CONTROL CRECIMIENTO (EDAD REAL) ---
elif menu == "🍗 CONTROL CRECIMIENTO":
    st.title("📈 Madurez de los Lotes")
    df_l = cargar_tabla('lotes')
    activos = df_l[df_l['estado'] == 'Activo']
    if not activos.empty:
        for _, row in activos.iterrows():
            edad, meta, prog = calcular_madurez(row['fecha'], row['edad_inicial'], row['tipo_engorde'], row['especie'])
            with st.expander(f"Lote {row['id']}: {row['raza']} - {edad} días", expanded=True):
                st.write(f"Meta: {meta} días | Faltan: {max(0, meta-edad)} días")
                st.progress(prog)
                if edad >= meta: st.error("🎯 OBJETIVO ALCANZADO")
    else: st.info("No hay lotes activos.")

# --- 6. SECCIÓN: PRODUCCIÓN HUEVOS (CHOCOLATE INCLUIDO) ---
elif menu == "🥚 PRODUCCIÓN HUEVOS":
    st.title("🥚 Diario de Puesta")
    with st.form("f_prod", clear_on_submit=True):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate", "General"])
        can = st.number_input("Cantidad de Huevos", min_value=1)
        if st.form_submit_button("✅ ANOTAR PUESTA"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), rz, can))
            conn.commit(); st.rerun()
    
    df_p = cargar_tabla('produccion')
    if not df_p.empty:
        cmap = {"Chocolate": "#5D4037", "Roja": "#C62828", "Blanca": "#F5F5F5", "General": "#FFA000"}
        st.plotly_chart(px.bar(df_p, x='fecha', y='cantidad', color='raza', color_discrete_map=cmap, title="Producción por Raza"))

# --- 7. SECCIÓN: GASTOS ---
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    with st.form("f_gasto", clear_on_submit=True):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Infraestructura", "Animales", "Salud", "Otros"])
        df_l = cargar_tabla('lotes')
        rz = st.selectbox("Asignar a Raza", ["General"] + (df_l['raza'].unique().tolist() if not df_l.empty else []))
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit(); st.rerun()
    st.subheader("Historial de Gastos")
    st.dataframe(cargar_tabla('gastos'), use_container_width=True)

# --- 8. SECCIÓN: VENTAS ---
elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    with st.form("f_venta", clear_on_submit=True):
        f = st.date_input("Fecha")
        pro = st.selectbox("Producto", ["Huevos", "Pollo Vivo", "Canal/Carne"])
        df_l = cargar_tabla('lotes')
        rz = st.selectbox("Raza", ["General"] + (df_l['raza'].unique().tolist() if not df_l.empty else []))
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total Cobrado (€)")
        if st.form_submit_button("✅ GUARDAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, can, tot, rz))
            conn.commit(); st.rerun()
    st.subheader("Historial de Ventas")
    st.dataframe(cargar_tabla('ventas'), use_container_width=True)

# --- 9. SECCIÓN: ALTA ANIMALES ---
elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Registro de Lotes")
    st.info("Para los comprados el 21 Feb con 15 días, pon esa fecha y '15' en edad inicial.")
    with st.form("f_lote"):
        f = st.date_input("Fecha adquisición")
        esp = st.selectbox("Especie", ["Pollos", "Gallinas"])
        rz = st.text_input("Raza")
        tipo = st.selectbox("Tipo (Pollos)", ["N/A", "Blanco", "Campero"])
        e_ini = st.number_input("Edad al comprar (días)", value=15)
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud €")
        if st.form_submit_button("✅ DAR DE ALTA"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, tipo, e_ini, can, pre, 'Activo'))
            conn.commit(); st.rerun()
    st.dataframe(cargar_tabla('lotes'))

# --- 10. SECCIÓN: ADMIN DATOS ---
elif menu == "🛠️ ADMIN DATOS":
    st.title("🛠️ Administración")
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df_admin = cargar_tabla(t)
    st.dataframe(df_admin)
    id_del = st.number_input("ID a eliminar", min_value=0)
    if st.button("🗑️ BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id=?", (id_del,))
        conn.commit(); st.rerun()
