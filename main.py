import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL IA V27.0", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_bunker():
    conn = get_conn()
    c = conn.cursor()
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, dida_estimada REAL",
        "hitos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items(): c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    conn.commit()
    conn.close()

inicializar_bunker()

# ====================== 2. INTELIGENCIA ARTIFICIAL (LÓGICA) ======================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120, "consejo": "Alta eficiencia en puesta. Ojo con el calcio."},
    "Blanca": {"puesta": 140, "cons": 0.115, "consejo": "Vuelo fácil, asegurar cercado alto."},
    "Mochuela": {"puesta": 210, "cons": 0.100, "consejo": "Crecimiento lento, gran rusticidad."},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210, "consejo": "Ritmo de crecimiento alto. Controlar patas."},
    "Campero": {"madurez": 90, "cons": 0.150, "consejo": "Sabor superior. Necesita espacio de pasto."}
}

def cargar(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

def IA_CONSEJO(seccion):
    consejos = {
        "ventas": "💡 IA: Las ventas de huevos suben en fines de semana. ¿Has revisado el stock?",
        "gastos": "💡 IA: Comprar sacos de 25kg suele ahorrar un 15% frente a los de 5kg.",
        "produccion": "💡 IA: Si la puesta baja un 20%, revisa el agua y posibles corrientes de aire."
    }
    st.caption(consejos.get(seccion, ""))

# ====================== 3. INTERFAZ Y NAVEGACIÓN ======================
lotes = cargar("lotes"); ventas = cargar("ventas"); prod = cargar("produccion"); gastos = cargar("gastos")

menu = st.sidebar.radio("MENÚ MAESTRO:", [
    "🏠 Panel Control", "📈 IA Crecimiento + 📸", "🥚 Producción", "🌟 Hitos",
    "💰 Ventas", "💸 Gastos", "🎄 Navidad 2026", "🐣 Alta Lotes", "📜 Histórico", "💾 COPIAS"
])

# --- DASHBOARD ---
if menu == "🏠 Panel Control":
    st.title("🚜 Control Central")
    c1, c2, c3 = st.columns(3)
    if not prod.empty: c1.metric("Huevos Totales", f"{int(prod['huevos'].sum())} ud")
    if not ventas.empty: c2.metric("Ingresos Caja", f"{ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum():.2f} €")
    if not gastos.empty: c3.metric("Gasto Pienso", f"{gastos['cantidad'].sum():.2f} €")
    if not prod.empty: st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

# --- IA CRECIMIENTO ---
elif menu == "📈 IA Crecimiento + 📸":
    st.title("📈 Seguimiento Visual")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}"):
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_lote).days + r["edad_inicial"]
            st.write(f"**Edad:** {edad} días. {CONFIG_IA.get(r['raza'], {}).get('consejo', '')}")
            img = st.camera_input("Capturar", key=f"c_{r['id']}")
            if img and st.button("Guardar Foto", key=f"b_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", (r['id'], datetime.now().strftime("%d/%m/%Y"), img.read())).connection.commit()
                st.success("Foto guardada")

# --- PRODUCCIÓN ---
elif menu == "🥚 Producción":
    IA_CONSEJO("produccion")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        c = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, c)).connection.commit(); st.rerun()

# --- VENTAS ---
elif menu == "💰 Ventas":
    IA_CONSEJO("ventas")
    with st.form("v"):
        tipo = st.radio("Destino", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Uds", 1); k = c2.number_input("Kg", 0.0); p = c3.number_input("Total €", 0.0)
        cli = st.text_input("Cliente")
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()

# --- GASTOS ---
elif menu == "💸 Gastos":
    IA_CONSEJO("gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("€", 0.0); kg = st.number_input("Kg", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

# --- NAVIDAD ---
elif menu == "🎄 Navidad 2026":
    st.title("🎄 Planificador Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    for raza, info in CONFIG_IA.items():
        if "madurez" in info:
            f_compra = f_obj - timedelta(days=info['madurez'])
            st.success(f"**{raza}**: Comprar el **{f_compra.strftime('%d/%m/%Y')}** para llegar al 20 de Dic.")

# --- ALTA LOTES ---
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Nuevo Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad", 1); ed = c2.number_input("Edad inicial", 0); pr = c3.number_input("Precio/Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- HISTÓRICO ---
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    st.dataframe(cargar(t), use_container_width=True)
    id_del = st.number_input("ID a borrar", 0)
    if st.button("Eliminar Registro"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={id_del}").connection.commit(); st.rerun()

# --- RESTAURACIÓN ---
elif menu == "💾 COPIAS":
    st.title("💾 Restaurar desde Excel")
    arch = st.file_uploader("Sube tu backup .xlsx", type=["xlsx"])
    if arch and st.button("🚀 RESTAURAR"):
        try:
            data = pd.read_excel(arch, sheet_name=None); conn = get_conn()
            for t_nom, df_temp in data.items():
                if t_nom in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                    conn.execute(f"DELETE FROM {t_nom}"); df_temp.to_sql(t_nom, conn, if_exists='append', index=False)
            conn.commit(); st.success("Restauración completa"); st.rerun()
        except Exception as e: st.error(f"Error: {e}")
