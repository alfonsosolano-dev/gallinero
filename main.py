import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN Y DIRECTORIOS ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide")

# Crear carpeta de datos si no existe (Indentación corregida)
if not os.path.exists('data'):
    os.makedirs('data')

DB_PATH = './data/corral_final_consolidado.db'

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

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

# ====================== 2. FUNCIONES AUXILIARES ======================
def cargar(tabla):
    conn = get_conn()
    try:
        return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def calcular_beneficio_mensual():
    df_g = cargar('gastos')
    df_v = cargar('ventas')
    if df_g.empty and df_v.empty:
        return pd.DataFrame()
    
    if not df_g.empty:
        df_g['fecha_dt'] = pd.to_datetime(df_g['fecha'], format='%d/%m/%Y', errors='coerce')
    if not df_v.empty:
        df_v['fecha_dt'] = pd.to_datetime(df_v['fecha'], format='%d/%m/%Y', errors='coerce')
    
    gastos_m = df_g.groupby(pd.Grouper(key='fecha_dt', freq='ME'))['importe'].sum().reset_index() if not df_g.empty else pd.DataFrame(columns=['fecha_dt', 'importe'])
    ventas_m = df_v.groupby(pd.Grouper(key='fecha_dt', freq='ME'))['total'].sum().reset_index() if not df_v.empty else pd.DataFrame(columns=['fecha_dt', 'total'])
    
    df_merge = pd.merge(ventas_m, gastos_m, on='fecha_dt', how='outer').fillna(0)
    df_merge['Beneficio'] = df_merge['total'] - df_merge['importe']
    df_merge['mes'] = df_merge['fecha_dt'].dt.strftime('%b %Y')
    return df_merge.sort_values('fecha_dt')

