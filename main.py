import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# =================================================================
# BLOQUE 1: MOTOR DE DATOS (NÚCLEO V47.0)
# =================================================================
st.set_page_config(page_title="CORRAL IA V47 - OMNI", layout="wide", page_icon="🚜")
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
        # PARCHES DE COMPATIBILIDAD (Asegura que las columnas de versiones anteriores existan)
        columnas_extra = {
            "gastos": ["ilos_pienso REAL", "destinado_a TEXT"],
            "ventas": ["unidades INTEGER", "ilos_finale REAL", "lote_id INTEGER", "cliente TEXT", "tipo_venta TEXT"]
        }
        if n in columnas_extra:
            for col in columnas_extra[n]:
                try: c.execute(f"ALTER TABLE {n} ADD COLUMN {col}")
                except: pass
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: INTELIGENCIA DE CONSUMO
# =================================================================
CONFIG_IA = {
    "Roja": {"cons_base": 0.110}, "Blanca": {"cons_base": 0.105},
    "Mochuela": {"cons_base": 0.095}, "Blanco Engorde": {"cons_base": 0.180, "madurez": 55},
    "Campero": {"cons_base": 0.140, "madurez": 90}
}

def calcular_balance_pienso_v47(gastos, lotes):
    # Sumamos los kilos de la columna 'ilos_pienso' de tus registros
    total_comprado = gastos['ilos_pienso'].sum() if not gastos.empty and 'ilos_pienso' in gastos.columns else 0
    consumo_acumulado = 0
    consumo_hoy = 0
    
    if not lotes.empty:
        for _, r in lotes.iterrows():
            try:
                f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
                dias_desde_llegada = (datetime.now() - f_lote).days
                
                # Cálculo día a día para precisión absoluta
                for d in range(dias_desde_llegada + 1):
                    edad_ese_dia = r["edad_inicial"] + d
                    base = CONFIG_IA.get(r['raza'], {"cons_base": 0.120})["cons_base"]
                    # Factor de crecimiento según edad
                    factor = 0.3 if edad_ese_dia < 20 else (0.6 if edad_ese_dia < 45 else 1.0)
                    consumo_acumulado += base * factor * r['cantidad']
                
                # Consumo de hoy para métrica de autonomía
                consumo_hoy += CONFIG_IA.get(r['raza'], {"cons_base": 0.120})["cons_base"] * r['cantidad']
            except: continue
            
    stock_final = total_comprado - consumo_acumulado
    return max(0, stock_final), consumo_hoy

# =================================================================
# BLOQUE 3: INTERFAZ Y NAVEGACIÓN
# =================================================================
inicializar_db()
lotes, ventas, prod, gastos = cargar_tabla("lotes"), cargar_tabla("ventas"), cargar_tabla("produccion"), cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control Maestro")
    stock, c_hoy = calcular_balance_pienso_v47(gastos, lotes)
    
    # Inversión = Coste Lotes + Gastos Totales
    coste_animales = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
    total_gastos = gastos['cantidad'].sum() if not gastos.empty else 0
    inv_total = coste_animales + total_gastos
    
    ingresos = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💸 Inversión Total", f"{inv_total:.2f} €")
    c2.metric("💰 Beneficio Real", f"{(ingresos + ahorro) - inv_total:.2f} €")
    c3.metric("🔋 Stock Pienso", f"{stock:.1f} kg")
    c4.metric("⏳ Autonomía", f"{int(stock/c_hoy) if c_hoy > 0 else 0} d")

    if stock <= 2: st.warning("⚠️ Stock crítico o agotado. Revisa tus registros de kilos en 'Gastos'.")

    col_izq, col_der = st.columns(2)
    with col_izq:
        st.subheader("📊 Gastos por Destinatario")
        if not gastos.empty and 'destinado_a' in gastos.columns:
            st.bar_chart(gastos.groupby('destinado_a')['cantidad'].sum())
    with col_der:
        st.subheader("🥚 Producción (Últimos 15 días)")
        if not prod.empty: st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

elif menu == "💸 Gastos":
    st.title("💸 Registro de Gastos")
    with st.form("g_v47"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Infraestructura", "Otros"])
        dest = st.selectbox("Destinado a", ["General (Ambos)", "Gallinas", "Pollos"])
        con = st.text_input("Concepto (ej: Saco Maíz o Pienso Ponedoras)")
        i = st.number_input("Importe (€)", 0.0)
        kg = st.number_input("Kilos de Pienso (IMPORTANTE)", 0.0)
        f_g = st.date_input("Fecha", datetime.now())
        if st.form_submit_button("Registrar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso, destinado_a) VALUES (?,?,?,?,?,?)", 
                               (f_g.strftime("%d/%m/%Y"), cat, con, i, kg, dest)).connection.commit(); st.rerun()

elif menu == "📈 Crecimiento":
    st.title("📈 Fotos y Evolución")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']} ({r['cantidad']} uds)"):
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_l).days + r['edad_inicial']
            st.write(f"📅 Edad: {edad} días")
            img = st.camera_input("Capturar", key=f"cam_{r['id']}")
            if img and st.button("Guardar Foto", key=f"sav_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", (r['id'], datetime.now().strftime("%d/%m/%Y"), img.read())).connection.commit(); st.rerun()

elif menu == "💰 Ventas":
    st.title("💰 Ventas y Consumo")
    with st.form("v_v47"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades", 1); k = st.number_input("Kg Carne", 0.0); p = st.number_input("Total €", 0.0)
        cli = st.text_input("Cliente/Destino")
        if st.form_submit_button("Ok"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()

elif menu == "📜 Histórico":
    st.title("📜 Histórico")
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("Borrar ID", 0)
    if st.button("Borrar Registro"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

elif menu == "💾 Copias":
    st.title("💾 Copias de Seguridad")
    if st.button("📥 Descargar Excel"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            for t in ["lotes", "gastos", "produccion", "ventas"]: cargar_tabla(t).to_excel(w, sheet_name=t, index=False)
        st.download_button("Guardar archivo", out.getvalue(), "Backup_Corral.xlsx")
    sub = st.file_uploader("Subir Backup", type="xlsx")
    if sub and st.button("🚀 Restaurar"):
        data = pd.read_excel(sub, sheet_name=None); conn = get_conn()
        for t in ["lotes", "gastos", "produccion", "ventas"]:
            if t in data: conn.execute(f"DELETE FROM {t}"); data[t].to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.rerun()

# Submenús adicionales mantenidos para integridad
elif menu == "🥚 Producción":
    st.title("🥚 Puesta")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos", 1)
        if st.form_submit_button("Ok"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    for rz, info in CONFIG_IA.items():
        if "madurez" in info:
            f_c = datetime(2026, 12, 20) - timedelta(days=info['madurez'])
            st.info(f"📌 **{rz}**: Comprar antes del {f_c.strftime('%d/%m/%Y')}")
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Alta")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        cant = st.number_input("Cant", 1); ed = st.number_input("Edad", 0); pr = st.number_input("Precio ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Crear"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()
