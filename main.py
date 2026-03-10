import streamlit as st
from sqlalchemy import text

# Intentar conectar
conn = st.connection("postgresql", type="sql")

try:
    with conn.session as s:
        s.execute(text("SELECT 1"))
    st.success("✅ ¡Conexión exitosa con Supabase!")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")

# 1. CONFIGURACIÓN VISUAL
st.set_page_config(page_title="CORRAL MAESTRO CLOUD", layout="wide", page_icon="🐓")

# ====================== 2. CONEXIÓN A SUPABASE ======================
# Esta línea busca la URL que pegaste en los "Secrets" de Streamlit
conn = st.connection("postgresql", type="sql")

def inicializar_db_nube():
    with conn.session as s:
        # Creamos las tablas en la nube si no existen
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
        
        # Usuario admin por defecto (admin / 1234)
        s.execute(text("INSERT INTO usuarios (nombre, clave, rango) VALUES ('admin', '1234', 'Admin') ON CONFLICT (nombre) DO NOTHING"))
        s.commit()

# Intentar conectar. Si falla, avisará que faltan los Secrets.
try:
    inicializar_db_nube()
except Exception as e:
    st.error("⚠️ Error de conexión. Revisa si pegaste bien la URL en los Secrets de Streamlit.")
    st.stop()

# ====================== 3. CONTROL DE ACCESO ======================
if 'auth' not in st.session_state:
    st.session_state.update({'auth': False, 'user': "", 'rango': ""})

if not st.session_state.auth:
    st.title("🔐 Acceso al Corral Cloud")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("ENTRAR"):
            res = conn.query(f"SELECT nombre, rango FROM usuarios WHERE nombre='{u}' AND clave='{p}'", ttl=0)
            if not res.empty:
                st.session_state.update({'auth': True, 'user': res.iloc[0]['nombre'], 'rango': res.iloc[0]['rango']})
                st.rerun()
            else: st.error("Usuario o clave incorrectos")
    st.stop()

# ====================== 4. NAVEGACIÓN ======================
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
    st.title("🏠 Estado del Corral (Nube)")
    df_l = conn.query("SELECT * FROM lotes", ttl=0)
    df_g = conn.query("SELECT * FROM gastos", ttl=0)
    df_b = conn.query("SELECT * FROM bajas", ttl=0)
    
    aves = (df_l['cantidad'].sum() if not df_l.empty else 0) - (df_b['cantidad'].sum() if not df_b.empty else 0)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Aves Reales", f"{int(aves)} uds")
    c2.metric("Gastos Totales", f"{df_g['importe'].sum() if not df_g.empty else 0:.2f} €")
    c3.metric("Bajas registradas", int(df_b['cantidad'].sum()) if not df_b.empty else 0)

# ---------------- 🥚 REGISTRO PUESTA ----------------
elif menu == "🥚 REGISTRO PUESTA":
    st.title("🥚 Producción Diaria")
    activos = conn.query("SELECT * FROM lotes WHERE estado='Activo'", ttl=0)
    df_pm = conn.query("SELECT * FROM puesta_manual", ttl=0)
    
    if activos.empty:
        st.warning("Primero debes dar de alta un lote en '🐣 ALTA AVES'")
    else:
        with st.form("f_puesta"):
            l_id = st.selectbox("Seleccione el Lote", activos['id'].tolist())
            
            # Lógica de primera puesta
            tiene_f1 = not df_pm.empty and l_id in df_pm['lote_id'].values
            if not tiene_f1:
                f_ini = st.date_input("🌟 Fecha de Primera Puesta (Solo se pide una vez)")
            else:
                fecha_guardada = df_pm[df_pm['lote_id']==l_id]['fecha_primera_puesta'].values[0]
                st.info(f"📅 Este lote inició su puesta el: {fecha_guardada}")
            
            cant = st.number_input("Huevos recogidos hoy", min_value=1)
            
            if st.form_submit_button("✅ CONFIRMAR REGISTRO"):
                with conn.session as s:
                    # Guardar producción
                    s.execute(text("INSERT INTO produccion (fecha, lote_id, cantidad, usuario) VALUES (:f, :l, :c, :u)"),
                              {"f": datetime.now().strftime('%d/%m/%Y'), "l": l_id, "c": cant, "u": st.session_state.user})
                    # Guardar primera puesta si es nuevo
                    if not tiene_f1:
                        s.execute(text("INSERT INTO puesta_manual (lote_id, fecha_primera_puesta, usuario) VALUES (:l, :fp, :u)"),
                                  {"l": l_id, "fp": f_ini.strftime('%d/%m/%Y'), "u": st.session_state.user})
                    s.commit()
                st.success("¡Datos guardados en la nube!"); st.rerun()

