import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# ====================== 1. CONFIGURACIÓN ======================

st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🚜")

if not os.path.exists('data'): os.makedirs('data')
DB_PATH = './data/corral_maestro_2026.db'

# ====================== 2. BASE DE DATOS ======================

def get_conn(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
conn = get_conn(); c = conn.cursor()
# Lotes
c.execute('''CREATE TABLE IF NOT EXISTS lotes (
id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, raza TEXT, cantidad INTEGER, estado TEXT, usuario TEXT, primera_puesta TEXT DEFAULT NULL)''')
# Producción
c.execute('''CREATE TABLE IF NOT EXISTS produccion (
id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, usuario TEXT)''')
# Finanzas
c.execute('''CREATE TABLE IF NOT EXISTS finanzas (
id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, tipo TEXT, categoria TEXT, concepto TEXT, importe REAL, usuario TEXT)''')
# Bajas
c.execute('''CREATE TABLE IF NOT EXISTS bajas (
id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT, usuario TEXT)''')
# Salud
c.execute('''CREATE TABLE IF NOT EXISTS salud (
id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT)''')
# Usuarios
c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
conn.commit(); conn.close()

inicializar_db()

# ====================== 3. LOGIN ======================

if 'auth' not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
st.title("🔐 Acceso al Sistema")
u = st.text_input("Usuario")
p = st.text_input("Clave", type="password")
if st.button("ENTRAR"):
conn = get_conn(); c = conn.cursor()
c.execute("SELECT nombre,rango FROM usuarios WHERE nombre=? AND clave=?", (u,p))
res = c.fetchone(); conn.close()
if res: st.session_state.auth=True; st.session_state.user=res[0]; st.session_state.rango=res[1]; st.rerun()
else: st.error("Usuario o contraseña incorrectos")
st.stop()
if st.sidebar.button("Cerrar Sesión"): st.session_state.auth=False; st.rerun()

# ====================== 4. FUNCIONES AUXILIARES ======================

def leer(tabla):
conn = get_conn()
try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
except: return pd.DataFrame()
finally: conn.close()

def registrar_primera_puesta(lote_id, fecha):
conn = get_conn(); c = conn.cursor()
c.execute("UPDATE lotes SET primera_puesta=? WHERE id=?", (fecha, lote_id))
conn.commit(); conn.close()

# ====================== 5. MENÚ ======================

st.sidebar.title(f"👤 {st.session_state.user}")
st.sidebar.write(f"Rango: `{st.session_state.rango}`")

opcion = st.sidebar.radio("SELECCIONE TAREA:", [
"🏠 Vista General",
"🐣 Entrada de Animales",
"🥚 Registro de Puesta",
"☠️ Reportar Baja",
"💰 Gastos y Ventas",
"📊 Estadísticas",
"💉 Salud",
"🛠️ Administración"
])

# ---------------- 🏠 VISTA GENERAL ----------------

if opcion=="🏠 Vista General":
st.title("🏠 Estado Actual del Corral")
df_l=leer('lotes'); df_b=leer('bajas')
totales = df_l['cantidad'].sum() - (df_b['cantidad'].sum() if not df_b.empty else 0)
c1,c2,c3 = st.columns(3)
c1.metric("Aves Totales", totales)
c2.metric("Lotes Activos", len(df_l))
c3.metric("Bajas", int(df_b['cantidad'].sum()) if not df_b.empty else 0, delta_color="inverse")
st.divider(); st.subheader("📋 Lotes")
st.dataframe(df_l, use_container_width=True)

# ---------------- 🐣 ENTRADA DE ANIMALES ----------------

elif opcion=="🐣 Entrada de Animales":
st.title("🐣 Registrar Nuevo Lote")
with st.form("form_alta"):
tipo=st.selectbox("Animal", ["Gallina Ponedora","Pollo Engorde","Codorniz","Pavo","Pato"])
raza=st.text_input("Raza")
cant=st.number_input("Cantidad", min_value=1, value=10)
fecha=st.date_input("Fecha de entrada")
if st.form_submit_button("✅ CONFIRMAR ENTRADA"):
conn=get_conn(); c=conn.cursor()
c.execute("INSERT INTO lotes (fecha,tipo,raza,cantidad,estado,usuario) VALUES (?,?,?,?,?,?)",
(fecha.strftime('%d/%m/%Y'),tipo,raza,cant,'Activo',st.session_state.user))
conn.commit(); conn.close(); st.success("Lote registrado")

# ---------------- 🥚 REGISTRO DE PUESTA ----------------

elif opcion=="🥚 Registro de Puesta":
st.title("🥚 Registro de Puesta")
df_l=leer('lotes')
if df_l.empty: st.warning("No hay lotes registrados")
else:
with st.form("form_puesta"):
lote_id=st.selectbox("Seleccionar Lote", df_l['id'].tolist())
fecha_puesta=st.date_input("Fecha de Puesta", value=datetime.now().date())
cant=st.number_input("Cantidad de Huevos", min_value=1)
primera=st.checkbox("Marcar como Primera Puesta")
if st.form_submit_button("💾 Guardar"):
conn=get_conn(); c=conn.cursor()
c.execute("INSERT INTO produccion (fecha,lote_id,cantidad,usuario) VALUES (?,?,?,?)",
(fecha_puesta.strftime('%d/%m/%Y'), lote_id, cant, st.session_state.user))
if primera: registrar_primera_puesta(lote_id, fecha_puesta.strftime('%d/%m/%Y'))
conn.commit(); conn.close(); st.success("Registro guardado")

# ---------------- ☠️ BAJAS ----------------

elif opcion=="☠️ Reportar Baja":
st.title("☠️ Registro de Bajas")
df_l=leer('lotes')
if df_l.empty: st.warning("No hay lotes")
else:
with st.form("form_baja"):
lote_id=st.selectbox("Lote", df_l['id'].tolist())
cant=st.number_input("Cantidad de bajas", min_value=1)
motivo=st.selectbox("Motivo", ["Enfermedad","Depredador","Accidente","Desconocido"])
if st.form_submit_button("❌ Confirmar Baja"):
conn=get_conn(); c=conn.cursor()
c.execute("INSERT INTO bajas (fecha,lote_id,cantidad,motivo,usuario) VALUES (?,?,?,?,?)",
(datetime.now().strftime('%d/%m/%Y'), lote_id, cant, motivo, st.session_state.user))
conn.commit(); conn.close(); st.error(f"{cant} bajas registradas")

# ---------------- 💰 GASTOS Y VENTAS ----------------

elif opcion=="💰 Gastos y Ventas":
st.title("💰 Registro Finanzas")
with st.form("form_finanzas"):
tipo=st.selectbox("Tipo", ["Gasto","Venta"])
cat=st.text_input("Categoría")
con=st.text_input("Concepto")
imp=st.number_input("Importe (€)", min_value=0.0)
if st.form_submit_button("💾 Guardar"):
conn=get_conn(); c=conn.cursor()
c.execute("INSERT INTO finanzas (fecha,tipo,categoria,concepto,importe,usuario) VALUES (?,?,?,?,?,?)",
(datetime.now().strftime('%d/%m/%Y'), tipo, cat, con, imp, st.session_state.user))
conn.commit(); conn.close(); st.success("Operación registrada")

# ---------------- 💉 SALUD ----------------

elif opcion=="💉 Salud":
st.title("💉 Registro de Salud")
df_l=leer('lotes')
with st.form("form_salud"):
lote_id=st.selectbox("Lote", df_l['id'].tolist())
tipo=st.selectbox("Tipo", ["Vacuna","Desparasitación","Tratamiento"])
notas=st.text_area("Notas")
if st.form_submit_button("Guardar"):
conn=get_conn(); c=conn.cursor()
c.execute("INSERT INTO salud (fecha,lote_id,tipo,notas,usuario) VALUES (?,?,?,?,?)",
(datetime.now().strftime('%d/%m/%Y'), lote_id, tipo, notas, st.session_state.user))
conn.commit(); conn.close(); st.success("Registro guardado")

# ---------------- 📊 ESTADÍSTICAS ----------------

elif opcion=="📊 Estadísticas":
st.title("📊 Estadísticas y Beneficios")
df_p=leer('produccion'); df_f=leer('finanzas')
if not df_f.empty:
df_f['fecha_dt']=pd.to_datetime(df_f['fecha'], format='%d/%m/%Y', errors='coerce')
gastos=df_f[df_f['tipo']=='Gasto'].groupby(pd.Grouper(key='fecha_dt',freq='M'))['importe'].sum().reset_index()
ventas=df_f[df_f['tipo']=='Venta'].groupby(pd.Grouper(key='fecha_dt',freq='M'))['importe'].sum().reset_index()
df_b=pd.merge(ventas,gastos,on='fecha_dt',how='outer').fillna(0)
df_b['Beneficio']=df_b['importe_x']-df_b['importe_y']
df_b['mes']=df_b['fecha_dt'].dt.strftime('%b %Y')
st.plotly_chart(px.bar(df_b,x='mes',y='Beneficio',text='Beneficio',title='Beneficio Mensual'),use_container_width=True)

# ---------------- 🛠️ ADMINISTRACIÓN ----------------

elif opcion=="🛠️ Administración":
if st.session_state.rango!='Admin': st.error("Acceso restringido")
else:
if st.button("📥 Descargar Backup Excel"):
output=io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
for t in ['lotes','produccion','finanzas','bajas','salud','usuarios']:
leer(t).to_excel(writer,sheet_name=t,index=False)
st.download_button("Descargar", output.getvalue(), "corral_backup.xlsx")
