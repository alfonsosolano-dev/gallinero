import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE LA APP ---

st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide")

# Crear carpeta data si no existe

if not os.path.exists('data'):
os.makedirs('data')

# Conexión a la base de datos en la carpeta data

db_path = './data/corral_final_consolidado.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()

# --- INICIALIZACIÓN DE LA BASE DE DATOS ---

def inicializar_db():
c.execute('''CREATE TABLE IF NOT EXISTS lotes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
fecha TEXT,
especie TEXT,
raza TEXT,
tipo_engorde TEXT,
cantidad INTEGER,
precio_ud REAL,
estado TEXT,
edad_inicial INTEGER DEFAULT 0
)''')
c.execute('''CREATE TABLE IF NOT EXISTS gastos (
id INTEGER PRIMARY KEY AUTOINCREMENT,
fecha TEXT,
concepto TEXT,
importe REAL,
kilos REAL DEFAULT 0,
categoria TEXT,
raza TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS ventas (
id INTEGER PRIMARY KEY AUTOINCREMENT,
fecha TEXT,
producto TEXT,
cantidad INTEGER,
total REAL,
raza TEXT,
especie TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS produccion (
id INTEGER PRIMARY KEY AUTOINCREMENT,
fecha TEXT,
raza TEXT,
cantidad REAL,
especie TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS salud (
id INTEGER PRIMARY KEY AUTOINCREMENT,
fecha TEXT,
lote_id INTEGER,
tipo TEXT,
notas TEXT
)''')
conn.commit()

inicializar_db()

# --- FUNCIONES AUXILIARES ---

def cargar(tabla):
try:
return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
except:
return pd.DataFrame()

def calcular_beneficio_mensual():
df_g = cargar('gastos')
df_v = cargar('ventas')
if df_g.empty and df_v.empty:
return pd.DataFrame()
df_g['fecha'] = pd.to_datetime(df_g['fecha'], format='%d/%m/%Y')
df_v['fecha'] = pd.to_datetime(df_v['fecha'], format='%d/%m/%Y')
gastos_m = df_g.groupby(pd.Grouper(key='fecha', freq='M'))['importe'].sum().reset_index()
ventas_m = df_v.groupby(pd.Grouper(key='fecha', freq='M'))['total'].sum().reset_index()
df_merge = pd.merge(ventas_m, gastos_m, on='fecha', how='outer').fillna(0)
df_merge['Beneficio'] = df_merge['total'] - df_merge['importe']
df_merge['mes'] = df_merge['fecha'].dt.strftime('%Y-%m')
return df_merge

# --- MENÚ LATERAL ---

st.sidebar.title("🐓 GESTIÓN INTEGRAL PRO")
menu = st.sidebar.radio("IR A:", [
"🏠 DASHBOARD",
"📊 RENTABILIDAD",
"📈 CRECIMIENTO",
"🥚 PUESTA",
"💸 GASTOS",
"💰 VENTAS",
"🐣 ALTA ANIMALES",
"💉 SALUD ANIMAL",
"🎄 PLAN NAVIDAD",
"🛠️ ADMIN"
])

# --- DASHBOARD PRINCIPAL ---

if menu == "🏠 DASHBOARD":
st.title("🏠 Dashboard PRO")
df_l = cargar('lotes')
df_g = cargar('gastos')
df_v = cargar('ventas')
df_p = cargar('produccion')
df_s = cargar('salud')

```
st.subheader("Resumen de Animales")
st.metric("Total Gallinas", df_l[df_l['especie']=='Gallinas']['cantidad'].sum() if not df_l.empty else 0)
st.metric("Total Pollos", df_l[df_l['especie']=='Pollos']['cantidad'].sum() if not df_l.empty else 0)
st.metric("Total Codornices", df_l[df_l['especie']=='Codornices']['cantidad'].sum() if not df_l.empty else 0)

st.subheader("Resumen Económico")
ingresos = df_v['total'].sum() if not df_v.empty else 0
gastos = df_g['importe'].sum() if not df_g.empty else 0
st.metric("Beneficio Actual", f"{ingresos - gastos:.2f}€")

# Alertas de salud próximas
st.subheader("Alertas de Salud")
hoy = datetime.now().date()
if not df_s.empty:
    df_s['fecha'] = pd.to_datetime(df_s['fecha'], format='%d/%m/%Y')
    proximos = df_s[df_s['fecha'].dt.date <= hoy + pd.Timedelta(days=7)]
    if not proximos.empty:
        for _, row in proximos.iterrows():
            st.warning(f"Próximo: {row['tipo']} para Lote ID {row['lote_id']} el {row['fecha'].strftime('%d/%m/%Y')}")
    else:
        st.success("No hay acciones de salud próximas en 7 días")

# Beneficio mensual en gráfico
df_bm = calcular_beneficio_mensual()
if not df_bm.empty:
    st.subheader("Beneficio Mensual")
    st.plotly_chart(px.bar(df_bm, x='mes', y='Beneficio', text='Beneficio', title='Beneficio Mensual'))
```

# --- ADMINISTRACIÓN Y BACKUP ---

