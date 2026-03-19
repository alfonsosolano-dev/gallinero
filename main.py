import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# =================================================================
# BLOQUE 1: MOTOR DE DATOS (CON AUTO-REPARACIÓN)
# =================================================================
st.set_page_config(page_title="CORRAL IA V35.0", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Esquema maestro
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
        # Parche para columnas faltantes (evita errores como el de tu captura)
        if n == "ventas":
            try: c.execute("ALTER TABLE ventas ADD COLUMN unidades INTEGER")
            except: pass
            try: c.execute("ALTER TABLE ventas ADD COLUMN ilos_finale REAL")
            except: pass
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn:
            df = pd.read_sql(f"SELECT * FROM {t}", conn)
            if t == "gastos" and not df.empty and 'ilos_pienso' not in df.columns: df['ilos_pienso'] = 0.0
            if t == "ventas" and not df.empty and 'unidades' not in df.columns: df['unidades'] = 0
            return df
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: INTELIGENCIA DE CONSUMO
# =================================================================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons_base": 0.110},
    "Blanca": {"puesta": 140, "cons_base": 0.105},
    "Mochuela": {"puesta": 210, "cons_base": 0.095},
    "Blanco Engorde": {"madurez": 55, "cons_base": 0.180},
    "Campero": {"madurez": 90, "cons_base": 0.140}
}

def calcular_consumo_diario(raza, edad, cantidad):
    base = CONFIG_IA.get(raza, {}).get("cons_base", 0.120)
    factor = 0.3 if edad < 20 else (0.6 if edad < 45 else 1.0)
    return base * factor * cantidad

# =================================================================
# BLOQUE 3: EL NUEVO PANEL DE CONTROL (REDISEÑADO)
# =================================================================
def vista_dashboard(prod, ventas, gastos, lotes):
    st.title("🏠 Panel de Control Maestro")
    
    # --- CÁLCULOS ---
    t_producido = prod['huevos'].sum() if not prod.empty else 0
    t_salidas = ventas['unidades'].sum() if not ventas.empty else 0
    stock_huevos = t_producido - t_salidas

    v_cliente = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro_casa = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    inversion = gastos['cantidad'].sum() if not gastos.empty else 0
    beneficio_neto = (v_cliente + ahorro_casa) - inversion

    # --- MÉTRICAS PRINCIPALES ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🥚 Stock Huevos", f"{int(stock_huevos)} ud")
    c2.metric("💸 Inversión Total", f"{inversion:.2f} €")
    c3.metric("💰 Caja (Ventas)", f"{v_cliente:.2f} €")
    c4.metric("🏠 Ahorro Casa", f"{ahorro_casa:.2f} €")
    
    st.metric("🚀 Beneficio Neto (Caja + Ahorro - Inversión)", f"{beneficio_neto:.2f} €", 
              delta=f"{beneficio_neto:.2f} €", delta_color="normal")

    st.divider()

    # --- TABLA DE CONSUMO POR ESPECIE ---
    st.subheader("📊 Consumo de Pienso Estimado (Hoy)")
    if not lotes.empty:
        consumos = []
        for _, r in lotes.iterrows():
            try:
                f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
                edad = (datetime.now() - f_lote).days + r["edad_inicial"]
                c_dia = calcular_consumo_diario(r['raza'], edad, r['cantidad'])
                consumos.append({"Lote": r['id'], "Especie": r['especie'], "Raza": r['raza'], "Edad": f"{edad} días", "Kg/Día": round(c_dia, 3)})
            except: pass
        st.table(pd.DataFrame(consumos))
    
    if not prod.empty:
        st.subheader("📈 Tendencia de Puesta")
        st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

# =================================================================
# BLOQUE 4: RESTO DE FUNCIONES (VENTAS, GASTOS, ETC)
# =================================================================
def vista_ventas(lotes):
    st.title("💰 Registrar Venta / Consumo")
    with st.form("v2"):
        t = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades (Huevos/Pollos)", 1)
        k = c2.number_input("Kg finales", 0.0)
        p = c3.number_input("Precio Total €", 0.0)
        cli = st.text_input("Cliente o Familia")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, t, p, l, k, u)).connection.commit(); st.rerun()

def vista_gastos():
    st.title("💸 Registrar Gasto")
    with st.form("g2"):
        cat = st.selectbox("Categoría", ["Pienso", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2)
        p = c1.number_input("Euros €", 0.0); kg = c2.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, p, kg)).connection.commit(); st.rerun()

# [Otras funciones simplificadas para asegurar carga]
def vista_alta():
    st.title("🐣 Nuevo Lote")
    with st.form("a2"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad inicial", 0); pr = st.number_input("Precio Ud", 0.0)
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# =================================================================
# BLOQUE 5: NAVEGACIÓN
# =================================================================
inicializar_db()
lotes = cargar_tabla("lotes"); ventas = cargar_tabla("ventas")
prod = cargar_tabla("produccion"); gastos = cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🐣 Alta Lotes", "💾 Copias"])

if menu == "🏠 Dashboard": vista_dashboard(prod, ventas, gastos, lotes)
elif menu == "💰 Ventas": vista_ventas(lotes)
elif menu == "💸 Gastos": vista_gastos()
elif menu == "🐣 Alta Lotes": vista_alta()
elif menu == "💾 Copias":
    st.title("💾 Restaurar")
    arch = st.file_uploader("Excel", type=["xlsx"])
    if arch and st.button("Restaurar Todo"):
        data = pd.read_excel(arch, sheet_name=None); conn = get_conn()
        for t, df in data.items():
            if t in ["lotes", "gastos", "produccion", "ventas"]:
                conn.execute(f"DELETE FROM {t}"); df.to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.success("Listo"); st.rerun()
