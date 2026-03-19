import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# =================================================================
# BLOQUE 1: MOTOR DE DATOS (REPARACIÓN DE KILOS)
# =================================================================
st.set_page_config(page_title="CORRAL IA V46 - DESTINATARIOS", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL, destinado_a TEXT",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
        # PARCHES DE COLUMNAS (Para que lea bien tu Excel)
        if n == "gastos":
            for col in ["ilos_pienso REAL", "destinado_a TEXT"]:
                try: c.execute(f"ALTER TABLE gastos ADD COLUMN {col}")
                except: pass
        if n == "ventas":
            for col in ["unidades INTEGER", "ilos_finale REAL", "lote_id INTEGER"]:
                try: c.execute(f"ALTER TABLE ventas ADD COLUMN {col}")
                except: pass
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: LÓGICA DE CONSUMO
# =================================================================
CONFIG_IA = {
    "Roja": {"cons_base": 0.110}, "Blanca": {"cons_base": 0.105},
    "Mochuela": {"cons_base": 0.095}, "Blanco Engorde": {"cons_base": 0.180, "madurez": 55},
    "Campero": {"cons_base": 0.140, "madurez": 90}
}

def obtener_balance_pienso_maestro(gastos, lotes):
    # Suma de kilos de tu Excel (columna ilos_pienso)
    total_comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo_total = 0
    c_hoy = 0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias = (datetime.now() - f_lote).days
            for d in range(dias + 1):
                edad_d = r["edad_inicial"] + d
                base = CONFIG_IA.get(r['raza'], {"cons_base": 0.120})["cons_base"]
                f = 0.3 if edad_d < 20 else (0.6 if edad_d < 45 else 1.0)
                consumo_total += base * f * r['cantidad']
            if dias >= 0:
                c_hoy += CONFIG_IA.get(r['raza'], {"cons_base": 0.120})["cons_base"] * r['cantidad']
    return max(0, total_comprado - consumo_total), c_hoy

# =================================================================
# BLOQUE 3: INTERFAZ
# =================================================================
inicializar_db()
lotes, ventas, prod, gastos = cargar_tabla("lotes"), cargar_tabla("ventas"), cargar_tabla("produccion"), cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control")
    stock, choy = obtener_balance_pienso_maestro(gastos, lotes)
    inv = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
    inv += gastos['cantidad'].sum() if not gastos.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💸 Inversión Total", f"{inv:.2f} €")
    c2.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c3.metric("⏳ Autonomía", f"{int(stock/choy) if choy > 0 else 0} días")
    
    if stock <= 0: st.error("🚨 Según tus compras y el tiempo de los lotes, no debería quedar pienso.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📊 Gastos por Destinatario")
        if not gastos.empty and 'destinado_a' in gastos.columns:
            st.bar_chart(gastos.groupby('destinado_a')['cantidad'].sum())
    with col_b:
        st.subheader("🥚 Producción Reciente")
        if not prod.empty: st.line_chart(prod.tail(10).set_index('fecha')['huevos'])

elif menu == "💸 Gastos":
    st.title("💸 Registro de Gastos")
    with st.form("g_v46"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Infraestructura", "Otros"])
        # NUEVO DESPLEGABLE SOLICITADO
        dest = st.selectbox("A quién va dirigido", ["General (Ambos)", "Gallinas", "Pollos"])
        con = st.text_input("Concepto (ej: Saco Maíz Partido)")
        i = st.number_input("Importe €", 0.0)
        kg = st.number_input("Kilos (si es pienso)", 0.0)
        f_g = st.date_input("Fecha")
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)", 
                               (f_g.strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

elif menu == "📈 Crecimiento":
    st.title("📈 Fotos y Seguimiento")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}"):
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            st.write(f"Edad: {(datetime.now() - f_l).days + r['edad_inicial']} días")
            cam = st.camera_input("Foto", key=f"c_{r['id']}")
            if cam and st.button("Guardar", key=f"b_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", (r['id'], datetime.now().strftime("%d/%m/%Y"), cam.read())).connection.commit(); st.rerun()

elif menu == "💾 Copias":
    st.title("💾 Copias")
    if st.button("Descargar Excel"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            for t in ["lotes", "gastos", "produccion", "ventas"]: cargar_tabla(t).to_excel(w, sheet_name=t, index=False)
        st.download_button("Bajar Backup", out.getvalue(), "Backup_Corral.xlsx")
    sub = st.file_uploader("Restaurar", type="xlsx")
    if sub and st.button("Restaurar"):
        data = pd.read_excel(sub, sheet_name=None); conn = get_conn()
        for t in ["lotes", "gastos", "produccion", "ventas"]:
            if t in data: conn.execute(f"DELETE FROM {t}"); data[t].to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.rerun()

# Resto de menús (Producción, Ventas, Navidad, Alta Lotes, Histórico) mantenidos igual para seguridad
elif menu == "🥚 Producción":
    st.title("🥚 Producción")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()
elif menu == "💰 Ventas":
    st.title("💰 Ventas")
    with st.form("v"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades", 1); k = st.number_input("Kg", 0.0); p = st.number_input("Total €", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), tipo, p, l, k, u)).connection.commit(); st.rerun()
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    for rz, info in CONFIG_IA.items():
        if "madurez" in info:
            f_c = datetime(2026, 12, 20) - timedelta(days=info['madurez'])
            st.warning(f"📌 **{rz}**: Comprar antes del {f_c.strftime('%d/%m/%Y')}")
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Alta")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        cant = st.number_input("Cant", 1); ed = st.number_input("Edad", 0); pr = st.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()
elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
