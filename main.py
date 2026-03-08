import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide")
DB_FILE = 'corral_pro_v66.db'

def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT)''')
    conn.commit()
    conn.close()

inicializar_db()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

# --- 2. LÓGICA DE NEGOCIO ---
def calcular_beneficio_mensual():
    df_g = cargar('gastos'); df_v = cargar('ventas')
    if df_g.empty and df_v.empty: return pd.DataFrame()
    df_g['fecha'] = pd.to_datetime(df_g['fecha'], format='%d/%m/%Y', errors='coerce')
    df_v['fecha'] = pd.to_datetime(df_v['fecha'], format='%d/%m/%Y', errors='coerce')
    gastos_m = df_g.groupby(pd.Grouper(key='fecha', freq='ME'))['importe'].sum().reset_index()
    ventas_m = df_v.groupby(pd.Grouper(key='fecha', freq='ME'))['total'].sum().reset_index()
    df_merge = pd.merge(ventas_m, gastos_m, on='fecha', how='outer').fillna(0)
    df_merge['Beneficio'] = df_merge['total'] - df_merge['importe']
    df_merge['mes'] = df_merge['fecha'].dt.strftime('%b %Y')
    return df_merge

# --- 3. MENÚ LATERAL ---
st.sidebar.title("🐓 GESTIÓN INTEGRAL PRO")
menu = st.sidebar.radio("IR A:", ["🏠 DASHBOARD", "📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "💉 SALUD ANIMAL", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# ============================= 🏠 DASHBOARD =============================
if menu == "🏠 DASHBOARD":
    st.title("🏠 Panel de Control Principal")
    df_l = cargar('lotes'); df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion'); df_s = cargar('salud')
    
    # Fila 1: Stock de Animales
    st.subheader("📦 Stock Actual de Animales")
    c1, c2, c3 = st.columns(3)
    c1.metric("Gallinas", int(df_l[df_l['especie']=='Gallinas']['cantidad'].sum() if not df_l.empty else 0))
    c2.metric("Pollos", int(df_l[df_l['especie']=='Pollos']['cantidad'].sum() if not df_l.empty else 0))
    c3.metric("Codornices", int(df_l[df_l['especie']=='Codornices']['cantidad'].sum() if not df_l.empty else 0))

    # Fila 2: Resumen Económico Pro
    st.divider()
    st.subheader("💰 Resumen Económico")
    ingresos = df_v['total'].sum() if not df_v.empty else 0
    gastos = df_g['importe'].sum() if not df_g.empty else 0
    ec1, ec2, ec3 = st.columns(3)
    ec1.metric("Ingresos Totales", f"{ingresos:.2f}€")
    ec2.metric("Gastos Totales", f"{gastos:.2f}€", delta_color="inverse")
    ec3.metric("Beneficio Neto", f"{ingresos - gastos:.2f}€", delta=f"{ingresos - gastos:.2f}€")

    # Fila 3: Alertas y Producción
    st.divider()
    col_alert, col_prod = st.columns([1, 2])
    
    with col_alert:
        st.subheader("💉 Alertas de Salud (Próximos 7 días)")
        if not df_s.empty:
            df_s['fecha_dt'] = pd.to_datetime(df_s['fecha'], format='%d/%m/%Y', errors='coerce')
            hoy = datetime.now()
            proximos = df_s[(df_s['fecha_dt'] >= hoy) & (df_s['fecha_dt'] <= hoy + timedelta(days=7))]
            if not proximos.empty:
                for _, row in proximos.iterrows():
                    st.warning(f"**{row['tipo']}** - Lote ID: {row['lote_id']} ({row['fecha']})")
            else: st.success("Todo al día en salud.")
        else: st.info("No hay registros de salud.")

    with col_prod:
        st.subheader("🥚 Producción Reciente (Últimos 7 días)")
        if not df_p.empty:
            df_p['fecha_dt'] = pd.to_datetime(df_p['fecha'], format='%d/%m/%Y', errors='coerce')
            puesta_semana = df_p[df_p['fecha_dt'] >= (datetime.now() - timedelta(days=7))]['cantidad'].sum()
            st.info(f"Has recogido **{int(puesta_semana)}** huevos esta semana.")
            df_bm = calcular_beneficio_mensual()
            if not df_bm.empty:
                st.plotly_chart(px.bar(df_bm, x='mes', y='Beneficio', color='Beneficio', title="Evolución de Beneficios"), use_container_width=True)

# ============================= 📊 RENTABILIDAD =============================
elif menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis por Especie")
    df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    t1, t2, t3 = st.tabs(["🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])
    
    for i, (tab, esp) in enumerate(zip([t1, t2, t3], ["Gallinas", "Pollos", "Codornices"])):
        with tab:
            g_e = df_g[df_g['categoria'].str.contains(esp, na=False, case=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp]['total'].sum()
            p_e = df_p[df_p['especie'] == esp]['cantidad'].sum()
            c_a, c_b = st.columns(2)
            c_a.metric("Beneficio Especie", f"{v_e - g_e:.2f}€")
            if p_e > 0: c_b.metric("Coste medio por unidad", f"{g_e/p_e:.2f}€")
            if not df_p.empty:
                st.plotly_chart(px.line(df_p[df_p['especie']==esp], x='fecha', y='cantidad', title=f"Histórico Puesta {esp}"))

# ============================= 📈 CRECIMIENTO =============================
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Madurez de Lotes")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
            else: meta = 140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
            prog = min(1.0, edad/meta)
            with st.expander(f"{row['especie']} {row['raza']} - {edad} días"):
                st.progress(prog)
                if prog >= 0.8 and row['especie'] != 'Gallinas': st.warning("⚠️ Lote para sacrificio/venta pronto.")
                st.write(f"Progreso: {int(prog*100)}% | Meta: {meta} días")

# ============================= 💉 SALUD ANIMAL =============================
elif menu == "💉 SALUD ANIMAL":
    st.title("💉 Registro Sanitario")
    df_l = cargar('lotes')
    with st.form("fs"):
        f = st.date_input("Fecha acción")
        l_id = st.selectbox("Lote", df_l['id'].tolist() if not df_l.empty else [0])
        tipo = st.selectbox("Tipo", ["Desparasitación", "Vacuna", "Cura", "Vitamina"])
        nota = st.text_area("Notas")
        if st.form_submit_button("Guardar Salud"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO salud (fecha, lote_id, tipo, notas) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), l_id, tipo, nota))
            conn.commit(); conn.close(); st.success("✅ Salud registrada"); st.rerun()
    st.dataframe(cargar('salud'))

# ============================= 💸 GASTOS =============================
elif menu == "💸 GASTOS":
    st.title("💸 Compras de Pienso y Otros")
    with st.form("fg"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        imp = st.number_input("Importe (€)", min_value=0.0)
        kgs = st.number_input("Kilos", min_value=0.0)
        if st.form_submit_button("Registrar Gasto"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, raza) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), "Compra", imp, kgs, cat, "General"))
            conn.commit(); conn.close(); st.success("✅ Gasto anotado"); st.rerun()
    st.dataframe(cargar('gastos'))

# ============================= 🥚 PUESTA =============================
elif menu == "🥚 PUESTA":
    st.title("🥚 Registro de Producción")
    df_l = cargar('lotes')
    razas = df_l['raza'].unique().tolist() if not df_l.empty else ["Roja"]
    with st.form("fp"):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", razas)
        can = st.number_input("Cantidad Huevos", min_value=1)
        if st.form_submit_button("Anotar Puesta"):
            esp = "Gallinas" if rz != "Codorniz" else "Codornices"
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); conn.close(); st.success("✅ Puesta guardada"); st.rerun()

# ============================= 💰 VENTAS =============================
elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    with st.form("fv"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        prod = st.text_input("Producto (Huevos, Carne, etc.)")
        tot = st.number_input("Total Venta (€)", min_value=0.0)
        if st.form_submit_button("Registrar Venta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, especie) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), prod, 1, tot, "General", esp))
            conn.commit(); conn.close(); st.success("✅ Venta registrada"); st.rerun()
    st.dataframe(cargar('ventas'))

# ============================= 🐣 ALTA ANIMALES =============================
elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Entrada de Animales")
    with st.form("fa"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Pollo Blanco (Engorde)", "Pollo Campero", "Codorniz Japónica", "OTRA"])
        can = st.number_input("Cantidad", min_value=1)
        e_ini = st.number_input("Edad inicial (días)", value=15)
        if st.form_submit_button("Dar de Alta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, 0.0, 'Activo'))
            conn.commit(); conn.close(); st.success("✅ Lote creado"); st.rerun()

# ============================= 🎄 PLAN NAVIDAD =============================
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación de Navidad")
    tipo = st.selectbox("Tipo de Pollo", ["Pollo Campero", "Pollo Blanco"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=dias)
    st.success(f"📅 Para Navidad, debes comprar los pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# ============================= 🛠️ ADMIN =============================
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Administración")
    tab = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion", "salud"])
    df = cargar(tab)
    if not df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Backup')
        st.download_button("📥 Descargar Excel", data=output.getvalue(), file_name=f"corral_{tab}.xlsx")
        st.divider()
        st.dataframe(df)
        id_b = st.number_input("ID a borrar", value=0)
        if st.button("🗑️ Borrar"):
            conn = get_conn(); c = conn.cursor()
            c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,))
            conn.commit(); conn.close(); st.rerun()
