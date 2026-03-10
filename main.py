import streamlit as st
import pandas as pd
from sqlalchemy import text
import io
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN VISUAL
st.set_page_config(page_title="CORRAL MAESTRO CLOUD", layout="wide", page_icon="🐓")

# ====================== 2. CONEXIÓN A SUPABASE ======================
conn = st.connection("postgresql", type="sql", autocommit=True)

def inicializar_tablas():
    with conn.session as s:
        # Creamos la estructura en la nube
        s.execute(text('''CREATE TABLE IF NOT EXISTS lotes 
            (id SERIAL PRIMARY KEY, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)'''))
        s.execute(text('''CREATE TABLE IF NOT EXISTS gastos 
            (id SERIAL PRIMARY KEY, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, usuario TEXT)'''))
        s.execute(text('''CREATE TABLE IF NOT EXISTS produccion 
            (id SERIAL PRIMARY KEY, fecha TEXT, lote_id INTEGER, cantidad INTEGER, usuario TEXT)'''))
        s.execute(text('''CREATE TABLE IF NOT EXISTS bajas 
            (id SERIAL PRIMARY KEY, fecha TEXT, lote_id INTEGER, cantidad INTEGER, motivo TEXT, usuario TEXT)'''))
        s.execute(text('''CREATE TABLE IF NOT EXISTS usuarios 
            (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, rango TEXT)'''))
        s.execute(text('''CREATE TABLE IF NOT EXISTS puesta_manual 
            (id SERIAL PRIMARY KEY, lote_id INTEGER, fecha_primera_puesta TEXT, usuario TEXT)'''))
        
        # Admin por defecto
        s.execute(text("INSERT INTO usuarios (nombre, clave, rango) VALUES ('admin', '1234', 'Admin') ON CONFLICT (nombre) DO NOTHING"))
        s.commit()

# Arrancamos la base de datos
try:
    inicializar_tablas()
except Exception as e:
    st.error(f"❌ Error al crear tablas: {e}")
    st.stop()

# ====================== 3. LOGIN ======================
if 'auth' not in st.session_state:
    st.session_state.update({'auth': False, 'user': "", 'rango': ""})

if not st.session_state.auth:
    st.title("🔐 Acceso al Corral Cloud")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("ENTRAR"):
            # Consultamos si el usuario existe en la nube
            res = conn.query(f"SELECT nombre, rango FROM usuarios WHERE nombre='{u}' AND clave='{p}'", ttl=0)
            if not res.empty:
                st.session_state.update({'auth': True, 'user': res.iloc[0]['nombre'], 'rango': res.iloc[0]['rango']})
                st.rerun()
            else: st.error("Usuario o clave incorrectos")
    st.stop()

# ====================== 4. MENÚ Y NAVEGACIÓN ======================
st.sidebar.title(f"👤 {st.session_state.user}")
menu = st.sidebar.radio("IR A:", [
    "🏠 DASHBOARD", "📈 MADUREZ", "🥚 REGISTRO PUESTA", 
    "☠️ REPORTAR BAJA", "💸 GASTOS", "🐣 ALTA AVES", 
    "🎄 PLAN NAVIDAD", "🛠️ ADMIN"
])

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.auth = False
    st.rerun()

# ---------------- 🏠 DASHBOARD ----------------
if menu == "🏠 DASHBOARD":
    st.title("🏠 Dashboard en Tiempo Real")
    df_l = conn.query("SELECT * FROM lotes", ttl=0)
    df_g = conn.query("SELECT * FROM gastos", ttl=0)
    df_b = conn.query("SELECT * FROM bajas", ttl=0)
    
    aves = (df_l['cantidad'].sum() if not df_l.empty else 0) - (df_b['cantidad'].sum() if not df_b.empty else 0)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Aves Reales", f"{int(aves)} uds")
    c2.metric("Gastos Totales", f"{df_g['importe'].sum() if not df_g.empty else 0:.2f} €")
    c3.metric("Bajas", int(df_b['cantidad'].sum()) if not df_b.empty else 0)

