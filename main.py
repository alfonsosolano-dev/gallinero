import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io
from PIL import Image

# ====================== 1. CONFIGURACIÓN Y MOTOR DE DATOS ======================
st.set_page_config(page_title="CORRAL IA V22.6 - FORTALEZA", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_bunker():
    conn = get_conn()
    c = conn.cursor()
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, kilos_finales REAL, unidades INTEGER",
        "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT",
        "hitos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    
    # AUTO-RESTAURACIÓN (Inyección de datos de tus capturas)
    c.execute("SELECT count(*) FROM lotes")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO lotes (id, fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", [
            (2, '21/02/2026', 'Gallinas', 'Blanca', 3, 80, 7.2, 'Activo'),
            (3, '28/02/2026', 'Gallinas', 'Roja', 2, 80, 7.2, 'Activo'),
            (5, '21/02/2026', 'Gallinas', 'Roja', 2, 80, 7.2, 'Activo'),
            (7, '21/02/2026', 'Pollos', 'Blanco Engorde', 2, 15, 2.4, 'Activo'),
            (8, '21/02/2026', 'Pollos', 'Campero', 2, 15, 2.4, 'Activo'),
            (9, '18/03/2026', 'Gallinas', 'Mochuela', 1, 80, 8.5, 'Activo')
        ])
        c.executemany("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", [
            ('21/02/2026', 'Otros', 'infraestructura', 100.0, 0),
            ('21/02/2026', 'Pienso Gallinas', 'saco', 14.0, 25),
            ('06/03/2026', 'Pienso Pollos', 'saco', 14.0, 25),
            ('18/03/2026', 'Pienso Gallinas', 'saco maiz', 13.0, 30)
        ])
        c.execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (5, 'Primera Puesta', '14/03/2026')")
        c.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES ('19/03/2026', 5, 1)")
        conn.commit()
    conn.close()

inicializar_bunker()

# ====================== 2. IA Y LÓGICA DE NEGOCIO ======================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120},
    "Blanca": {"puesta": 140, "cons": 0.115},
    "Mochuela": {"puesta": 210, "cons": 0.100},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210},
    "Campero": {"madurez": 90, "cons": 0.150}
}

def cargar(t):
    with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)

def calcular_stock_pienso(categoria, especie):
    g = cargar("gastos")
    l = cargar("lotes")
    entradas = g[g['categoria'] == categoria]['kilos_pienso'].sum()
    consumo = 0
    for _, r in l[l['especie'] == especie].iterrows():
        f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y")
        dias = (datetime.now() - f_ini).days + r['edad_inicial']
        consumo += r['cantidad'] * dias * CONFIG_IA.get(r['raza'], {"cons": 0.12})["cons"]
    return max(0, entradas - (consumo * 0.8))

# ====================== 3. INTERFAZ DE USUARIO (EL CÓDIGO COMPLETO) ======================
lotes = cargar("lotes"); ventas = cargar("ventas"); prod = cargar("produccion")
gastos = cargar("gastos"); hitos = cargar("hitos")

menu = st.sidebar.radio("MENÚ PRINCIPAL:", [
    "🏠 Control Maestro", "📈 IA Crecimiento +📸", "🥚 Producción Diaria", "🌟 Primera Puesta",
    "💰 Ventas y Consumo", "🎄 Plan Navidad", "🐣 Alta Lotes", "💸 Gastos/Compras", 
    "📜 Histórico y Borrado", "💾 COPIAS Y EXCEL"
])

if menu == "🏠 Control Maestro":
    st.title("🚜 Panel de Control")
    s_gal = calcular_stock_pienso("Pienso Gallinas", "Gallinas")
    s_pol = calcular_stock_pienso("Pienso Pollos", "Pollos")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock Gallinas", f"{s_gal:.1f} kg")
    c2.metric("Stock Pollos", f"{s_pol:.1f} kg")
    c3.metric("Huevos Totales", f"{int(prod['huevos'].sum())} ud")
    c4.metric("Ventas Totales", f"{ventas['cantidad'].sum():.2f} €")
    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.subheader("💰 Resumen Financiero")
        v_real = ventas[ventas['tipo_venta'] == 'Venta Cliente']['cantidad'].sum()
        v_ahorro = ventas[ventas['tipo_venta'] == 'Consumo Propio']['cantidad'].sum()
        st.info(f"Ventas Clientes: {v_real:.2f} €\nAhorro Casa: {v_ahorro:.2f} €")
    with cb:
        if not prod.empty:
            st.subheader("🥚 Histórico Puesta")
            st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

elif menu == "📈 IA Crecimiento +📸":
    st.title("📈 Seguimiento y Fotos")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}", expanded=True):
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_lote).days + r["edad_inicial"]
            st.write(f"**Edad:** {edad} días")
            img_file = st.camera_input(f"Capturar", key=f"c_{r['id']}")
            if img_file and st.button("Guardar Foto", key=f"s_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                   (r['id'], datetime.now().strftime("%d/%m/%Y"), img_file.read())).connection.commit()
                st.success("Foto guardada"); st.rerun()

elif menu == "🥚 Producción Diaria":
    st.title("🥚 Registro de Huevos")
    with st.form("p_form"):
        f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        c = st.number_input("Cantidad", min_value=1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l_id, c)).connection.commit(); st.rerun()

elif menu == "💰 Ventas y Consumo":
    st.title("💰 Salidas")
    with st.form("v_form"):
        tipo = st.radio("Destino", ["Venta Cliente", "Consumo Propio"])
        l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades", 1); p = st.number_input("Valor €", 0.0)
        cli = st.text_input("Nombre")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, unidades) VALUES (?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l_id, u)).connection.commit(); st.rerun()

elif menu == "🎄 Plan Navidad":
    st.title("🎄 Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    for raza in ["Blanco Engorde", "Campero"]:
        f_compra = f_obj - timedelta(days=CONFIG_IA[raza]["madurez"])
        st.success(f"**{raza}**: Comprar el {f_compra.strftime('%d/%m/%Y')}")

elif menu == "💸 Gastos/Compras":
    st.title("💸 Compras")
    with st.form("g_form"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Infraestructura", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kilos", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

elif menu == "📜 Histórico y Borrado":
    st.title("📜 Histórico")
    t = st.selectbox("Tabla:", ["lotes", "gastos", "produccion", "ventas", "hitos", "fotos"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    id_del = st.number_input("ID a eliminar:", min_value=0)
    if st.button("🗑️ Borrar"):
        get_conn().execute(f"DELETE FROM {t} WHERE id=?", (id_del,)).connection.commit(); st.rerun()

elif menu == "💾 COPIAS Y EXCEL":
    st.title("💾 Backups")
    if st.button("📊 Descargar Excel"):
        try:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                for t in ["lotes", "gastos", "produccion", "ventas"]:
                    cargar(t).to_excel(wr, index=False, sheet_name=t)
            st.download_button("📥 Bajar Excel", out.getvalue(), "corral.xlsx")
        except: st.error("Librería Excel no lista.")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 Descargar DB (.db)", f, "bunker.db")
