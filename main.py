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
c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual (
id INTEGER PRIMARY KEY AUTOINCREMENT,
lote_id INTEGER,
fecha_manual TEXT
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

# --- CRECIMIENTO (con fecha manual para gallinas) ---

elif menu == "📈 CRECIMIENTO":
st.title("📈 Control de Madurez")
df_l = cargar('lotes')
df_pm = cargar('puesta_manual')
if not df_l.empty:
for _, row in df_l[df_l['estado']=='Activo'].iterrows():
f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'])

```
        # Permitir fecha manual de puesta
        fecha_manual = df_pm[df_pm['lote_id']==row['id']]['fecha_manual']
        if not fecha_manual.empty:
            f_ent = datetime.strptime(fecha_manual.iloc[0], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days

        rz = row['raza'].upper()
        if row['especie'] == 'Codornices': meta = 45
        elif row['especie'] == 'Pollos': meta = 60 if "BLANCO" in rz else 95 if "CAMPERO" in rz else 110
        else: meta = 140 if "ROJA" in rz else 185 if "CHOCOLATE" in rz else 165
        prog = min(1.0, edad_t/meta)
        with st.expander(f"🔹 {row['especie']} {row['raza']} - {edad_t} días", expanded=True):
            st.progress(prog)
            if prog >= 0.8 and row['especie'] != 'Gallinas': st.warning("⚠️ REPOSICIÓN PRÓXIMA")
            st.write(f"Meta: {meta} días | Progreso: {int(prog*100)}%")
            # Opción de actualizar manualmente la fecha de puesta
            if row['especie'] == 'Gallinas':
                nueva_fecha = st.date_input(f"Fecha de puesta manual para {row['raza']}", value=f_ent.date(), key=row['id'])
                if st.button(f"Actualizar fecha puesta lote {row['id']}", key=f"btn_{row['id']}"):
                    c.execute("INSERT OR REPLACE INTO puesta_manual (lote_id, fecha_manual) VALUES (?,?)", (row['id'], nueva_fecha.strftime('%d/%m/%Y')))
                    conn.commit()
                    st.success("✅ Fecha de puesta actualizada")
```