# ---------------- 🥚 REGISTRO PUESTA ----------------
elif menu == "🥚 REGISTRO PUESTA":
    st.title("🥚 Producción Diaria")
    activos = conn.query("SELECT * FROM lotes WHERE estado='Activo'", ttl=0)
    df_pm = conn.query("SELECT * FROM puesta_manual", ttl=0)
    
    if activos.empty:
        st.warning("⚠️ No hay lotes activos. Ve a 'ALTA AVES'.")
    else:
        with st.form("f_puesta"):
            l_id = st.selectbox("Lote", activos['id'].tolist())
            tiene_f1 = not df_pm.empty and l_id in df_pm['lote_id'].values
            
            if not tiene_f1:
                f_ini = st.date_input("🌟 Fecha de Primera Puesta (Solo una vez)")
            else:
                fecha_f1 = df_pm[df_pm['lote_id']==l_id]['fecha_primera_puesta'].values[0]
                st.info(f"📅 Poniendo desde: {fecha_f1}")
            
            cant = st.number_input("Cantidad de Huevos", min_value=1)
            if st.form_submit_button("✅ GUARDAR"):
                with conn.session as s:
                    s.execute(text("INSERT INTO produccion (fecha, lote_id, cantidad, usuario) VALUES (:f, :l, :c, :u)"),
                              {"f": datetime.now().strftime('%d/%m/%Y'), "l": l_id, "c": int(cant), "u": st.session_state.user})
                    if not tiene_f1:
                        s.execute(text("INSERT INTO puesta_manual (lote_id, fecha_primera_puesta, usuario) VALUES (:l, :fp, :u)"),
                                  {"l": l_id, "fp": f_ini.strftime('%d/%m/%Y'), "u": st.session_state.user})
                    s.commit()
                st.success("Guardado en Supabase"); st.rerun()

# ---------------- 🐣 ALTA AVES ----------------
elif menu == "🐣 ALTA AVES":
    st.title("🐣 Registrar Nuevo Lote")
    with st.form("f_alta"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.text_input("Raza", value="Roja"); can = st.number_input("Cantidad", 1); ed = st.number_input("Edad (días)", 0)
        if st.form_submit_button("✅ CREAR LOTE"):
            with conn.session as s:
                s.execute(text("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (:f, :e, :r, :c, 'Activo', :ed, :u)"),
                          {"f": f.strftime('%d/%m/%Y'), "e": esp, "r": rz, "c": int(can), "ed": int(ed), "u": st.session_state.user})
                s.commit()
            st.success("Lote creado"); st.balloons(); st.rerun()

# ---------------- 📈 MADUREZ ----------------
elif menu == "📈 MADUREZ":
    st.title("📈 Control de Edad")
    df_l = conn.query("SELECT * FROM lotes WHERE estado='Activo'", ttl=0)
    if df_l.empty: st.info("No hay datos.")
    else:
        for _, r in df_l.iterrows():
            f_ini = datetime.strptime(r['fecha'], '%d/%m/%Y')
            edad = (datetime.now() - f_ini).days + r['edad_inicial']
            st.write(f"🏷️ **Lote {r['id']}**: {r['especie']} ({r['raza']}) - **{edad} días**")
            st.progress(min(1.0, edad/150))

# ---------------- 🛠️ ADMIN ----------------
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Panel Admin")
    if st.session_state.rango == 'Admin':
        if st.button("📥 Descargar Copia Excel"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ['lotes', 'gastos', 'produccion', 'bajas']:
                    conn.query(f"SELECT * FROM {t}", ttl=0).to_excel(writer, index=False, sheet_name=t)
            st.download_button("Click para descargar", output.getvalue(), "corral_cloud.xlsx")
    else: st.error("Sin acceso.")

