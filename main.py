import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io
from PIL import Image

# ====================== 1. NÚCLEO DE DATOS (MIGRACIONES INCLUIDAS) ======================
st.set_page_config(page_title="CORRAL IA V24.0 - EL BÚNKER", layout="wide", page_icon="🛡️")
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
    for n, e in tablas.items(): c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    conn.commit()
    conn.close()

inicializar_bunker()

# ====================== 2. INTELIGENCIA BIOLÓGICA Y STOCK ======================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120},
    "Blanca": {"puesta": 140, "cons": 0.115},
    "Mochuela": {"puesta": 210, "cons": 0.100},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210},
    "Campero": {"madurez": 90, "cons": 0.150}
}

def cargar(t):
    with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)

def calcular_pienso_restante(categoria, especie):
    g = cargar("gastos"); l = cargar("lotes")
    entradas = g[g['categoria'] == categoria]['kilos_pienso'].sum()
    consumo = 0
    for _, r in l[l['especie'] == especie].iterrows():
        dias = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r['edad_inicial']
        consumo += r['cantidad'] * dias * CONFIG_IA.get(r['raza'], {"cons": 0.12})["cons"]
    return max(0, entradas - (consumo * 0.75)) # Ajuste de desperdicio

# ====================== 3. INTERFAZ PROFESIONAL ======================
lotes = cargar("lotes"); ventas = cargar("ventas"); prod = cargar("produccion")
gastos = cargar("gastos"); hitos = cargar("hitos")

menu = st.sidebar.radio("MENÚ DE CONTROL:", [
    "🏠 Panel de Control", "📈 IA Crecimiento + 📸", "🥚 Producción", "💰 Ventas/Consumo", 
    "💸 Gastos/Compras", "🎄 Plan Navidad", "🐣 Alta de Lote", "📜 Histórico y Borrado", "💾 COPIAS Y RESTAURAR"
])

# --- DASHBOARD ---
if menu == "🏠 Panel de Control":
    st.title("🚜 Estado General de la Granja")
    s_gal = calcular_pienso_restante("Pienso Gallinas", "Gallinas")
    s_pol = calcular_pienso_restante("Pienso Pollos", "Pollos")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock Gallinas", f"{s_gal:.1f} kg")
    c2.metric("Stock Pollos", f"{s_pol:.1f} kg")
    c3.metric("Huevos Totales", f"{int(prod['huevos'].sum())} ud")
    c4.metric("Caja Real", f"{ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum():.2f} €")
    
    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.subheader("💰 Economía")
        st.write(f"💵 **Ventas:** {ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum():.2f} €")
        st.write(f"🏠 **Ahorro Casa:** {ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum():.2f} €")
        st.write(f"📉 **Inversión:** {gastos['cantidad'].sum():.2f} €")
    with cb:
        if not prod.empty:
            st.subheader("🥚 Evolución de Puesta")
            st.line_chart(prod.tail(20).set_index('fecha')['huevos'])

# --- IA CRECIMIENTO CON FOTOS ---
elif menu == "📈 IA Crecimiento + 📸":
    st.title("📈 Seguimiento Visual e IA")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']} ({r['especie']})", expanded=True):
            edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
            st.write(f"**Edad:** {edad} días")
            img = st.camera_input("Capturar", key=f"c_{r['id']}")
            if img and st.button("Guardar Foto", key=f"b_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", (r['id'], "19/03/2026", img.read())).connection.commit()
                st.success("Foto guardada."); st.rerun()

# --- PRODUCCIÓN ---
elif menu == "🥚 Producción":
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist())
        c = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, c)).connection.commit(); st.rerun()

# --- VENTAS CON PESO ---
elif menu == "💰 Ventas/Consumo":
    st.title("💰 Registro de Salidas")
    with st.form("v"):
        tipo = st.radio("Destino", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote Origen", lotes['id'].tolist())
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1); k = c2.number_input("Kilos", 0.0); p = c3.number_input("Precio/Valor €", 0.0)
        cli = st.text_input("Cliente / Familia")
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, kilos_finales, unidades) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()

# --- NAVIDAD ---
elif menu == "🎄 Plan Navidad":
    st.title("🎄 Planificador Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    for raza in ["Blanco Engorde", "Campero"]:
        f_compra = f_obj - timedelta(days=CONFIG_IA[raza]["madurez"])
        st.success(f"⚠️ **{raza}**: Debes comprarlos el **{f_compra.strftime('%d/%m/%Y')}**")

# --- GASTOS ---
elif menu == "💸 Gastos/Compras":
    with st.form("g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Cat", ["Pienso Gallinas", "Pienso Pollos", "Infraestructura", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kilos", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

# --- HISTÓRICO Y BORRADO ---
elif menu == "📜 Histórico y Borrado":
    st.title("📜 Histórico")
    t = st.selectbox("Tabla:", ["lotes", "gastos", "produccion", "ventas", "hitos", "fotos"])
    df = cargar(t)
    st.dataframe(df, use_container_width=True)
    id_del = st.number_input("ID a eliminar:", 0)
    if st.button("❌ Borrar Registro"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={id_del}").connection.commit(); st.rerun()

# --- COPIAS Y RESTAURACIÓN ---
elif menu == "💾 COPIAS Y RESTAURAR":
    st.title("💾 Gestión de Copias")
    
    st.subheader("🔄 Restaurar desde Backup")
    arch = st.file_uploader("Sube tu Excel de backup para recuperar todo", type=["xlsx"])
    if arch and st.button("🚀 INICIAR RESTAURACIÓN"):
        try:
            data = pd.read_excel(arch, sheet_name=None); conn = get_conn()
            for name, df_temp in data.items():
                if name in ["lotes", "gastos", "produccion", "ventas", "hitos"]:
                    conn.execute(f"DELETE FROM {name}"); df_temp.to_sql(name, conn, if_exists='append', index=False)
            conn.commit(); st.success("¡Datos recuperados!"); st.rerun()
        except Exception as e: st.error(f"Error: {e}")
        
    st.divider()
    if st.button("📊 Descargar Excel"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
            for t in ["lotes", "gastos", "produccion", "ventas", "hitos"]: cargar(t).to_excel(wr, index=False, sheet_name=t)
        st.download_button("📥 Bajar Excel", out.getvalue(), "granja_backup.xlsx")
