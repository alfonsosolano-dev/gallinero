import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io

# =================================================================
# BLOQUE 1: MOTOR DE DATOS
# =================================================================
st.set_page_config(page_title="CORRAL IA V31.0", layout="wide", page_icon="🚜")
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
        "hitos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items(): c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: INTELIGENCIA ARTIFICIAL (LÓGICA)
# =================================================================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120, "consejo": "Alta puesta. Ojo con el calcio."},
    "Blanca": {"puesta": 140, "cons": 0.115, "consejo": "Vuelan mucho. Vallado alto."},
    "Mochuela": {"puesta": 210, "cons": 0.100, "consejo": "Rústica y resistente."},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210, "consejo": "Crecimiento rápido. Ojo patas."},
    "Campero": {"madurez": 90, "cons": 0.150, "consejo": "Sabor top. Necesita campo."}
}

def obtener_consejo(seccion):
    dict_c = {
        "ventas": "💡 IA: Las ventas suelen subir en festivos. Revisa existencias.",
        "gastos": "💡 IA: Comprar al por mayor reduce el gasto anual un 12%.",
        "produccion": "💡 IA: Una bajada de luz reduce la puesta. Mantén horas de luz.",
        "crecimiento": "💡 IA: El pesaje semanal ayuda a detectar enfermedades antes que el ojo humano."
    }
    st.info(dict_c.get(seccion, "Gestión optimizada por IA."))

# =================================================================
# BLOQUE 3: VISTAS MODULARES (SECCIONES)
# =================================================================

def vista_dashboard(prod, ventas, gastos):
    st.title("🏠 Panel de Control Maestro")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Huevos Totales", f"{int(prod['huevos'].sum()) if not prod.empty else 0}")
    c2.metric("Caja Real", f"{ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0:.2f} €")
    c3.metric("Ahorro Casa", f"{ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0:.2f} €")
    c4.metric("Inversión", f"{gastos['cantidad'].sum() if not gastos.empty else 0:.2f} €")
    if not prod.empty:
        st.subheader("📈 Tendencia de Puesta")
        st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

def vista_crecimiento(lotes):
    st.title("📈 Crecimiento e Inteligencia Visual")
    obtener_consejo("crecimiento")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']} ({r['especie']})", expanded=True):
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_lote).days + r["edad_inicial"]
            st.write(f"📅 Edad: {edad} días. | {CONFIG_IA.get(r['raza'], {}).get('consejo', '')}")
            
            # Foto
            img = st.camera_input(f"Capturar Lote {r['id']}", key=f"cam_{r['id']}")
            if img and st.button(f"Guardar Foto {r['id']}", key=f"btn_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                   (r['id'], datetime.now().strftime("%d/%m/%Y"), img.read())).connection.commit()
                st.success("Foto guardada."); st.rerun()

def vista_produccion(lotes):
    st.title("🥚 Producción")
    obtener_consejo("produccion")
    with st.form("f_p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Cantidad Huevos", 1)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()

def vista_ventas(lotes):
    st.title("💰 Ventas")
    obtener_consejo("ventas")
    with st.form("f_v"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1); k = c2.number_input("Kg", 0.0); p = c3.number_input("Total €", 0.0)
        cli = st.text_input("Cliente/Familia")
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()

def vista_gastos():
    st.title("💸 Gastos")
    obtener_consejo("gastos")
    with st.form("f_g"):
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2)
        imp = c1.number_input("Importe €", 0.0); kg = c2.number_input("Kg (ilos_pienso)", 0.0)
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

def vista_navidad():
    st.title("🎄 Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    for raza, info in CONFIG_IA.items():
        if "madurez" in info:
            f_compra = f_obj - timedelta(days=info['madurez'])
            st.success(f"📌 **{raza}**: Comprar el **{f_compra.strftime('%d/%m/%Y')}**")

def vista_alta(lotes):
    st.title("🐣 Alta Lotes")
    with st.form("f_a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad", 1); ed = c2.number_input("Edad inicial", 0); pr = c3.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

def vista_copias():
    st.title("💾 Copias y Restauración")
    arch = st.file_uploader("Subir Backup Excel", type=["xlsx"])
    if arch and st.button("🚀 RESTAURAR"):
        data = pd.read_excel(arch, sheet_name=None); conn = get_conn()
        for t, df in data.items():
            if t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
                conn.execute(f"DELETE FROM {t}"); df.to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.success("OK"); st.rerun()

# =================================================================
# BLOQUE 4: NAVEGACIÓN PRINCIPAL
# =================================================================
inicializar_db()
lotes = cargar_tabla("lotes"); ventas = cargar_tabla("ventas")
prod = cargar_tabla("produccion"); gastos = cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard": vista_dashboard(prod, ventas, gastos)
elif menu == "📈 Crecimiento": vista_crecimiento(lotes)
elif menu == "🥚 Producción": vista_produccion(lotes)
elif menu == "💰 Ventas": vista_ventas(lotes)
elif menu == "💸 Gastos": vista_gastos()
elif menu == "🎄 Navidad": vista_navidad()
elif menu == "🐣 Alta Lotes": vista_alta(lotes)
elif menu == "💾 Copias": vista_copias()
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas"])
    st.dataframe(cargar_tabla(t), use_container_width=True)
    id_del = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={id_del}").connection.commit(); st.rerun()