elif menu == "🛠️ ADMIN":
st.title("Administración y Copia de Seguridad")
tablas = ['lotes','gastos','ventas','produccion','salud']
backup_file = './data/backup_completo.xlsx'
with pd.ExcelWriter(backup_file, engine='xlsxwriter') as writer:
for tabla in tablas:
df = cargar(tabla)
if not df.empty:
df.to_excel(writer, sheet_name=tabla, index=False)
st.success(f"✅ Backup completo generado en {backup_file}")
st.download_button("📥 Descargar Backup", data=open(backup_file, 'rb').read(), file_name='backup_completo.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y DIRECTORIOS ---
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide")

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

# --- 2. FUNCIONES DE CARGA Y CÁLCULO ---
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
    if df_g.empty and df_v.empty: return pd.DataFrame()
    
    # Limpieza de fechas para el gráfico
    for df, col in [(df_g, 'importe'), (df_v, 'total')]:
        if not df.empty:
            df['fecha_dt'] = pd.to_datetime(df['fecha'], format='%d/%m/%Y', errors='coerce')
    
    gastos_m = df_g.groupby(pd.Grouper(key='fecha_dt', freq='ME'))['importe'].sum().reset_index() if not df_g.empty else pd.DataFrame(columns=['fecha_dt', 'importe'])
    ventas_m = df_v.groupby(pd.Grouper(key='fecha_dt', freq='ME'))['total'].sum().reset_index() if not df_v.empty else pd.DataFrame(columns=['fecha_dt', 'total'])
    
    df_merge = pd.merge(ventas_m, gastos_m, on='fecha_dt', how='outer').fillna(0)
    df_merge['Beneficio'] = df_merge['total'] - df_merge['importe']
    df_merge['mes'] = df_merge['fecha_dt'].dt.strftime('%Y-%m')
    return df_merge.sort_values('fecha_dt')

# --- 3. MENÚ LATERAL ---
st.sidebar.title("🐓 GESTIÓN INTEGRAL PRO")
menu = st.sidebar.radio("IR A:", ["🏠 DASHBOARD", "📊 RENTABILIDAD", "📈 CRECIMIENTO", "🥚 PUESTA", "💸 GASTOS", "💰 VENTAS", "🐣 ALTA ANIMALES", "💉 SALUD ANIMAL", "🎄 PLAN NAVIDAD", "🛠️ ADMIN"])

# ============================= 🏠 DASHBOARD =============================
if menu == "🏠 DASHBOARD":
    st.title("🏠 Dashboard de Control")
    df_l = cargar('lotes'); df_g = cargar('gastos'); df_v = cargar('ventas'); df_p = cargar('produccion'); df_s = cargar('salud')

    # Fila 1: Métricas de Animales
    st.subheader("📊 Población Actual")
    col1, col2, col3 = st.columns(3)
    col1.metric("Gallinas", int(df_l[df_l['especie']=='Gallinas']['cantidad'].sum() if not df_l.empty else 0))
    col2.metric("Pollos", int(df_l[df_l['especie']=='Pollos']['cantidad'].sum() if not df_l.empty else 0))
    col3.metric("Codornices", int(df_l[df_l['especie']=='Codornices']['cantidad'].sum() if not df_l.empty else 0))

    # Fila 2: Economía con Delta
    st.divider()
    st.subheader("💰 Balance Económico")
    ingresos = df_v['total'].sum() if not df_v.empty else 0
    gastos = df_g['importe'].sum() if not df_g.empty else 0
    c_i, c_g, c_b = st.columns(3)
    c_i.metric("Ingresos Totales", f"{ingresos:.2f}€")
    c_g.metric("Gastos Totales", f"{gastos:.2f}€", delta_color="inverse")
    c_b.metric("Beneficio Neto", f"{ingresos - gastos:.2f}€", delta=f"{ingresos - gastos:.2f}€")

    # Fila 3: Salud y Gráficos
    st.divider()
    c_left, c_right = st.columns([1, 2])
    
    with c_left:
        st.subheader("💉 Alertas de Salud")
        hoy = datetime.now().date()
        if not df_s.empty:
            df_s['fecha_dt'] = pd.to_datetime(df_s['fecha'], format='%d/%m/%Y').dt.date
            proximos = df_s[df_s['fecha_dt'] <= hoy + timedelta(days=7)]
            if not proximos.empty:
                for _, row in proximos.iterrows():
                    st.warning(f"**{row['tipo']}** - Lote {row['lote_id']} ({row['fecha']})")
            else: st.success("Sin tareas pendientes")
        else: st.info("No hay registros médicos")

    with c_right:
        df_bm = calcular_beneficio_mensual()
        if not df_bm.empty:
            st.plotly_chart(px.bar(df_bm, x='mes', y='Beneficio', text_auto='.2f', title="Evolución Mensual (€)"), use_container_width=True)

# ============================= 🛠️ ADMIN =============================
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Administración y Backup")
    tablas = ['lotes','gastos','ventas','produccion','salud']
    
    # Generar Excel en memoria para descarga directa
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for tabla in tablas:
            df_export = cargar(tabla)
            if not df_export.empty:
                df_export.to_excel(writer, sheet_name=tabla, index=False)
    
    st.download_button(
        label="📥 Descargar Backup Completo (Excel)",
        data=output.getvalue(),
        file_name=f'backup_corral_{datetime.now().strftime("%Y%m%d")}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    st.divider()
    # Gestión de borrado
    sel_tab = st.selectbox("Ver/Borrar datos de:", tablas)
    df_view = cargar(sel_tab)
    st.dataframe(df_view)
    id_del = st.number_input("ID a eliminar", min_value=0)
    if st.button("🗑️ Eliminar Registro"):
        conn = get_conn(); c = conn.cursor()
        c.execute(f"DELETE FROM {sel_tab} WHERE id=?", (id_del,))
        conn.commit(); conn.close(); st.rerun()

# --- LAS DEMÁS SECCIONES (PUESTA, ALTA, ETC.) SIGUEN TU LÓGICA ANTERIOR ---
