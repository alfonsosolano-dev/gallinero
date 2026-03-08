# main.py
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime, timedelta

# ====================== CONFIGURACIÓN ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide")
DB_FILE = "corral_final_pro.db"

# ====================== BASE DE DATOS ======================
def get_conn():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT,
        cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0,
        categoria TEXT, raza TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL,
        raza TEXT, especie TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT
    )''')
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try:
        df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def insertar(tabla, datos):
    conn = get_conn()
    c = conn.cursor()
    keys = ", ".join(datos.keys())
    placeholders = ", ".join("?" for _ in datos)
    c.execute(f"INSERT INTO {tabla} ({keys}) VALUES ({placeholders})", tuple(datos.values()))
    conn.commit()
    conn.close()

def borrar(tabla, id_):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"DELETE FROM {tabla} WHERE id=?", (id_,))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== UTILIDADES ======================
META_EDAD = {
    "Gallinas": {"ROJA": 140, "CHOCOLATE": 185, "DEFAULT": 165},
    "Pollos": {"BLANCO": 60, "CAMPERO": 95, "DEFAULT": 110},
    "Codornices": {"DEFAULT": 45}
}

def calcular_progreso(fecha_str, especie, raza, edad_inicial=0):
    f_ent = datetime.strptime(fecha_str, '%d/%m/%Y')
    edad_t = (datetime.now() - f_ent).days + int(edad_inicial)
    raza = raza.upper()
    meta = META_EDAD.get(especie, {}).get(raza, META_EDAD.get(especie, {}).get("DEFAULT", 100))
    prog = min(1.0, edad_t / meta)
    return edad_t, meta, prog

def plot_grafico_stock(df, especie_col='especie', cantidad_col='cantidad', fecha_col='fecha'):
    if df.empty: return None
    df_group = df.groupby([fecha_col, especie_col])[cantidad_col].sum().reset_index()
    fig = px.line(df_group, x=fecha_col, y=cantidad_col, color=especie_col, markers=True, title="Stock por especie")
    return fig

def plot_beneficios(df_gastos, df_ventas):
    if df_gastos.empty and df_ventas.empty: return None
    df_gastos['mes'] = pd.to_datetime(df_gastos['fecha'], format='%d/%m/%Y').dt.to_period('M')
    df_ventas['mes'] = pd.to_datetime(df_ventas['fecha'], format='%d/%m/%Y').dt.to_period('M')
    gastos_mes = df_gastos.groupby('mes')['importe'].sum().reset_index()
    ventas_mes = df_ventas.groupby('mes')['total'].sum().reset_index()
    df_merge = pd.merge(ventas_mes, gastos_mes, on='mes', how='outer').fillna(0)
    df_merge['beneficio'] = df_merge['total'] - df_merge['importe']
    fig = px.bar(df_merge, x='mes', y='beneficio', title="Beneficios Mensuales", text='beneficio')
    return fig

# ====================== MENÚ LATERAL ======================
st.sidebar.title("🐓 GESTIÓN INTEGRAL PRO")
menu = st.sidebar.radio("IR A:", ["📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS",
                                  "🐣 ALTA ANIMALES", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# ============================= RENTABILIDAD =============================
if menu == "📊 RENTABILIDAD":
    st.title("📊 Análisis de Rentabilidad PRO")
    df_g, df_v, df_p = cargar('gastos'), cargar('ventas'), cargar('produccion')

    st.subheader("Beneficio Global")
    g_t = df_g['importe'].sum() if not df_g.empty else 0
    v_t = df_v['total'].sum() if not df_v.empty else 0
    st.metric("Beneficio Total", f"{v_t - g_t:.2f}€")
    
    fig1 = plot_beneficios(df_g, df_v)
    if fig1: st.plotly_chart(fig1)

    st.subheader("Stock por especie")
    df_l = cargar('lotes')
    fig2 = plot_grafico_stock(df_l)
    if fig2: st.plotly_chart(fig2)

# ============================= CRECIMIENTO =============================
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Control de Madurez PRO")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            edad_t, meta, prog = calcular_progreso(row['fecha'], row['especie'], row['raza'], row['edad_inicial'])
            with st.expander(f"{row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.progress(prog)
                if prog >= 0.8 and row['especie'] != 'Gallinas':
                    st.warning("⚠️ REPOSICIÓN PRÓXIMA")
                st.write(f"Meta: {meta} días | Progreso: {int(prog*100)}%")

# ============================= FORMULARIOS DINÁMICOS =============================
elif menu == "💸 GASTOS":
    st.title("💸 Registrar Gastos")
    with st.form("fg"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Salud", "Infraestructura"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)")
        kgs = st.number_input("Kilos", 0.0)
        if st.form_submit_button("✅ Registrar"):
            insertar('gastos', {'fecha': f.strftime('%d/%m/%Y'), 'concepto': con, 'importe': imp, 'kilos': kgs, 'categoria': cat, 'raza': 'General'})
            st.success("✅ Gastos registrados")
    st.dataframe(cargar('gastos'))

elif menu == "💰 VENTAS":
    st.title("💰 Registrar Ventas")
    with st.form("fv"):
        f = st.date_input("Fecha")
        prod = st.text_input("Producto")
        can = st.number_input("Cantidad", 1)
        total = st.number_input("Total (€)")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.text_input("Raza")
        if st.form_submit_button("✅ Registrar"):
            insertar('ventas', {'fecha': f.strftime('%d/%m/%Y'), 'producto': prod, 'cantidad': can, 'total': total, 'especie': esp, 'raza': rz})
            st.success("✅ Venta registrada")
    st.dataframe(cargar('ventas'))

elif menu == "🥚 PUESTA":
    st.title("🥚 Registrar Puesta")
    with st.form("fp"):
        f = st.date_input("Fecha")
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Codorniz"])
        can = st.number_input("Cantidad", 1)
        if st.form_submit_button("✅ Registrar"):
            especie = "Gallinas" if rz != "Codorniz" else "Codornices"
            insertar('produccion', {'fecha': f.strftime('%d/%m/%Y'), 'raza': rz, 'cantidad': can, 'especie': especie})
            st.success("✅ Producción registrada")
    st.dataframe(cargar('produccion'))

elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Registrar Lotes")
    with st.form("fa"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.text_input("Raza")
        can = st.number_input("Cantidad", 1)
        pre = st.number_input("Precio/ud")
        e_ini = st.number_input("Edad inicial", 0)
        if st.form_submit_button("✅ Registrar"):
            insertar('lotes', {'fecha': f.strftime('%d/%m/%Y'), 'especie': esp, 'raza': rz, 'tipo_engorde': 'N/A',
                               'edad_inicial': e_ini, 'cantidad': can, 'precio_ud': pre, 'estado': 'Activo'})
            st.success("✅ Lote registrado")
    st.dataframe(cargar('lotes'))

elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Plan Navidad 2026")
    tipo = st.selectbox("Tipo de Pollo", ["Pollo Campero", "Pollo Blanco"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=dias)
    st.success(f"📅 Comprar pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Administración y Copia de Seguridad")
    tab = st.selectbox("Seleccionar Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = cargar(tab)
    if not df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Datos')
        output.seek(0)
        st.download_button(f"📥 Descargar {tab}", data=output.getvalue(),
                           file_name=f"corral_pro_{tab}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.divider()
        st.dataframe(df)
        id_b = st.number_input("ID a borrar", 0)
        if st.button("🗑️ BORRAR REGISTRO") and id_b > 0:
            if id_b in df['id'].values:
                borrar(tab, id_b)
                st.success("✅ Registro borrado")
                st.experimental_rerun()
            else:
                st.warning("❌ ID no encontrado")
