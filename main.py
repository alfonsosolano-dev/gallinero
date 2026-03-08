import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y BASE DE DATOS ---
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide")
conn = sqlite3.connect('corral_final_consolidado.db', check_same_thread=False)
c = conn.cursor()

# Inicialización segura de la DB (no borra datos existentes)
def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    conn.commit()

inicializar_db()

# Backup automático al iniciar la app
for tabla in ['lotes','gastos','ventas','produccion']:
    df_backup = pd.read_sql(f"SELECT * FROM {tabla}", conn)
    df_backup.to_excel(f"backup_{tabla}_{datetime.now().strftime('%Y%m%d')}.xlsx", index=False)

# Función para cargar tablas
def cargar(tabla):
    try:
        return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except:
        return pd.DataFrame()

# --- 2. MENÚ LATERAL ---
st.sidebar.title("🐓 GESTIÓN INTEGRAL")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS (PIENSO)", "💰 VENTAS", "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# --- 3. RENTABILIDAD ---
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis de Rentabilidad")
    df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion')
    tabs = st.tabs(["🌍 General", "🐔 Gallinas", "🐥 Pollos", "🐦 Codornices"])

    with tabs[0]:
        g_t = df_g['importe'].sum(); v_t = df_v['total'].sum()
        st.metric("Beneficio Global", f"{v_t - g_t:.2f}€", delta=f"{v_t - g_t:.2f}€")
        if not df_g.empty:
            st.plotly_chart(px.pie(df_g, values='importe', names='categoria'))

    for i, esp in enumerate(["Gallinas", "Pollos", "Codornices"], 1):
        with tabs[i]:
            g_e = df_g[df_g['categoria'].str.contains(esp, na=False)]['importe'].sum()
            v_e = df_v[df_v['especie'] == esp]['total'].sum()
            st.subheader(f"Balance {esp}: {v_e - g_e:.2f}€")
            p_data = df_p[df_p['especie'] == esp]
            if not p_data.empty:
                p_data['fecha'] = p_data['fecha'].astype(str)  # Corregir fechas
                st.plotly_chart(px.line(p_data, x='fecha', y='cantidad'))

# --- 4. CRECIMIENTO ---
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Control de Madurez")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])
            rz = row['raza'].upper()
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
            else: meta = 140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
            prog = min(1.0, edad_t/meta)
            with st.expander(f"🔹 {row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.progress(prog)
                if prog >= 0.8 and row['especie'] != 'Gallinas': st.warning("⚠️ REPOSICIÓN PRÓXIMA")
                st.write(f"Meta: {meta} días | Progreso: {int(prog*100)}%")

# --- 5. GASTOS ---
elif menu == "💸 GASTOS (PIENSO)":
    st.title("💸 Gastos y Suministros")
    with st.form("fg"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)")
        kgs = st.number_input("Kilos", 0.0)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, raza) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, kgs, cat, "General"))
            conn.commit(); st.rerun()
    st.dataframe(cargar('gastos'))

# --- 6. PLAN NAVIDAD ---
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Plan Navidad 2026")
    tipo = st.selectbox("Tipo de Pollo", ["Pollo Campero", "Pollo Blanco"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=dias)
    st.success(f"📅 Comprar pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# --- 7. ADMIN ---
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Administración y Copia de Seguridad")
    tab = st.selectbox("Seleccionar Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')
        st.download_button(label="📥 DESCARGAR TABLA EN EXCEL", data=output.getvalue(), file_name=f"corral_{tab}_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.divider()
        st.dataframe(df)
        id_b = st.number_input("ID a borrar", 0)
        if st.button("🗑️ BORRAR REGISTRO"):
            c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,))
            conn.commit(); st.rerun()

# --- 8. PUESTA ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Puesta")
    df_l = cargar('lotes')
    razas_disponibles = df_l['raza'].unique().tolist() if not df_l.empty else ["Roja"]
    f = st.date_input("Fecha")
    rz = st.selectbox("Raza", razas_disponibles)
    can = st.number_input("Cantidad", 1)
    if st.button("Anotar"):
        especie = "Gallinas" if rz != "Codorniz" else "Codornices"
        c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), rz, can, especie))
        conn.commit(); st.rerun()

# --- 9. VENTAS ---
elif menu == "💰 VENTAS":
    st.title("💰 Ventas")
    st.dataframe(cargar('ventas'))

# --- 10. ALTA ANIMALES ---
elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Alta")
    with st.form("fa"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Pollo Blanco (Engorde)", "Pollo Campero", "Codorniz Japónica", "OTRA"])
        can = st.number_input("Cant.")
        pre = st.number_input("Precio/ud")
        e_ini = st.number_input("Edad inicial", 15)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, rz, "N/A", e_ini, can, pre, 'Activo'))
            conn.commit(); st.rerun()