# ---------------- 📈 MADUREZ ----------------
elif menu == "📈 MADUREZ":
    st.title("📈 Control de Edad y Madurez")
    df_l = conn.query("SELECT * FROM lotes WHERE estado='Activo'", ttl=0)
    df_pm = conn.query("SELECT * FROM puesta_manual", ttl=0)
    
    if df_l.empty: st.info("No hay lotes activos.")
    for _, r in df_l.iterrows():
        f_llegada = datetime.strptime(r['fecha'], '%d/%m/%Y')
        edad = (datetime.now() - f_llegada).days + r['edad_inicial']
        st.subheader(f"Lote {r['id']} - {r['especie']} {r['raza']}")
        st.write(f"🎂 Edad: **{edad} días**")
        
        if not df_pm.empty and r['id'] in df_pm['lote_id'].values:
            st.success(f"🥚 En producción desde: {df_pm[df_pm['lote_id']==r['id']]['fecha_primera_puesta'].values[0]}")
        
        st.progress(min(1.0, edad/150)) # Barra de progreso hasta los 150 días
        st.divider()

# ---------------- 🐣 ALTA AVES ----------------
elif menu == "🐣 ALTA AVES":
    st.title("🐣 Registrar Nuevo Lote")
    with st.form("f_alta"):
        f = st.date_input("Fecha de entrada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices", "Patos"])
        rz = st.text_input("Raza", value="Roja")
        can = st.number_input("Cantidad de aves", min_value=1)
        ed = st.number_input("Edad inicial (días)", 0)
        
        if st.form_submit_button("✅ CREAR LOTE PERMANENTE"):
            with conn.session as s:
                s.execute(text("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (:f, :e, :r, :c, 'Activo', :ed, :u)"),
                          {"f": f.strftime('%d/%m/%Y'), "e": esp, "r": rz, "c": can, "ed": ed, "u": st.session_state.user})
                s.commit()
            st.success("Lote registrado correctamente"); st.balloons(); st.rerun()

# ---------------- ☠️ REPORTAR BAJA ----------------
elif menu == "☠️ REPORTAR BAJA":
    st.title("☠️ Registro de Bajas")
    df_l = conn.query("SELECT * FROM lotes", ttl=0)
    if df_l.empty: st.warning("No hay animales.")
    else:
        with st.form("f_bajas"):
            l_id = st.selectbox("Lote afectado", df_l['id'].tolist())
            c_baja = st.number_input("Cantidad", min_value=1)
            mot = st.selectbox("Motivo", ["Enfermedad", "Depredador", "Accidente", "Otro"])
            if st.form_submit_button("❌ CONFIRMAR BAJA"):
                with conn.session as s:
                    s.execute(text("INSERT INTO bajas (fecha, lote_id, cantidad, motivo, usuario) VALUES (:f, :l, :c, :m, :u)"),
                              {"f": datetime.now().strftime('%d/%m/%Y'), "l": l_id, "c": c_baja, "m": mot, "u": st.session_state.user})
                    s.commit()
                st.error("Baja registrada."); st.rerun()

# ---------------- 💸 GASTOS ----------------
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    with st.form("f_gastos"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Infraestructura", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("💰 GUARDAR GASTO"):
            with conn.session as s:
                s.execute(text("INSERT INTO gastos (fecha, concepto, importe, categoria, usuario) VALUES (:f, :c, :i, :cat, :u)"),
                          {"f": f.strftime('%d/%m/%Y'), "c": con, "i": imp, "cat": cat, "u": st.session_state.user})
                s.commit()
            st.success("Gasto anotado"); st.rerun()

# ---------------- 🎄 PLAN NAVIDAD ----------------
elif menu == "🎄 PLAN NAVIDAD":
    st.title("🎄 Planificación Navidad 2026")
    tipo = st.radio("Tipo de ave", ["Pollo Campero (95 días)", "Pollo Blanco (60 días)"])
    dias = 95 if "Campero" in tipo else 60
    f_compra = datetime(2026, 12, 24) - timedelta(days=dias)
    st.success(f"📅 Para Navidad, compra los pollitos el: **{f_compra.strftime('%d/%m/%Y')}**")

# ---------------- 🛠️ ADMIN ----------------
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Panel de Control")
    if st.session_state.rango == 'Admin':
        if st.button("📥 Generar Copia de Seguridad Excel"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ['lotes', 'gastos', 'produccion', 'bajas', 'puesta_manual']:
                    conn.query(f"SELECT * FROM {t}", ttl=0).to_excel(writer, index=False, sheet_name=t)
            st.download_button("Descargar Excel", output.getvalue(), "corral_backup.xlsx")
    else: st.error("No tienes permisos de administrador.")

