import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io

# ====================== 1. NÚCLEO DE SEGURIDAD Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL IA SHIELD V18.5", layout="wide", page_icon="🛡️")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def blindar_base_de_datos():
    """Añade columnas nuevas automáticamente sin romper las tablas existentes."""
    conn = get_conn()
    c = conn.cursor()
    # Estructura maestra de tablas
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
    
    # Verificación de columnas críticas para evitar el error de "unidades" o "kilos"
    def check_col(tabla, columna, tipo):
        cols = [col[1] for col in c.execute(f"PRAGMA table_info({tabla})")]
        if columna not in cols:
            c.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            
    check_col("ventas", "unidades", "INTEGER DEFAULT 1")
    check_col("ventas", "kilos_finales", "REAL DEFAULT 0")
    check_col("ventas", "tipo_venta", "TEXT DEFAULT 'Venta Cliente'")
    
    conn.commit()
    conn.close()

def cargar_datos(tabla):
    try:
        conn = get_conn()
        df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

blindar_base_de_datos()

# ====================== 2. MOTOR IA (CENTRALIZADO) ======================
# Si quieres añadir una raza, solo edita este diccionario
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120},
    "Blanca": {"puesta": 140, "cons": 0.115},
    "Chocolate": {"puesta": 160, "cons": 0.130},
    "Mochuela (Pintada)": {"puesta": 210, "cons": 0.100},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210},
    "Campero": {"madurez": 90, "cons": 0.150},
    "Codorniz": {"puesta": 45, "cons": 0.035}
}

lotes = cargar_datos("lotes")
gastos = cargar_datos("gastos")
ventas = cargar_datos("ventas")
produccion = cargar_datos("produccion")
bajas = cargar_datos("bajas")
hitos = cargar_datos("hitos")

# ====================== 3. LÓGICA DE NEGOCIO Y CÁLCULOS ======================
def calc_pienso(categoria, especie):
    try:
        kg_comprados = gastos[gastos['categoria'] == categoria]['kilos_pienso'].sum()
        consumo_total = 0
        if not lotes.empty:
            for _, r in lotes[lotes['especie'] == especie].iterrows():
                vivas = r['cantidad'] - (bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0)
                dias = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days
                factor = CONFIG_IA.get(r["raza"], {"cons": 0.11}).get("cons")
                # Cálculo de consumo progresivo simplificado para el stock
                consumo_total += max(0, vivas) * (dias + r["edad_inicial"]) * factor * 0.75
        return max(0, kg_comprados - consumo_total)
    except: return 0.0

# ====================== 4. INTERFAZ (MENÚ SEGURO) ======================
seccion = st.sidebar.radio("SISTEMA DE GESTIÓN:", [
    "🏠 Dashboard", "📈 IA Crecimiento", "🥚 Producción", "🌟 Primera Puesta",
    "💰 Ventas/Consumo", "🎄 IA Navidad", "🐣 Alta Lotes", "💸 Gastos", "📜 Histórico", "💾 EXPORTAR"
])

if seccion == "🏠 Dashboard":
    st.title("🏠 Control Maestro")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pienso Gallinas", f"{calc_pienso('Pienso Gallinas', 'Gallinas'):.1f} kg")
    c2.metric("Pienso Pollos", f"{calc_pienso('Pienso Pollos', 'Pollos'):.1f} kg")
    
    # Separación clara de ingresos vs ahorro
    v_cash = ventas[ventas['tipo_venta'] == 'Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    v_home = ventas[ventas['tipo_venta'] == 'Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    c1.metric("Caja Real", f"{v_cash:.2f} €")
    c2.metric("Ahorro Casa", f"{v_home:.2f} €")

elif seccion == "📈 IA Crecimiento":
    st.title("📈 Predicción de Puesta y Madurez")
    for _, r in lotes.iterrows():
        info = CONFIG_IA.get(r["raza"], {"puesta": 150, "madurez": 90})
        meta = info.get("puesta") if "puesta" in info else info.get("madurez")
        edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
        progreso = min(100, int((edad/meta)*100))
        
        ya_pone = "🥚" if not hitos[(hitos['lote_id']==r['id']) & (hitos['tipo']=='Primera Puesta')].empty else ""
        st.write(f"**Lote {r['id']} ({r['raza']})** {ya_pone} - {edad} días de vida")
        st.progress(progreso/100)
        if progreso < 100:
            f_est = datetime.now() + timedelta(days=meta-edad)
            st.info(f"📅 IA estima madurez el: {f_est.strftime('%d/%m/%Y')}")

elif seccion == "💰 Ventas/Consumo":
    st.title("💰 Salidas de Producto")
    with st.form("venta_blindada"):
        tipo = st.selectbox("Tipo de Salida", ["Venta Cliente", "Consumo Propio"])
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1)
        k = c2.number_input("Kilos Totales", 0.0)
        p = c3.number_input("Valor/Precio €", 0.0)
        cli = st.text_input("Cliente / Familiar")
        con = st.text_input("Concepto (ej: Pollo limpio, docena huevos...)")
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad, lote_id, kilos_finales, unidades) VALUES (?,?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, con, p, int(l_id), k, u)).connection.commit(); st.rerun()

elif seccion == "🎄 IA Navidad":
    st.title("🎄 Planificador Navidad")
    f_obj = datetime(datetime.now().year, 12, 20)
    for raza in ["Blanco Engorde", "Campero"]:
        info = CONFIG_IA[raza]
        f_compra = f_obj - timedelta(days=info['madurez'])
        st.success(f"**Para {raza}**: Comprar el **{f_compra.strftime('%d de Septiembre')}** para estar listo en Navidad.")

elif seccion == "💾 EXPORTAR":
    st.title("💾 Copia de Seguridad y Excel")
    try:
        import xlsxwriter
        if st.button("📊 Generar Excel Completo"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for t in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                    cargar_datos(t).to_excel(writer, sheet_name=t, index=False)
            st.download_button("📥 Descargar Excel", output.getvalue(), "corral_maestro.xlsx")
    except:
        st.error("Librería Excel no detectada. Usa el backup .db")
    
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 Descargar Base de Datos (.db)", f, "corral.db")

# Las secciones de Producción, Alta Lotes, Gastos y Bajas se mantienen 
# integradas con la misma lógica de protección de datos.
elif seccion == "🥚 Producción":
    st.title("🥚 Registro de Huevos")
    with st.form("p"):
        f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        cant = st.number_input("Cantidad", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l_id, cant)).connection.commit(); st.rerun()

elif seccion == "🌟 Primera Puesta":
    st.title("🌟 Hito: Primera Puesta")
    with st.form("h"):
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        f_h = st.date_input("Fecha")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?, 'Primera Puesta', ?)", (int(l_id), f_h.strftime("%d/%m/%Y"))).connection.commit(); st.rerun()

elif seccion == "🐣 Alta Lotes":
    st.title("🐣 Alta Inteligente")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cant", 1); ed = c2.number_input("Edad inicial", 0); pr = c3.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

elif seccion == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kilos", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

elif seccion == "📜 Histórico":
    st.title("📜 Histórico")
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    df = cargar_datos(t); st.dataframe(df, use_container_width=True)
