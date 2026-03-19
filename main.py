import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io

# ====================== 1. MOTOR DE BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL IA V26.0 - EL BÚNKER", layout="wide", page_icon="🛡️")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_bunker():
    conn = get_conn()
    c = conn.cursor()
    # Tablas ajustadas fielmente a tus capturas de Excel
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, dida_estimada REAL",
        "hitos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    conn.commit()
    conn.close()

inicializar_bunker()

# ====================== 2. LÓGICA DE INTELIGENCIA ======================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120},
    "Blanca": {"puesta": 140, "cons": 0.115},
    "Mochuela": {"puesta": 210, "cons": 0.100},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210},
    "Campero": {"madurez": 90, "cons": 0.150}
}

def cargar(t):
    try:
        with get_conn() as conn:
            return pd.read_sql(f"SELECT * FROM {t}", conn)
    except:
        return pd.DataFrame()

def calcular_stock(categoria, especie):
    g = cargar("gastos")
    l = cargar("lotes")
    # Blindaje contra KeyError si las tablas están vacías
    if g.empty or 'ilos_pienso' not in g.columns or l.empty:
        return 0.0
    
    entradas = g[g['categoria'] == categoria]['ilos_pienso'].sum()
    consumo = 0
    for _, r in l[l['especie'] == especie].iterrows():
        try:
            f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias = (datetime.now() - f_ini).days + r['edad_inicial']
            consumo += r['cantidad'] * dias * CONFIG_IA.get(r['raza'], {"cons": 0.12})["cons"]
        except: continue
    return max(0.0, entradas - (consumo * 0.8))

# ====================== 3. INTERFAZ Y NAVEGACIÓN ======================
lotes = cargar("lotes"); ventas = cargar("ventas"); prod = cargar("produccion")
gastos = cargar("gastos")

menu = st.sidebar.radio("NAVEGACIÓN:", [
    "🏠 Dashboard Maestro", "📈 IA + 📸", "🥚 Producción", "💰 Ventas", 
    "💸 Gastos", "🎄 Navidad", "🐣 Alta de Lotes", "📜 Histórico", "💾 COPIAS Y RESTAURACIÓN"
])

# --- DASHBOARD ---
if menu == "🏠 Dashboard Maestro":
    st.title("🚜 Estado Real de la Granja")
    s_gal = calcular_stock("Pienso Gallinas", "Gallinas")
    s_pol = calcular_stock("Pienso Pollos", "Pollos")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock Pienso Gallinas", f"{s_gal:.1f} kg")
    c2.metric("Stock Pienso Pollos", f"{s_pol:.1f} kg")
    c3.metric("Huevos Totales", f"{int(prod['huevos'].sum()) if not prod.empty else 0} ud")
    c4.metric("Caja Real", f"{ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0:.2f} €")
    
    st.divider()
    if not prod.empty:
        st.subheader("🥚 Historial de Puesta")
        st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

# --- IA Y FOTOS ---
elif menu == "📈 IA + 📸":
    st.title("📈 Seguimiento Visual")
    if lotes.empty: st.info("No hay lotes activos. Sube tu Excel o crea uno.")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}"):
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_lote).days + r["edad_inicial"]
            st.write(f"Edad: {edad} días")
            img = st.camera_input("Capturar", key=f"cam_{r['id']}")
            if img and st.button("Guardar Foto", key=f"b_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                   (r['id'], datetime.now().strftime("%d/%m/%Y"), img.read())).connection.commit()
                st.success("Guardada")

# --- PRODUCCIÓN ---
elif menu == "🥚 Producción":
    with st.form("p_form"):
        f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [0])
        cant = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l_id, cant)).connection.commit(); st.rerun()

# --- VENTAS ---
elif menu == "💰 Ventas":
    with st.form("v_form"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [0])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1); k = c2.number_input("Kilos (ilos_finale)", 0.0); p = c3.number_input("Precio €", 0.0)
        cli = st.text_input("Cliente")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l_id, k, u)).connection.commit(); st.rerun()

# --- GASTOS ---
elif menu == "💸 Gastos":
    with st.form("g_form"):
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kg (ilos_pienso)", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    df_h = cargar(t)
    st.dataframe(df_h, use_container_width=True)
    id_del = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={id_del}").connection.commit(); st.rerun()

# --- RESTAURACIÓN ---
elif menu == "💾 COPIAS Y RESTAURACIÓN":
    st.title("💾 Restaurar Sistema")
    arch = st.file_uploader("Sube 'corral_completo.xlsx'", type=["xlsx"])
    if arch and st.button("🚀 INICIAR RESTAURACIÓN"):
        try:
            # Usamos motor 'openpyxl' explícitamente si está disponible
            data = pd.read_excel(arch, sheet_name=None)
            conn = get_conn()
            for t_nom, df_temp in data.items():
                if t_nom in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                    conn.execute(f"DELETE FROM {t_nom}")
                    df_temp.to_sql(t_nom, conn, if_exists='append', index=False)
            conn.commit()
            st.success("¡Datos recuperados!"); st.rerun()
        except Exception as e: st.error(f"Error: {e}")
