import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# =================================================================
# BLOQUE 1: MOTOR DE DATOS Y SEGURIDAD (V41.1)
# =================================================================
st.set_page_config(page_title="CORRAL IA TOTAL V41.1", layout="wide", page_icon="🚜")
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
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
        if n == "ventas":
            for col in ["unidades INTEGER", "ilos_finale REAL", "lote_id INTEGER"]:
                try: c.execute(f"ALTER TABLE ventas ADD COLUMN {col}")
                except: pass
        if n == "gastos":
            try: c.execute("ALTER TABLE gastos ADD COLUMN ilos_pienso REAL")
            except: pass
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: IA Y CONFIGURACIÓN
# =================================================================
CONFIG_IA = {
    "Roja": {"puesta": 1, "cons_base": 0.110, "consejo": "Alta puesta. Calcio vital."},
    "Blanca": {"puesta": 0.9, "cons_base": 0.105, "consejo": "Vuelan mucho."},
    "Mochuela": {"puesta": 0.85, "cons_base": 0.095, "consejo": "Muy rústica."},
    "Blanco Engorde": {"madurez": 55, "cons_base": 0.180, "consejo": "Crecimiento rápido."},
    "Campero": {"madurez": 90, "cons_base": 0.140, "consejo": "Sabor premium."}
}

def calcular_consumo_diario(raza, edad, cantidad):
    base = CONFIG_IA.get(raza, {}).get("cons_base", 0.120)
    factor = 0.3 if edad < 20 else (0.6 if edad < 45 else 1.0)
    return base * factor * cantidad

# =================================================================
# BLOQUE 3: DASHBOARD PROFESIONAL (SIN LIBRERÍAS EXTERNAS)
# =================================================================
def vista_dashboard(prod, ventas, gastos, lotes):
    st.title("🏠 Panel de Control Inteligente")
    
    # Cálculos Financieros
    v_cli = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    inv = gastos['cantidad'].sum() if not gastos.empty else 0
    
    # Cálculos Pienso
    total_pienso = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo_hoy = 0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_l).days + r["edad_inicial"]
            consumo_hoy += calcular_consumo_diario(r['raza'], edad, r['cantidad'])
    
    dias_restantes = total_pienso / consumo_hoy if consumo_hoy > 0 else 0

    # Métricas principales
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Caja (Ventas)", f"{v_cli:.2f} €")
    c2.metric("🏠 Ahorro Casa", f"{ahorro:.2f} €")
    c3.metric("💸 Inversión", f"{inv:.2f} €")
    c4.metric("🚀 Beneficio Neto", f"{(v_cli + ahorro) - inv:.2f} €")

    st.divider()

    col_izq, col_der = st.columns(2)
    
    with col_izq:
        st.subheader("📊 Inversión por Categoría")
        if not gastos.empty:
            g_cat = gastos.groupby('categoria')['cantidad'].sum()
            st.bar_chart(g_cat)
        else: st.info("No hay gastos para mostrar gráficos.")

    with col_der:
        st.subheader("🔋 Almacén y Stock")
        st.write(f"**Pienso en Almacén:** {total_pienso:.1f} kg")
        st.write(f"**Consumo Estimado hoy:** {consumo_hoy:.2f} kg/día")
        if dias_restantes < 5:
            st.error(f"⚠️ ¡ATENCIÓN! Solo queda pienso para {dias_restantes:.1f} días")
        else:
            st.success(f"✅ Stock seguro para {dias_restantes:.1f} días")

# =================================================================
# BLOQUE 4: PRODUCCIÓN, CRECIMIENTO Y OTROS
# =================================================================
def vista_produccion(prod, lotes):
    st.title("🥚 Producción y Eficiencia")
    if not lotes.empty:
        total_g = lotes[lotes['especie']=='Gallinas']['cantidad'].sum()
        hoy = datetime.now().strftime("%d/%m/%Y")
        h_hoy = prod[prod['fecha'] == hoy]['huevos'].sum() if not prod.empty else 0
        eficiencia = (h_hoy / total_g * 100) if total_g > 0 else 0
        st.metric("📈 Eficiencia de Puesta (Hoy)", f"{eficiencia:.1f} %")

    with st.form("f_prod"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos recogidos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()

def vista_crecimiento(lotes):
    st.title("📈 Historial Visual")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}"):
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            st.write(f"📅 Edad: {(datetime.now() - f_l).days + r['edad_inicial']} días")
            c1, c2 = st.columns(2)
            with c1: img_cam = st.camera_input(f"Foto Lote {r['id']}", key=f"c_{r['id']}")
            with c2: img_f = st.file_uploader("Subir archivo", type=['jpg','png'], key=f"f_{r['id']}")
            
            f_final = img_cam if img_cam else img_f
            if f_final and st.button(f"Guardar Foto {r['id']}", key=f"b_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", (r['id'], datetime.now().strftime("%d/%m/%Y"), f_final.read())).connection.commit(); st.rerun()
            
            df_fotos = cargar_tabla("fotos")
            if not df_fotos.empty:
                f_lote = df_fotos[df_fotos['lote_id'] == r['id']]
                cols = st.columns(4)
                for i, fr in f_lote.tail(4).iterrows(): cols[f_lote.tail(4).index.get_loc(i)].image(fr['imagen'], caption=fr['fecha'])

def vista_copias():
    st.title("💾 Backups")
    if st.button("📥 Crear Excel"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for t in ["lotes", "gastos", "produccion", "ventas"]: cargar_tabla(t).to_excel(writer, sheet_name=t, index=False)
        st.download_button(label="⬇️ Descargar", data=output.getvalue(), file_name="Corral_Backup.xlsx")
    
    arch = st.file_uploader("Restaurar Excel", type="xlsx")
    if arch and st.button("🚀 Restaurar"):
        data = pd.read_excel(arch, sheet_name=None); conn = get_conn()
        for t in ["lotes", "gastos", "produccion", "ventas"]:
            if t in data: conn.execute(f"DELETE FROM {t}"); data[t].to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.success("OK"); st.rerun()

# =================================================================
# NAVEGACIÓN
# =================================================================
inicializar_db()
lotes, ventas, prod, gastos = cargar_tabla("lotes"), cargar_tabla("ventas"), cargar_tabla("produccion"), cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard": vista_dashboard(prod, ventas, gastos, lotes)
elif menu == "📈 Crecimiento": vista_crecimiento(lotes)
elif menu == "🥚 Producción": vista_produccion(prod, lotes)
elif menu == "💰 Ventas":
    st.title("💰 Ventas")
    with st.form("v"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades", 1); k = st.number_input("Kg", 0.0); p = st.number_input("€", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), "Genérico", tipo, p, l, k, u)).connection.commit(); st.rerun()
elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Animales", "Medicina", "Otros"]); con = st.text_input("Concepto")
        i = st.number_input("€", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg)).connection.commit(); st.rerun()
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    for rz, info in CONFIG_IA.items():
        if "madurez" in info: st.success(f"📌 {rz}: Comprar antes de {(datetime(2026,12,20) - timedelta(days=info['madurez'])).strftime('%d/%m/%Y')}")
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Alta")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad", 0); pr = st.number_input("Precio", 0.0)
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()
elif menu == "💾 Copias": vista_copias()
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