# ====================== 3. MENÚ LATERAL ======================
st.sidebar.title("🐓 GESTIÓN INTEGRAL PRO")
menu = st.sidebar.radio("IR A:", ["🏠 DASHBOARD", "📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "💉 SALUD ANIMAL", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# ============================= 🏠 DASHBOARD =============================
if menu == "🏠 DASHBOARD":
    st.title("🏠 Dashboard de Control")
    df_l = cargar('lotes'); df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion'); df_s = cargar('salud')

    st.subheader("📊 Población Actual")
    col1, col2, col3 = st.columns(3)
    col1.metric("Gallinas", int(df_l[df_l['especie']=='Gallinas']['cantidad'].sum() if not df_l.empty else 0))
    col2.metric("Pollos", int(df_l[df_l['especie']=='Pollos']['cantidad'].sum() if not df_l.empty else 0))
    col3.metric("Codornices", int(df_l[df_l['especie']=='Codornices']['cantidad'].sum() if not df_l.empty else 0))

    st.divider()
    st.subheader("💰 Balance Económico Global")
    ing = df_v['total'].sum() if not df_v.empty else 0
    gas = df_g['importe'].sum() if not df_g.empty else 0
    c_i, c_g, c_b = st.columns(3)
    c_i.metric("Ingresos", f"{ing:.2f}€")
    c_g.metric("Gastos", f"{gas:.2f}€", delta_color="inverse")
    c_b.metric("Beneficio Neto", f"{ing - gas:.2f}€", delta=f"{ing - gas:.2f}€")

    st.divider()
    c_left, c_right = st.columns([1, 2])
    with c_left:
        st.subheader("💉 Próximas Vacunas/Curas")
        hoy = datetime.now().date()
        if not df_s.empty:
            df_s['fecha_dt'] = pd.to_datetime(df_s['fecha'], format='%d/%m/%Y', errors='coerce').dt.date
            proximos = df_s[df_s['fecha_dt'] <= hoy + timedelta(days=7)]
            if not proximos.empty:
                for _, row in proximos.iterrows():
                    st.warning(f"**{row['tipo']}** - Lote {row['lote_id']} ({row['fecha']})")
            else: st.success("Todo al día.")
        else: st.info("Sin registros de salud.")

    with c_right:
        df_bm = calcular_beneficio_mensual()
        if not df_bm.empty:
            st.plotly_chart(px.bar(df_bm, x='mes', y='Beneficio', color='Beneficio', text_auto='.2f', title="Beneficio Mensual (€)"), use_container_width=True)

# ============================= 📊 RENTABILIDAD =============================
elif menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis de Rentabilidad")
    df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    t1, t2, t3 = st.tabs(["Gallinas", "Pollos", "Codornices"])
    for tab, esp in zip([t1, t2, t3], ["Gallinas", "Pollos", "Codornices"]):
        with tab:
            g_e = df_g[df_g['categoria'].str.contains(esp, na=False, case=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp]['total'].sum()
            st.metric(f"Balance {esp}", f"{v_e - g_e:.2f}€")
            p_data = df_p[df_p['especie'] == esp]
            if not p_data.empty:
                st.plotly_chart(px.line(p_data, x='fecha', y='cantidad', title="Producción Histórica"))

# ============================= 📈 CRECIMIENTO =============================
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Madurez de los Lotes")
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
                st.write(f"Progreso: {int(prog*100)}% | Meta: {meta} días")

# ============================= 🥚 PUESTA =============================
elif menu == "🥚 PUESTA":
    st.title("🥚 Registro de Puesta")
    df_l = cargar('lotes')
    razas = df_l['raza'].unique().tolist() if not df_l.empty else ["Roja"]
    with st.form("fp"):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", razas)
        can = st.number_input("Cantidad de Huevos", min_value=1)
        if st.form_submit_button("Guardar"):
            esp = "Gallinas" if rz != "Codorniz" else "Codornices"
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); conn.close(); st.success("✅ Puesta anotada"); st.rerun()

# ============================= 💸 GASTOS =============================
elif menu == "💸 GASTOS":
    st.title("💸 Gastos (Pienso/Salud/Obra)")
    with st.form("fg"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        con = st.text_input("Concepto (Ej: Saco 25kg)")
        imp = st.number_input("Importe (€)", min_value=0.0)
        kgs = st.number_input("Kilos", min_value=0.0)
        if st.form_submit_button("Registrar Gasto"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, raza) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, kgs, cat, "General"))
            conn.commit(); conn.close(); st.success("✅ Gasto guardado"); st.rerun()

# ============================= 💰 VENTAS =============================
elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    with st.form("fv"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        prod = st.text_input("Producto")
        tot = st.number_input("Total Venta (€)", min_value=0.0)
        if st.form_submit_button("Registrar Venta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza, especie) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), prod, 1, tot, "General", esp))
            conn.commit(); conn.close(); st.success("✅ Venta guardada"); st.rerun()

# ============================= 🐣 ALTA ANIMALES =============================
elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Entrada de Animales")
    with st.form("fa"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Pollo Blanco", "Pollo Campero", "Codorniz Japónica"])
        can = st.number_input("Cantidad", min_value=1)
        e_ini = st.number_input("Edad inicial (días)", value=15)
        if st.form_submit_button("Dar de Alta"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, 0.0, 'Activo'))
            conn.commit(); conn.close(); st.success("✅ Lote creado"); st.rerun()

# ============================= 💉 SALUD ANIMAL =============================
elif menu == "💉 SALUD ANIMAL":
    st.title("💉 Registro Veterinario")
    df_l = cargar('lotes')
    with st.form("fs"):
        f = st.date_input("Fecha")
        l_id = st.selectbox("Lote ID", df_l['id'].tolist() if not df_l.empty else [0])
        tipo = st.selectbox("Acción", ["Desparasitación", "Vacuna", "Vitamina", "Tratamiento"])
        nota = st.text_area("Notas")
        if st.form_submit_button("Guardar Salud"):
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO salud (fecha, lote_id, tipo, notas) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), l_id, tipo, nota))
            conn.commit(); conn.close(); st.success("✅ Registro médico guardado"); st.rerun()

# ============================= 🎄 PLAN NAVIDAD =============================
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Plan Navidad 2026")
    tipo = st.selectbox("Pollo para Navidad", ["Pollo Campero", "Pollo Blanco"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=dias)
    st.success(f"📅 Compra tus pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# ============================= 🛠️ ADMIN =============================
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Administración y Backup")
    tablas = ['lotes','gastos','ventas','produccion','salud']
    
    # Exportar a Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for tabla in tablas:
            df_export = cargar(tabla)
            if not df_export.empty:
                df_export.to_excel(writer, sheet_name=tabla, index=False)
    
    st.download_button(label="📥 Descargar Backup Completo", data=output.getvalue(), file_name=f'backup_corral_{datetime.now().strftime("%Y%m%d")}.xlsx')
    
    st.divider()
    sel_tab = st.selectbox("Gestionar tabla:", tablas)
    df_view = cargar(sel_tab)
    st.dataframe(df_view)
    id_del = st.number_input("ID a borrar", min_value=0)
    if st.button("🗑️ Borrar"):
        conn = get_conn(); c = conn.cursor()
        c.execute(f"DELETE FROM {sel_tab} WHERE id=?", (id_del,))
        conn.commit(); conn.close(); st.rerun()
