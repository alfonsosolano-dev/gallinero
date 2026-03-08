import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.59", layout="wide")
conn = sqlite3.connect('corral_v59_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    conn.commit()

inicializar_db()

def cargar(tabla):
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()

# --- 2. MENÚ LATERAL CON ICONOS ---
st.sidebar.title("🐓 MI CORRAL")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. SECCIÓN: RENTABILIDAD (POR PESTAÑAS) ---
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis por Especie")
    df_l = cargar('lotes'); df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    tab_gen, tab_gall, tab_poll, tab_cod = st.tabs(["🌍 Global", "🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])
    
    with tab_gen:
        g_t = df_g['importe'].sum(); v_t = df_v['total'].sum()
        st.metric("Balance Total", f"{v_t - g_t:.2f}€", delta=f"{v_t - g_t:.2f}€")
        if not df_g.empty: st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="Gastos por Categoría"))

    for tab, esp in [(tab_gall, "Gallinas"), (tab_poll, "Pollos"), (tab_cod, "Codornices")]:
        with tab:
            g_e = df_g[df_g['raza'].str.contains(esp, case=False, na=False) | df_g['categoria'].str.contains(esp, case=False, na=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp]['total'].sum()
            st.subheader(f"Balance {esp}: {v_e - g_e:.2f}€")
            p_e = df_p[df_p['especie'] == esp]
            if not p_e.empty: st.plotly_chart(px.line(p_e, x='fecha', y='cantidad', title=f"Producción de {esp}"))

# --- 4. SECCIÓN: CRECIMIENTO (LÓGICA MEJORADA) ---
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Madurez y Objetivos")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            
            # Asignación de metas según los nuevos desplegables
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos':
                if "BLANCO" in rz: meta = 60
                elif "CAMPERO" in rz: meta = 95
                else: meta = 110
            else: # Gallinas
                if "ROJA" in rz: meta = 140
                elif "CHOCOLATE" in rz: meta = 185
                elif "BLANCA" in rz: meta = 150
                else: meta = 165
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"🔹 {row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.write(f"Objetivo de madurez: **{meta} días**")
                st.progress(prog)
                if edad_t >= meta: st.success("🎯 ¡LISTO PARA PRODUCCIÓN!")
                else: st.info(f"Faltan aprox. {meta - edad_t} días para la madurez.")

# --- 5. SECCIÓN: PUESTA (CON ALERTA VISUAL) ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Registro de Huevos")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, l in df_l[(df_l['especie'] == 'Gallinas') & (df_l['estado'] == 'Activo')].iterrows():
            edad = (datetime.now() - datetime.strptime(l['fecha'], '%d/%m/%Y')).days + int(l['edad_inicial'])
            if edad >= 130: st.error(f"⚠️ ¡ATENCIÓN! Las {l['raza']} ya tienen {edad} días. ¿Has puesto el huevo ficticio?")
    
    with st.form("fp", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        esp = col2.selectbox("Especie", ["Gallinas", "Codornices"])
        rz = st.selectbox("Capa/Color", ["Roja", "Blanca", "Chocolate", "Azul/Verde", "Codorniz Japónica"])
        can = st.number_input("Cantidad", min_value=1)
        if st.form_submit_button("✅ ANOTAR"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); st.rerun()

# --- 6. SECCIÓN: ALTA ANIMALES (NUEVOS DESPLEGABLES) ---
elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Entrada de Nuevo Lote")
    with st.form("fa"):
        f = st.date_input("Fecha de llegada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz_sel = st.selectbox("Raza exacta", ["Roja", "Blanca", "Chocolate", "Pollo Blanco (Engorde)", "Pollo Campero", "Codorniz Japónica", "OTRA"])
        rz_input = st.text_input("Si elegiste 'OTRA', escribe el nombre:")
        raza_f = rz_input if rz_sel == "OTRA" else rz_sel
        e_ini = st.number_input("Edad actual (días)", value=15)
        can = st.number_input("Cantidad de aves", min_value=1)
        pre = st.number_input("Precio por unidad (€)")
        if st.form_submit_button("✅ REGISTRAR ENTRADA"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f_s, esp, raza_f, "N/A", e_ini, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f_s, f"Compra {can} {raza_f}", can*pre, "Animales", raza_f))
            conn.commit(); st.rerun()

# --- 7. GASTOS, VENTAS, NAVIDAD Y ADMIN ---
elif menu == "💸 GASTOS":
    st.title("💸 Gastos")
    with st.form("fg"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        rz = st.text_input("Asignar a Raza"); con = st.text_input("Concepto"); imp = st.number_input("Importe (€)")
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit(); st.rerun()
    st.dataframe(cargar('gastos'))

elif menu == "💰 VENTAS":
    st.title("💰 Ventas")
    with st.form("fv"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro = st.selectbox("Producto", ["Huevos", "Animal Vivo", "Carne"]); can = st.number_input("Cantidad"); tot = st.number_input("Total (€)")
        if st.form_submit_button("✅ REGISTRAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, especie) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, can, tot, "General", esp))
            conn.commit(); st.rerun()

elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación de Invierno")
    st.info("💡 Consejo: A partir de octubre, programa 14h de luz para no perder la puesta.")

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Administración")
    tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        st.dataframe(df)
        id_b = st.number_input("ID a eliminar", min_value=0)
        if st.button("🗑️ Borrar registro"):
            c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,))
            conn.commit(); st.rerun()
