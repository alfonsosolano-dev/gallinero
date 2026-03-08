import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
import os
from datetime import datetime, timedelta

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

# ====================== 2. BASE DE DATOS ======================
if not os.path.exists('data'):
    os.makedirs('data')

DB_PATH = './data/corral_final_consolidado.db'

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, kilos REAL DEFAULT 0, categoria TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, total REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS salud (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote_id INTEGER, tipo TEXT, notas TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, clave TEXT, rango TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual (id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha_primera_puesta TEXT, usuario TEXT)''')
    
    # Parche de seguridad para columnas
    for tabla in ['lotes', 'gastos', 'ventas', 'produccion', 'salud', 'puesta_manual']:
        try: c.execute(f"ALTER TABLE {tabla} ADD COLUMN usuario TEXT")
        except: pass
            
    c.execute("INSERT OR IGNORE INTO usuarios (nombre, clave, rango) VALUES (?,?,?)", ('admin', '1234', 'Admin'))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 3. SESIÓN Y LOGIN ======================
if 'autenticado' not in st.session_state:
    st.session_state.update({'autenticado': False, 'usuario': "", 'rango': ""})

if not st.session_state['autenticado']:
    st.sidebar.title("🔐 Acceso Sistema")
    with st.sidebar.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT rango FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                st.session_state.update({'autenticado': True, 'usuario': u, 'rango': res[0]})
                st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

# ====================== 4. FUNCIONES AUXILIARES ======================
def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()
    finally: conn.close()

# ====================== 5. NAVEGACIÓN ======================
st.sidebar.button("Cerrar Sesión", on_click=lambda: st.session_state.update({'autenticado': False}))
menu = st.sidebar.radio("MENÚ PRINCIPAL", ["🏠 DASHBOARD", "🐣 ALTA DE AVES", "🥚 REGISTRO PUESTA", "📈 MADUREZ Y CRECIMIENTO", "💸 GASTOS", "💰 VENTAS", "💉 SALUD", "🎄 NAVIDAD", "🛠️ ADMIN"])

# ---------------- ALTA DE AVES (FORMULARIO ESTRUCTURADO) ----------------
if menu == "🐣 ALTA DE AVES":
    st.title("🐣 Entrada de Nuevo Lote")
    st.info("Complete los datos del nuevo lote. El botón de abajo confirmará el ingreso permanente.")
    
    with st.form("form_alta_aves"):
        col1, col2 = st.columns(2)
        with col1:
            f_alta = st.date_input("Fecha de Ingreso")
            especie_alta = st.selectbox("Especie", ["Gallina Ponedora", "Pollo de Engorde", "Codorniz", "Pavo", "Pato"])
            raza_alta = st.selectbox("Raza", ["Isabrown", "Leghorn", "Campero", "Blanco", "Gigante de Jersey", "Japónica", "Otra"])
            if raza_alta == "Otra":
                raza_alta = st.text_input("Especifique la Raza")
        
        with col2:
            cantidad_alta = st.number_input("Cantidad de Aves", min_value=1, value=10)
            edad_alta = st.number_input("Edad Actual (Días)", min_value=0, value=0)
            notas_alta = st.text_area("Notas Adicionales")

        st.markdown("---")
        confirmar_alta = st.form_submit_button("✅ CONFIRMAR ENTRADA DE LOTE")
        
        if confirmar_alta:
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado, edad_inicial, usuario) VALUES (?,?,?,?,?,?,?)",
                      (f_alta.strftime('%d/%m/%Y'), especie_alta, raza_alta, cantidad_alta, 'Activo', edad_alta, st.session_state['usuario']))
            conn.commit(); conn.close()
            st.success(f"Lote de {cantidad_alta} {especie_alta} ({raza_alta}) registrado con éxito.")
            st.balloons()

# ---------------- PUESTA (CON SELECTOR DE LOTE Y PRIMERA PUESTA) ----------------
elif menu == "🥚 REGISTRO PUESTA":
    st.title("🥚 Producción Diaria")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    activos = df_l[df_l['estado']=='Activo']
    
    if activos.empty:
        st.warning("No hay lotes registrados para producir huevos.")
    else:
        with st.form("form_puesta"):
            # Generar etiqueta para el selector: "ID - Raza - Especie"
            lista_lotes = activos.apply(lambda x: f"Lote {x['id']}: {x['raza']} ({x['especie']})", axis=1).tolist()
            lote_label = st.selectbox("Seleccione el Lote productor", lista_lotes)
            l_id = int(lote_label.split(":")[0].replace("Lote ", ""))
            
            # Verificación de primera puesta
            tiene_f1 = not df_pm.empty and l_id in df_pm['lote_id'].values
            
            if not tiene_f1:
                st.subheader("🌟 Registro de Madurez")
                f_primera = st.date_input("Fecha del primer huevo de este lote", help="Solo se guardará una vez")
            else:
                f_p_guardada = df_pm[df_pm['lote_id']==l_id]['fecha_primera_puesta'].values[0]
                st.info(f"📅 Este lote inició su vida productiva el: {f_p_guardada}")

            cant_huevos = st.number_input("Cantidad de Huevos Recogidos", min_value=1)
            
            confirmar_puesta = st.form_submit_button("🚀 CONFIRMAR REGISTRO DE HUEVOS")
            
            if confirmar_puesta:
                conn = get_conn(); c = conn.cursor()
                datos_l = activos[activos['id']==l_id].iloc[0]
                # Guardar producción
                c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie, usuario) VALUES (?,?,?,?,?)",
                          (datetime.now().strftime('%d/%m/%Y'), datos_l['raza'], cant_huevos, datos_l['especie'], st.session_state['usuario']))
                # Guardar fecha inicial si no existe
                if not tiene_f1:
                    c.execute("INSERT INTO puesta_manual (lote_id, fecha_primera_puesta, usuario) VALUES (?,?,?)",
                              (l_id, f_primera.strftime('%d/%m/%Y'), st.session_state['usuario']))
                conn.commit(); conn.close()
                st.success("Producción registrada.")
                st.rerun()

# ---------------- GASTOS (CATEGORÍAS CLARAS) ----------------
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Compras y Gastos")
    with st.form("form_gastos"):
        f_gasto = st.date_input("Fecha de Compra")
        cat_gasto = st.selectbox("Categoría de Gasto", ["Alimentación (Pienso)", "Salud y Vacunas", "Infraestructura", "Suministros (Agua/Luz)", "Compra de Aves", "Otros"])
        concepto_gasto = st.text_input("Concepto (Ej: Saco 25kg Pienso Inicio)")
        importe_gasto = st.number_input("Importe Total (€)", min_value=0.0, format="%.2f")
        kilos_gasto = st.number_input("Kilos (si aplica)", min_value=0.0)
        
        confirmar_gasto = st.form_submit_button("💰 REGISTRAR GASTO")
        
        if confirmar_gasto:
            conn = get_conn(); c = conn.cursor()
            c.execute("INSERT INTO gastos (fecha, concepto, importe, kilos, categoria, usuario) VALUES (?,?,?,?,?,?)",
                      (f_gasto.strftime('%d/%m/%Y'), concepto_gasto, importe_gasto, kilos_gasto, cat_gasto, st.session_state['usuario']))
            conn.commit(); conn.close()
            st.success("Gasto guardado en el historial.")
            st.rerun()

# ---------------- DASHBOARD (GRÁFICOS) ----------------
elif menu == "🏠 DASHBOARD":
    st.title("🏠 Panel de Control General")
    df_l = cargar('lotes'); df_v = cargar('ventas'); df_g = cargar('gastos')
    
    col_a, col_b, col_c = st.columns(3)
    with col_a: st.metric("Stock Aves", int(df_l['cantidad'].sum()) if not df_l.empty else 0)
    with col_b: st.metric("Ventas Totales", f"{df_v['total'].sum() if not df_v.empty else 0:.2f}€")
    with col_c: st.metric("Gastos Totales", f"{df_g['importe'].sum() if not df_g.empty else 0:.2f}€")
    
    if not df_g.empty:
        st.plotly_chart(px.pie(df_g, values='importe', names='categoria', title="Análisis de Gastos por Categoría"), use_container_width=True)

# ---------------- RESTO DE SECCIONES (SIMPLIFICADAS PARA ESTE BLOQUE) ----------------
elif menu == "📈 MADUREZ Y CRECIMIENTO":
    st.title("📈 Control de Edad y Madurez")
    df_l = cargar('lotes'); df_pm = cargar('puesta_manual')
    if not df_l.empty:
        for _, r in df_l[df_l['estado']=='Activo'].iterrows():
            f_llegada = datetime.strptime(r['fecha'], '%d/%m/%Y')
            edad = (datetime.now() - f_llegada).days + r['edad_inicial']
            st.subheader(f"{r['especie']} - {r['raza']}")
            st.write(f"🎂 **{edad} días de edad**")
            if not df_pm.empty and r['id'] in df_pm['lote_id'].values:
                st.success(f"🥚 En producción desde: {df_pm[df_pm['lote_id']==r['id']]['fecha_primera_puesta'].values[0]}")
            st.progress(min(1.0, edad/150))
            st.divider()

elif menu == "🎄 NAVIDAD":
    st.title("🎄 Planificación Campaña Navidad")
    tipo_nav = st.radio("Tipo de Ave para Navidad", ["Pollo Campero (95 días de engorde)", "Pollo Blanco (60 días de engorde)"])
    dias_nav = 95 if "Campero" in tipo_nav else 60
    f_compra_nav = datetime(2026, 12, 24) - timedelta(days=dias_nav)
    st.success(f"📅 Para llegar al 24 de diciembre, compra tus pollitos el: **{f_compra_nav.strftime('%d/%m/%Y')}**")

elif menu == "🛠️ ADMIN":
    if st.session_state['rango'] != 'Admin':
        st.error("Acceso restringido a Administradores.")
    else:
        st.title("🛠️ Gestión del Sistema")
        # Sección de creación de usuarios y backup Excel...
        st.write("Panel de administrador activo.")
        if st.button("📥 Generar Copia de Seguridad Excel"):
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                for t in ['lotes','gastos','ventas','produccion','salud','usuarios','puesta_manual']:
                    df_exp = cargar(t)
                    if not df_exp.empty: df_exp.to_excel(wr, sheet_name=t, index=False)
            st.download_button("Descargar Backup", buf.getvalue(), "corral_pro_backup.xlsx")
