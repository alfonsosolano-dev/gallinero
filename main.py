import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io
from PIL import Image

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL IA V25.0", layout="wide", page_icon="🛡️")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_bunker():
    conn = get_conn()
    c = conn.cursor()
    # Definición de tablas con los nombres exactos de tus capturas (ilos_...)
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

# ====================== 2. INTELIGENCIA Y CÁLCULOS ======================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120},
    "Blanca": {"puesta": 140, "cons": 0.115},
    "Mochuela": {"puesta": 210, "cons": 0.100},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210},
    "Campero": {"madurez": 90, "cons": 0.150}
}

def cargar(t):
    with get_conn() as conn:
        return pd.read_sql(f"SELECT * FROM {t}", conn)

def calcular_stock(categoria, especie):
    g = cargar("gastos")
    l = cargar("lotes")
    if g.empty or l.empty: return 0.0
    # Usamos 'ilos_pienso' como aparece en tu captura
    entradas = g[g['categoria'] == categoria]['ilos_pienso'].sum()
    consumo = 0
    for _, r in l[l['especie'] == especie].iterrows():
        f_ini = datetime.strptime(r["fecha"], "%d/%m/%Y")
        dias = (datetime.now() - f_ini).days + r['edad_inicial']
        consumo += r['cantidad'] * dias * CONFIG_IA.get(r['raza'], {"cons": 0.12})["cons"]
    return max(0.0, entradas - (consumo * 0.8))

# ====================== 3. INTERFAZ DE USUARIO ======================
lotes = cargar("lotes"); ventas = cargar("ventas"); prod = cargar("produccion")
gastos = cargar("gastos"); hitos = cargar("hitos")

menu = st.sidebar.radio("NAVEGACIÓN:", [
    "🏠 Dashboard Maestro", 
    "📈 IA Crecimiento + 📸", 
    "🥚 Producción Diaria", 
    "🌟 Hitos y Puestas",
    "💰 Ventas y Consumo", 
    "🎄 Plan Navidad", 
    "🐣 Alta de Lotes", 
    "💸 Gastos y Compras", 
    "📜 Histórico y Borrado", 
    "💾 COPIAS Y RESTAURACIÓN"
])

# --- DASHBOARD ---
if menu == "🏠 Dashboard Maestro":
    st.title("🚜 Estado Real de la Granja")
    s_gal = calcular_stock("Pienso Gallinas", "Gallinas")
    s_pol = calcular_stock("Pienso Pollos", "Pollos")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pienso Gallinas", f"{s_gal:.1f} kg")
    c2.metric("Pienso Pollos", f"{s_pol:.1f} kg")
    c3.metric("Huevos Totales", f"{int(prod['huevos'].sum())} ud")
    c4.metric("Caja Real", f"{ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum():.2f} €")
    
    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.subheader("💰 Resumen Económico")
        v_real = ventas[ventas['tipo_venta'] == 'Venta Cliente']['cantidad'].sum()
        v_ahorro = ventas[ventas['tipo_venta'] == 'Consumo Propio']['cantidad'].sum()
        st.info(f"Ventas: {v_real:.2f} € | Ahorro Casa: {v_ahorro:.2f} €")
        st.warning(f"Inversión Total: {gastos['cantidad'].sum():.2f} €")
    with cb:
        if not prod.empty:
            st.subheader("🥚 Producción Reciente")
            st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

# --- IA VISUAL ---
elif menu == "📈 IA Crecimiento + 📸":
    st.title("📈 Seguimiento por Lote")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']} ({r['especie']})"):
            edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
            st.write(f"Edad: {edad} días")
            img = st.camera_input("Capturar", key=f"cam_{r['id']}")
            if img and st.button("Guardar Foto", key=f"btn_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                   (r['id'], datetime.now().strftime("%d/%m/%Y"), img.read())).connection.commit()
                st.success("Foto guardada en DB."); st.rerun()

# --- PRODUCCIÓN ---
elif menu == "🥚 Producción Diaria":
    st.title("🥚 Registro de Puesta")
    with st.form("p_form"):
        f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist())
        cant = st.number_input("Cantidad de huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", 
                               (f.strftime("%d/%m/%Y"), l_id, cant)).connection.commit(); st.rerun()

