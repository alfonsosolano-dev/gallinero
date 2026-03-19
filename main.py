import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io

# =================================================================
# MÓDULO 1: NÚCLEO DE DATOS Y CONEXIÓN
# =================================================================
st.set_page_config(page_title="CORRAL IA V29.0", layout="wide", page_icon="🚜")
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
        "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, dida_estimada REAL",
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
# MÓDULO 2: INTELIGENCIA ARTIFICIAL Y CONFIGURACIÓN
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
        "produccion": "💡 IA: Una bajada de luz reduce la puesta. Mantén horas de luz constantes."
    }
    st.info(dict_c.get(seccion, "Gestión optimizada por IA."))

# =================================================================
# MÓDULO 3: VISTAS (FORMULARIOS Y PANTALLAS)
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

def vista_produccion(lotes):
    st.title("🥚 Registro de Producción")
    obtener_consejo("produccion")
    with st.form("f_prod"):
        f = st.date_input("Fecha")
        l = st.selectbox("Seleccionar Lote", lotes['id'].tolist() if not lotes.empty else ["No hay lotes"])
        h = st.number_input("Cantidad de Huevos", min_value=1)
        if st.form_submit_button("Guardar Producción"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit()
            st.success("Producción registrada"); st.rerun()

def vista_ventas(lotes):
    st.title("💰 Ventas y Consumo Propio")
    obtener_consejo("ventas")
    with st.form("f_ventas"):
        tipo = st.radio("Tipo de Salida", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote de Origen", lotes['id'].tolist() if not lotes.empty else ["No hay lotes"])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1)
        k = c2.number_input("Kilos (ilos_finale)", 0.0)
        p = c3.number_input("Importe Total €", 0.0)
        cli = st.text_input("Cliente / Familia")
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit()
            st.success("Registro completado"); st.rerun()

def vista_gastos():
    st.title("💸 Compras y Gastos")
    obtener_consejo("gastos")
    with st.form("f_gastos"):
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Infraestructura", "Otros"])
        con = st.text_input("Concepto")
        c1, c2 = st.columns(2)
        imp = c1.number_input("Importe €", 0.0)
        kg = c2.number_input("Kilos (ilos_pienso)", 0.0)
        f = st.date_input("Fecha de Compra")
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", 
                               (f.strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit()
            st.success("Gasto guardado"); st.rerun()

def vista_navidad():
    st.title("🎄 Planificador Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    st.write("Fechas límite para que los animales estén listos el 20 de Diciembre:")
    for raza, info in CONFIG_IA.items():
        if "madurez" in info:
            f_compra = f_obj - timedelta(days=info['madurez'])
            st.success(f"📌 **{raza}**: Debes comprarlos antes del **{f_compra.strftime('%d/%m/%Y')}**")

def vista_alta_lotes():
    st.title("🐣 Alta de Nuevos Lotes")
    with st.form("alta_lote"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad", 1)
        ed = c2.number_input("Edad Inicial (días)", 0)
        pr = c3.number_input("Precio Ud €", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit()
            st.success("Nuevo lote creado"); st.rerun()

def vista_copias():
    st.title("💾 Restauración y Seguridad")
    arch = st.file_uploader("Sube tu backup Excel (.xlsx)", type=["xlsx"])
    if arch and st.button("🚀 RESTAURAR TODO"):
        try:
            data = pd.read_excel(arch, sheet_name=None)
            conn = get_conn()
            for t_nom, df_temp in data.items():
                if t_nom in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                    conn.execute(f"DELETE FROM {t_nom}")
                    df_temp.to_sql(t_nom, conn, if_exists='append', index=False)
            conn.commit(); st.success("✅ Sistema restaurado con éxito."); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# =================================================================
# MÓDULO 4: LÓGICA DE NAVEGACIÓN (MAIN)
# =================================================================
inicializar_db()
lotes = cargar_tabla("lotes"); ventas = cargar_tabla("ventas")
prod = cargar_tabla("produccion"); gastos = cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ PRINCIPAL:", [
    "🏠 Dashboard", "🥚 Producción", "💰 Ventas", "💸 Gastos", 
    "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"
])

if menu == "🏠 Dashboard": vista_dashboard(prod, ventas, gastos)
elif menu == "🥚 Producción": vista_produccion(lotes)
elif menu == "💰 Ventas": vista_ventas(lotes)
elif menu == "💸 Gastos": vista_gastos()
elif menu == "🎄 Navidad": vista_navidad()
elif menu == "🐣 Alta Lotes": vista_alta_lotes()
elif menu == "💾 Copias": vista_copias()
elif menu == "📜 Histórico":
    t_sel = st.selectbox("Ver tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    st.dataframe(cargar_tabla(t_sel), use_container_width=True)
    id_del = st.number_input("ID a eliminar", 0)
    if st.button("Eliminar Registro"):
        get_conn().execute(f"DELETE FROM {t_sel} WHERE id={id_del}").connection.commit(); st.rerun()
