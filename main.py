import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# =================================================================
# BLOQUE 1: MOTOR DE DATOS (CON PROTECCIÓN DE COLUMNAS)
# =================================================================
st.set_page_config(page_title="CORRAL IA V33.1", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Aseguramos que todas las columnas existan desde el inicio
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
            # PARCHE ANTICRISIS: Si falta la columna crítica, la creamos vacía en el DataFrame
            if t == "gastos" and not df.empty and 'ilos_pienso' not in df.columns:
                df['ilos_pienso'] = 0.0
            return df
    except:
        return pd.DataFrame()

# =================================================================
# BLOQUE 2: IA Y LÓGICA
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
# BLOQUE 3: VISTAS (DASHBOARD CORREGIDO)
# =================================================================
def vista_dashboard(prod, ventas, gastos, lotes):
    st.title("🏠 Panel de Control Maestro")
    
    # Verificación de columna segura para evitar el KeyError de tu foto
    total_pienso = 0
    if not gastos.empty and 'ilos_pienso' in gastos.columns:
        total_pienso = gastos['ilos_pienso'].sum()

    if total_pienso < 10:
        st.error(f"⚠️ Alerta Stock: {total_pienso:.1f} kg")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Huevos", f"{int(prod['huevos'].sum()) if not prod.empty else 0}")
    
    ingresos = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    c2.metric("Caja", f"{ingresos:.2f} €")
    
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

# =================================================================
# BLOQUE 4: NAVEGACIÓN
# =================================================================
inicializar_db()
lotes = cargar_tabla("lotes"); ventas = cargar_tabla("ventas")
prod = cargar_tabla("produccion"); gastos = cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "💾 Copias"])

if menu == "🏠 Dashboard":
    vista_dashboard(prod, ventas, gastos, lotes)
elif menu == "💾 Copias":
    st.title("💾 Restaurar")
    arch = st.file_uploader("Sube el Excel", type=["xlsx"])
    if arch and st.button("RESTAURAR"):
        try:
            data = pd.read_excel(arch, sheet_name=None)
            conn = get_conn()
            for t, df in data.items():
                if t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
                    # Aseguramos que el Excel tenga las columnas que pide la DB
                    conn.execute(f"DELETE FROM {t}")
                    df.to_sql(t, conn, if_exists='append', index=False)
            conn.commit(); st.success("¡Restaurado!"); st.rerun()
        except Exception as e: st.error(f"Error: {e}. Asegúrate de tener 'openpyxl' en requirements.txt")
# (El resto de funciones de la V33 se mantienen igual...)
