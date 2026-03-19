import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL IA ELITE V18.3", layout="wide", page_icon="🤖")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_y_migrar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, kilos_finales REAL, unidades INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, perdida_estimada REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS hitos(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT)")
    
    # Verificación de columnas (Migración en vivo)
    cols_v = [col[1] for col in c.execute("PRAGMA table_info(ventas)")]
    if "unidades" not in cols_v: c.execute("ALTER TABLE ventas ADD COLUMN unidades INTEGER DEFAULT 1")
    if "kilos_finales" not in cols_v: c.execute("ALTER TABLE ventas ADD COLUMN kilos_finales REAL DEFAULT 0")
    conn.commit(); conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

inicializar_y_migrar_db()

# ====================== 2. MOTOR IA BIOLÓGICA ======================
lotes = cargar("lotes"); gastos = cargar("gastos"); ventas = cargar("ventas")
bajas = cargar("bajas"); hitos = cargar("hitos"); produccion = cargar("produccion")

DICC_IA = {
    "Roja": {"puesta_dias": 145, "cons_adulto": 0.120},
    "Blanca": {"puesta_dias": 140, "cons_adulto": 0.115},
    "Chocolate": {"puesta_dias": 160, "cons_adulto": 0.130},
    "Mochuela (Pintada)": {"puesta_dias": 210, "cons_adulto": 0.100},
    "Blanco Engorde": {"madurez_dias": 55, "cons_adulto": 0.210},
    "Campero": {"madurez_dias": 90, "cons_adulto": 0.150},
    "Codorniz": {"puesta_dias": 45, "cons_adulto": 0.035}
}

def obtener_consumo_diario(raza, edad_dias):
    base = DICC_IA.get(raza, {"cons_adulto": 0.110})
    ca = base.get("cons_adulto", 0.110)
    if edad_dias < 30: return ca * 0.4
    if edad_dias < 90: return ca * 0.75
    return ca

def calc_stock(cat, esp):
    kg_c = gastos[gastos['categoria'] == cat]['kilos_pienso'].sum() if not gastos.empty else 0
    cons_tot = 0
    if not lotes.empty:
        for _, r in lotes[lotes['especie'] == esp].iterrows():
            vivas = max(0, r['cantidad'] - (bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0))
            d_v = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days
            for d in range(d_v + 1):
                cons_tot += vivas * obtener_consumo_diario(r["raza"], r["edad_inicial"] + d)
    return max(0, kg_c - cons_tot)

# ====================== 3. INTERFAZ ======================
seccion = st.sidebar.radio("MENÚ IA:", [
    "🏠 Dashboard", "📈 IA Crecimiento", "🥚 Producción", "🌟 Primera Puesta",
    "💰 Ventas", "🎄 IA Navidad", "🐣 Alta Lotes", "💸 Gastos", "💀 Bajas", 
    "📜 Histórico", "💾 EXPORTAR/SEGURIDAD"
])

if seccion == "🏠 Dashboard":
    st.title("🏠 Dashboard")
    col1, col2, col3 = st.columns(3)
    col1.metric("Pienso Gallinas", f"{calc_stock('Pienso Gallinas', 'Gallinas'):.1f} kg")
    col2.metric("Pienso Pollos", f"{calc_stock('Pienso Pollos', 'Pollos'):.1f} kg")
    col3.metric("Pienso Codornices", f"{calc_stock('Pienso Codornices', 'Codornices'):.1f} kg")
    if not produccion.empty:
        st.subheader("📊 Producción (Últimos 15 días)")
        st.bar_chart(produccion.tail(15).set_index('fecha')['huevos'])

elif seccion == "📈 IA Crecimiento":
    st.title("📈 IA de Crecimiento")
    for _, r in lotes.iterrows():
        edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
        info = DICC_IA.get(r["raza"], {"puesta_dias": 150, "madurez_dias": 90})
        meta = info.get("puesta_dias") if "puesta_dias" in info else info.get("madurez_dias")
        porc = min(100, int((edad/meta)*100))
        ya_pone = "🥚" if not hitos[(hitos['lote_id']==r['id']) & (hitos['tipo']=='Primera Puesta')].empty else ""
        st.write(f"**Lote {r['id']} - {r['raza']}** {ya_pone} ({edad} días)")
        st.progress(porc/100)
        if porc < 100:
            f_est = datetime.now() + timedelta(days=meta-edad)
            st.warning(f"IA estima madurez el: {f_est.strftime('%d/%m/%Y')} (Faltan {meta-edad} días)")

elif seccion == "🥚 Producción":
    st.title("🥚 Producción")
    with st.form("p"):
        f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        cant = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l_id, cant)).connection.commit(); st.rerun()

elif seccion == "🌟 Primera Puesta":
    st.title("🌟 Hito: Primera Puesta")
    with st.form("h"):
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        f_h = st.date_input("Fecha")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?, 'Primera Puesta', ?)", (int(l_id), f_h.strftime("%d/%m/%Y"))).connection.commit(); st.rerun()

elif seccion == "💰 Ventas":
    st.title("💰 Ventas (Unidades y Peso)")
    with st.form("v"):
        f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        uds = c1.number_input("Unidades", 1); kgs = c2.number_input("Kilos", 0.0); pr = c3.number_input("Precio €", 0.0)
        cli = st.text_input("Cliente"); conc = st.text_input("Concepto")
        if st.form_submit_button("Guardar Venta"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad, lote_id, kilos_finales, unidades) VALUES (?,?,'Venta Cliente',?,?,?,?,?)", 
                               (f.strftime("%d/%m/%Y"), cli, conc, pr, int(l_id), kgs, uds)).connection.commit(); st.rerun()

elif seccion == "🎄 IA Navidad":
    st.title("🎄 Planificador Navidad")
    f_obj = datetime(datetime.now().year, 12, 20)
    for r in ["Blanco Engorde", "Campero"]:
        info = DICC_IA[r]; f_c = f_obj - timedelta(days=info['madurez_dias'])
        st.info(f"**{r}**: Comprar el {f_c.strftime('%d/%m')}. Consumo medio: {info['madurez_dias']*info['cons_adulto']*0.7:.1f} kg/ave.")

elif seccion == "🐣 Alta Lotes":
    st.title("🐣 Alta Lotes")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", list(DICC_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cant", 1); ed = c2.number_input("Edad inicial", 0); pr = c3.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

elif seccion == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Cat", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("€", 0.0); kg = st.number_input("Kg", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

elif seccion == "📜 Histórico":
    st.title("📜 Histórico")
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        id_del = st.number_input("Eliminar ID", 0)
        if st.button("Borrar Registro"):
            get_conn().execute(f"DELETE FROM {t} WHERE id=?", (id_del,)).connection.commit(); st.rerun()

elif seccion == "💾 EXPORTAR/SEGURIDAD":
    st.title("💾 Exportar")
    try:
        import xlsxwriter
        if st.button("📊 Exportar Excel"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                for t in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                    cargar(t).to_excel(wr, sheet_name=t, index=False)
            st.download_button("📥 Descargar Excel", out.getvalue(), "corral.xlsx")
    except:
        st.error("⚠️ Falta 'xlsxwriter'. Sube el requirements.txt a GitHub.")
    
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 Descargar DB (.db)", f, "corral.db")