# --- HITOS ---
elif menu == "🌟 Hitos y Puestas":
    st.title("🌟 Registro de Hitos")
    with st.form("h_form"):
        l_id = st.selectbox("Lote", lotes['id'].tolist())
        tipo = st.selectbox("Hito", ["Primera Puesta", "Cambio Pienso", "Tratamiento"])
        f = st.date_input("Fecha")
        if st.form_submit_button("Registrar Hito"):
            get_conn().execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?,?,?)", 
                               (l_id, tipo, f.strftime("%d/%m/%Y"))).connection.commit(); st.rerun()

# --- VENTAS ---
elif menu == "💰 Ventas y Consumo":
    st.title("💰 Salida de Productos")
    with st.form("v_form"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l_id = st.selectbox("Lote Origen", lotes['id'].tolist())
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1)
        k = c2.number_input("Kilos (ilos_finale)", 0.0)
        p = c3.number_input("Precio/Valor €", 0.0)
        cli = st.text_input("Cliente/Nombre")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l_id, k, u)).connection.commit(); st.rerun()

# --- NAVIDAD ---
elif menu == "🎄 Plan Navidad":
    st.title("🎄 Planificador Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    for raza in ["Blanco Engorde", "Campero"]:
        f_compra = f_obj - timedelta(days=CONFIG_IA[raza]["madurez"])
        st.success(f"⚠️ **{raza}**: Comprar antes del **{f_compra.strftime('%d/%m/%Y')}**")

# --- GASTOS ---
elif menu == "💸 Gastos y Compras":
    st.title("💸 Registro de Gastos")
    with st.form("g_form"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Infraestructura", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe €", 0.0)
        kg = st.number_input("Kilos (ilos_pienso)", 0.0)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", 
                               (f.strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

# --- ALTA LOTES ---
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Alta de Nuevo Lote")
    with st.form("a_form"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cant", 1); ed = c2.number_input("Edad inicial", 0); pr = c3.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# --- HISTÓRICO ---
elif menu == "📜 Histórico y Borrado":
    st.title("📜 Consulta y Limpieza")
    t_name = st.selectbox("Selecciona Tabla", ["lotes", "gastos", "produccion", "ventas", "hitos", "bajas"])
    df = cargar(t_name)
    st.dataframe(df, use_container_width=True)
    st.divider()
    id_del = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ Eliminar Registro Definitivamente"):
        get_conn().execute(f"DELETE FROM {t_name} WHERE id=?", (id_del,)).connection.commit()
        st.error(f"ID {id_del} eliminado."); st.rerun()

# --- COPIAS Y RESTAURACIÓN ---
elif menu == "💾 COPIAS Y RESTAURACIÓN":
    st.title("💾 Gestión de Backups")
    st.subheader("1. Restaurar desde Excel")
    arch = st.file_uploader("Sube tu archivo .xlsx", type=["xlsx"])
    if arch and st.button("🚀 RESTAURAR TODO"):
        try:
            data = pd.read_excel(arch, sheet_name=None); conn = get_conn()
            for t_nom, df_temp in data.items():
                if t_nom in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                    conn.execute(f"DELETE FROM {t_nom}"); df_temp.to_sql(t_nom, conn, if_exists='append', index=False)
            conn.commit(); st.success("✅ Restauración completa."); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

    st.divider()
    st.subheader("2. Descargar Copias")
    if st.button("📊 Generar Excel Actual"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
            for t in ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"]:
                cargar(t).to_excel(wr, index=False, sheet_name=t)
        st.download_button("📥 Bajar Excel", out.getvalue(), "corral_backup.xlsx")
