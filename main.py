import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.43.2", layout="wide")
conn = sqlite3.connect('corral_v43_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_sistema():
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
    
    # Gasto automático del material de febrero (100€) si no existe
    c.execute("SELECT COUNT(*) FROM gastos WHERE concepto LIKE '%Material%'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                  ('21/02/2026', 'Compra Material y Equipamiento Inicial', 100.0, 'Infraestructura', 'General'))
    conn.commit()

inicializar_sistema()

# --- 2. FUNCIONES DE APOYO ---
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
    meta = 60 if "Blanco" in (tipo_e or "") else (110 if esp == "Pollos" else 140)
    return edad_total, meta, min(1.0, edad_total/meta)

# --- 3. MENÚ LATERAL ---
menu = st.sidebar.radio("MENÚ PRINCIPAL", 
    ["📊 RESUMEN", "🍗 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🛠️ ADMIN"])

# --- 4. SECCIÓN: RESUMEN ---
if menu == "📊 RESUMEN":
    st.title("📊 Resumen del Corral")
    df_g = cargar_tabla('gastos'); df_v = cargar_tabla('ventas')
    c1, c2, c3 = st.columns(3)
    c1.metric("Inversión Total", f"{df_g['importe'].sum()} €")
    c2.metric("Ventas Totales", f"{df_v['total'].sum()} €")
    balance = df_v['total'].sum() - df_g['importe'].sum()
    c3.metric("Balance Neto", f"{balance} €", delta=balance)
    
    st.divider()
    if not df_g.empty:
        st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="Distribución de Gastos", hole=0.4))

# --- 5. SECCIÓN: CRECIMIENTO ---
elif menu == "🍗 CRECIMIENTO":
    st.title("📈 Madurez y Tiempo de Salida")
    df_l = cargar_tabla('lotes')
    activos = df_l[df_l['estado'] == 'Activo']
    if not activos.empty:
        for _, row in activos.iterrows():
            edad, meta, prog = calcular_madurez(row['fecha'], row['edad_inicial'], row['tipo_engorde'], row['especie'])
            with st.expander(f"Lote {row['id']}: {row['raza']} - {edad} días", expanded=True):
                col_a, col_b = st.columns([1,3])
                col_a.metric("Edad Actual", f"{edad}d")
                with col_b:
                    st.write(f"Objetivo: {meta} días")
                    st.progress(prog)
                    if edad >= meta: st.error("🎯 ¡LISTO PARA SALIDA / PUESTA!")
                    else: st.info(f"Faltan aprox. {meta-edad} días.")
    else: st.info("No hay lotes activos. Registra uno en 'Alta Animales'.")

# --- 6. SECCIÓN: PUESTA ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Diario de Puesta")
    df_l = cargar_tabla('lotes')
    razas_disponibles = list(df_l['raza'].unique()) if not df_l.empty else ["Blanca", "Roja"]
    if "Chocolate" not in razas_disponibles: razas_disponibles.append("Chocolate")
    if "Huevos Azules" not in razas_disponibles: razas_disponibles.append("Huevos Azules")

    with st.form("f_prod", clear_on_submit=True):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", razas_disponibles)
        can = st.number_input("Cantidad de Huevos", min_value=1)
        if st.form_submit_button("✅ ANOTAR"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), rz, can))
            conn.commit(); st.rerun()
    
    df_p = cargar_tabla('produccion')
    if not df_p.empty:
        cmap = {"Chocolate": "#5D4037", "Roja": "#C62828", "Blanca": "#F5F5F5", "Huevos Azules": "#81D4FA", "General": "#FFA000"}
        st.plotly_chart(px.bar(df_p, x='fecha', y='cantidad', color='raza', color_discrete_map=cmap, barmode='group'))

# --- 7. SECCIÓN: GASTOS ---
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    with st.form("f_gasto", clear_on_submit=True):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Infraestructura", "Animales", "Salud", "Otros"])
        df_l = cargar_tabla('lotes')
        rz = st.selectbox("Asignar a Raza", ["General"] + list(df_l['raza'].unique()) if not df_l.empty else ["General"])
        con = st.text_input("Concepto (Ej: Saco Pienso)")
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
        rz = st.selectbox("Raza Relacionada", ["General"] + list(df_l['raza'].unique()) if not df_l.empty else ["General"])
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total Cobrado (€)")
        if st.form_submit_button("✅ REGISTRAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, can, tot, rz))
            conn.commit(); st.rerun()
    st.subheader("Historial de Ventas")
    st.dataframe(cargar_tabla('ventas'), use_container_width=True)

# --- 9. SECCIÓN: ALTA ANIMALES (CON SELECTOR FLEXIBLE) ---
elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Entrada de Aves")
    with st.form("f_lote"):
        f = st.date_input("Fecha adquisición")
        esp = st.selectbox("Especie", ["Pollos", "Gallinas"])
        raza_sel = st.selectbox("Selecciona Raza", ["Blanca", "Roja", "Chocolate", "Campero", "OTRA (Escribir abajo)"])
        raza_nueva = st.text_input("Si elegiste 'OTRA', escribe el nombre:")
        raza_final = raza_nueva if raza_sel == "OTRA (Escribir abajo)" else raza_sel
        tipo = st.selectbox("Tipo de Engorde", ["N/A", "Blanco", "Campero"])
        e_ini = st.number_input("Edad al comprar (días)", value=15)
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud €")
        if st.form_submit_button("✅ DAR DE ALTA"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f_s, esp, raza_final, tipo, e_ini, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f_s, f"Compra {can} {raza_final}", can*pre, "Animales", raza_final))
            conn.commit(); st.rerun()
    st.subheader("Listado de Lotes")
    st.dataframe(cargar_tabla('lotes'), use_container_width=True)

# --- 10. SECCIÓN: ADMIN ---
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Administración de Datos")
    t = st.selectbox("Tabla a gestionar", ["lotes", "gastos", "ventas", "produccion"])
    df_admin = cargar_tabla(t)
    if not df_admin.empty:
        st.dataframe(df_admin)
        id_del = st.number_input("ID del registro a eliminar", min_value=0)
        if st.button("🗑️ ELIMINAR PERMANENTEMENTE"):
            c.execute(f"DELETE FROM {t} WHERE id=?", (id_del,))
            conn.commit(); st.rerun()
    else: st.info("Tabla vacía.")
