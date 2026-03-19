import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# =================================================================
# BLOQUE 1: MOTOR DE DATOS (PROTECCIÓN TOTAL)
# =================================================================
st.set_page_config(page_title="CORRAL IA V34.0", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items(): c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn:
            df = pd.read_sql(f"SELECT * FROM {t}", conn)
            if t == "gastos" and not df.empty and 'ilos_pienso' not in df.columns:
                df['ilos_pienso'] = 0.0
            return df
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: IA Y LÓGICA DE CRECIMIENTO/CONSUMO
# =================================================================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons_base": 0.110, "consejo": "Alta puesta. Revisa calcio."},
    "Blanca": {"puesta": 140, "cons_base": 0.105, "consejo": "Vuelan mucho. Vallado alto."},
    "Mochuela": {"puesta": 210, "cons_base": 0.095, "consejo": "Rústica y resistente."},
    "Blanco Engorde": {"madurez": 55, "cons_base": 0.180, "consejo": "Crecimiento rápido."},
    "Campero": {"madurez": 90, "cons_base": 0.140, "consejo": "Sabor top. Necesita campo."}
}

def calcular_consumo_diario(raza, edad, cantidad):
    base = CONFIG_IA.get(raza, {}).get("cons_base", 0.120)
    factor = 0.3 if edad < 20 else (0.6 if edad < 45 else 1.0)
    return base * factor * cantidad

# =================================================================
# BLOQUE 3: VISTAS MODULARES (TODAS LAS SECCIONES)
# =================================================================

def vista_dashboard(prod, ventas, gastos, lotes):
    st.title("🏠 Panel de Control Maestro")
    
    # Alerta de Stock Protegida
    total_pienso = 0
    if not gastos.empty and 'ilos_pienso' in gastos.columns:
        total_pienso = gastos['ilos_pienso'].sum()
    
    if total_pienso < 10:
        st.error(f"⚠️ Alerta Stock Pienso: {total_pienso:.1f} kg (Comprar pronto)")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Huevos", f"{int(prod['huevos'].sum()) if not prod.empty else 0}")
    
    ingresos = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    c2.metric("Caja Real", f"{ingresos:.2f} €")
    
    consumo_hoy = 0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
                edad = (datetime.now() - f_lote).days + r["edad_inicial"]
                consumo_hoy += calcular_consumo_diario(r['raza'], edad, r['cantidad'])
            except: pass
    c3.metric("Consumo Hoy", f"{consumo_hoy:.2f} kg")
    c4.metric("Inversión", f"{gastos['cantidad'].sum() if not gastos.empty else 0:.2f} €")
    
    if not prod.empty:
        st.subheader("📈 Histórico de Puesta")
        st.line_chart(prod.tail(20).set_index('fecha')['huevos'])

def vista_crecimiento(lotes):
    st.title("📈 Seguimiento de Crecimiento")
    if lotes.empty: st.warning("No hay lotes."); return
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}", expanded=True):
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_lote).days + r["edad_inicial"]
            st.write(f"📅 **Edad:** {edad} días | **Consumo diario est.:** {calcular_consumo_diario(r['raza'], edad, r['cantidad']):.2f} kg")
            
            c1, c2 = st.columns(2)
            with c1:
                img_cam = st.camera_input(f"Captura {r['id']}", key=f"c_{r['id']}")
            with c2:
                img_file = st.file_uploader("Subir foto histórica", type=['jpg','png','jpeg'], key=f"f_{r['id']}")
                f_f = st.date_input("Fecha foto", datetime.now(), key=f"d_{r['id']}")
            
            img_save = img_cam if img_cam else img_file
            if img_save and st.button(f"Guardar Foto Lote {r['id']}", key=f"b_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                   (r['id'], f_f.strftime("%d/%m/%Y"), img_save.read())).connection.commit()
                st.success("Foto guardada."); st.rerun()

def vista_produccion(lotes):
    st.title("🥚 Registro de Producción")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()

def vista_ventas(lotes):
    st.title("💰 Ventas y Salidas")
    with st.form("v"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades", 1); k = st.number_input("Kg (ilos_finale)", 0.0); p = st.number_input("€ Total", 0.0)
        cli = st.text_input("Cliente/Destino")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()

def vista_gastos():
    st.title("💸 Compras y Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Infraestructura", "Otros"])
        con = st.text_input("Concepto"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg)).connection.commit(); st.rerun()

def vista_navidad():
    st.title("🎄 Planificador Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    for rz, info in CONFIG_IA.items():
        if "madurez" in info:
            f_c = f_obj - timedelta(days=info['madurez'])
            st.success(f"📌 **{rz}**: Comprar antes del {f_c.strftime('%d/%m/%Y')}")

def vista_alta():
    st.title("🐣 Alta de Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad inicial", 0); pr = st.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Crear Lote"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

def vista_copias():
    st.title("💾 Gestión de Copias")
    arch = st.file_uploader("Sube Excel de Backup", type=["xlsx"])
    if arch and st.button("🚀 INICIAR RESTAURACIÓN"):
        try:
            data = pd.read_excel(arch, sheet_name=None)
            conn = get_conn()
            for t, df in data.items():
                if t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
                    conn.execute(f"DELETE FROM {t}"); df.to_sql(t, conn, if_exists='append', index=False)
            conn.commit(); st.success("Sistema restaurado con éxito."); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# =================================================================
# BLOQUE 4: NAVEGACIÓN PRINCIPAL
# =================================================================
inicializar_db()
lotes = cargar_tabla("lotes"); ventas = cargar_tabla("ventas")
prod = cargar_tabla("produccion"); gastos = cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard": vista_dashboard(prod, ventas, gastos, lotes)
elif menu == "📈 Crecimiento": vista_crecimiento(lotes)
elif menu == "🥚 Producción": vista_produccion(lotes)
elif menu == "💰 Ventas": vista_ventas(lotes)
elif menu == "💸 Gastos": vista_gastos()
elif menu == "🎄 Navidad": vista_navidad()
elif menu == "🐣 Alta Lotes": vista_alta()
elif menu == "💾 Copias": vista_copias()
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas"])
    df_h = cargar_tabla(t)
    st.dataframe(df_h, use_container_width=True)
    id_del = st.number_input("ID a borrar", 0)
    if st.button("Eliminar Registro"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={id_del}").connection.commit(); st.rerun()
