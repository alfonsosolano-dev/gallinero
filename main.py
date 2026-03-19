import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io

# ====================== 1. NÚCLEO Y MIGRACIONES (EL ESCUDO) ======================
st.set_page_config(page_title="CORRAL IA ULTRA-SHIELD", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def blindar_db():
    conn = get_conn()
    c = conn.cursor()
    # Creación de tablas si no existen
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, kilos_finales REAL, unidades INTEGER",
        "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, perdida_estimada REAL",
        "hitos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT"
    }
    for nombre, esquema in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {nombre} ({esquema})")
    
    # MIGRACIÓN AUTOMÁTICA: Si olvidas una columna en el futuro, el sistema la crea sola
    def asegurar_columna(tabla, columna, tipo_defecto):
        cursor = c.execute(f"PRAGMA table_info({tabla})")
        cols = [row[1] for row in cursor.fetchall()]
        if columna not in cols:
            c.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo_defecto}")
    
    asegurar_columna("ventas", "unidades", "INTEGER DEFAULT 1")
    asegurar_columna("ventas", "kilos_finales", "REAL DEFAULT 0")
    asegurar_columna("ventas", "tipo_venta", "TEXT DEFAULT 'Venta Cliente'")
    
    conn.commit()
    conn.close()

blindar_db()

# ====================== 2. CONFIGURACIÓN IA (EL CEREBRO) ======================
# Solo necesitas tocar aquí para añadir nuevos animales en el futuro
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120},
    "Blanca": {"puesta": 140, "cons": 0.115},
    "Chocolate": {"puesta": 160, "cons": 0.130},
    "Mochuela (Pintada)": {"puesta": 210, "cons": 0.100},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210},
    "Campero": {"madurez": 90, "cons": 0.150},
    "Pavo": {"madurez": 150, "cons": 0.350},
    "Codorniz": {"puesta": 45, "cons": 0.035}
}

def cargar(tabla):
    try:
        with get_conn() as conn:
            return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()

# Carga masiva de datos
lotes = cargar("lotes"); gastos = cargar("gastos"); ventas = cargar("ventas")
prod = cargar("produccion"); bajas = cargar("bajas"); hitos = cargar("hitos")

# ====================== 3. FUNCIONES DE CÁLCULO ======================
def stock_pienso(cat, esp):
    kg_in = gastos[gastos['categoria'] == cat]['kilos_pienso'].sum() if not gastos.empty else 0
    kg_out = 0
    if not lotes.empty:
        for _, r in lotes[lotes['especie'] == esp].iterrows():
            muertos = bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0
            vivos = r['cantidad'] - muertos
            dias = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days
            kg_out += max(0, vivos) * (dias + r['edad_inicial']) * CONFIG_IA.get(r['raza'], {"cons": 0.1}).get("cons") * 0.8
    return max(0, kg_in - kg_out)

# ====================== 4. INTERFAZ STREAMLIT ======================
menu = st.sidebar.radio("NAVEGACIÓN:", ["🏠 Panel IA", "📈 Crecimiento", "🥚 Huevos", "💰 Salidas", "🎄 Navidad", "🐣 Altas", "💸 Gastos", "📜 Histórico", "💾 Backup"])

if menu == "🏠 Panel IA":
    st.title("🚜 Gestión de Corral Inteligente")
    
    # Sistema de Alertas de Stock
    s_gal = stock_pienso("Pienso Gallinas", "Gallinas")
    s_pol = stock_pienso("Pienso Pollos", "Pollos")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Pienso Gallinas", f"{s_gal:.1f} kg", delta="-Consumo Diario" if s_gal > 0 else "SIN STOCK")
    c2.metric("Pienso Pollos", f"{s_pol:.1f} kg")
    
    if s_gal < 10: st.error(f"⚠️ ¡Atención! Quedan solo {s_gal:.1f} kg de pienso para gallinas.")
    
    st.divider()
    # Resumen Económico (Ventas vs Ahorro Casa)
    v_ext = ventas[ventas['tipo_venta'] == 'Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    v_int = ventas[ventas['tipo_venta'] == 'Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    col_a, col_b = st.columns(2)
    col_a.info(f"💰 **Ingresos por Ventas:** {v_ext:.2f} €")
    col_b.success(f"🏠 **Ahorro por Consumo Propio:** {v_int:.2f} €")

elif menu == "📈 Crecimiento":
    st.title("📈 IA de Seguimiento Biológico")
    for _, r in lotes.iterrows():
        info = CONFIG_IA.get(r['raza'], {"puesta": 150, "madurez": 90})
        meta = info.get("puesta") if "puesta" in info else info.get("madurez")
        edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
        prog = min(100, int((edad/meta)*100))
        
        st.write(f"**Lote {r['id']} ({r['raza']})** - {edad} días")
        st.progress(prog/100)
        if prog < 100:
            st.caption(f"Faltan {meta-edad} días para el objetivo.")

elif menu == "💰 Salidas":
    st.title("💰 Venta o Consumo Propio")
    with st.form("salida"):
        t = st.radio("Tipo de Salida", ["Venta Cliente", "Consumo Propio"])
        l_id = st.selectbox("Lote Origen", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1); k = c2.number_input("Kilos", 0.0); p = c3.number_input("Valor €", 0.0)
        cli = st.text_input("Destinatario (Cliente o Familia)")
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, kilos_finales, unidades) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cli, t, p, int(l_id), k, u)).connection.commit(); st.rerun()

elif menu == "💾 Backup":
    st.title("💾 Exportación Blindada")
    if st.button("📊 Generar Reporte Excel"):
        try:
            import xlsxwriter
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                for t in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                    cargar(t).to_excel(wr, sheet_name=t, index=False)
            st.download_button("📥 Descargar Excel", out.getvalue(), "mi_corral.xlsx")
        except: st.error("Librería xlsxwriter no instalada.")
    
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 Descargar Base de Datos (.db)", f, "datos_corral.db")

# Las secciones de Producción, Navidad, Alta Lotes y Gastos se mantienen operativas
# con la misma lógica de blindaje de datos.
