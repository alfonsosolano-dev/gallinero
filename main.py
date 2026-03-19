import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# =================================================================
# BLOQUE 1: MOTOR DE DATOS (REFORZADO)
# =================================================================
st.set_page_config(page_title="CORRAL IA MAESTRO V45", layout="wide", page_icon="🚜")
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
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
        # PARCHES DE SEGURIDAD (Evitan errores de columnas faltantes)
        if n == "ventas":
            for col in ["unidades INTEGER", "ilos_finale REAL", "lote_id INTEGER"]:
                try: c.execute(f"ALTER TABLE ventas ADD COLUMN {col}")
                except: pass
        if n == "gastos":
            try: c.execute("ALTER TABLE gastos ADD COLUMN ilos_pienso REAL")
            except: pass
    conn.commit()
    conn.close()

def cargar_tabla(t):
    try:
        with get_conn() as conn: return pd.read_sql(f"SELECT * FROM {t}", conn)
    except: return pd.DataFrame()

# =================================================================
# BLOQUE 2: LÓGICA DE INTELIGENCIA ARTIFICIAL
# =================================================================
CONFIG_IA = {
    "Roja": {"cons_base": 0.110, "consejo": "Alta puesta. Calcio vital."},
    "Blanca": {"cons_base": 0.105, "consejo": "Vuelan mucho."},
    "Mochuela": {"cons_base": 0.095, "consejo": "Muy rústica."},
    "Blanco Engorde": {"cons_base": 0.180, "madurez": 55, "consejo": "Crecimiento rápido."},
    "Campero": {"cons_base": 0.140, "madurez": 90, "consejo": "Sabor excelente."}
}

def calcular_consumo_especifico(raza, edad, cantidad):
    base = CONFIG_IA.get(raza, {}).get("cons_base", 0.120)
    # Curva: Pollitos 30%, Jóvenes 60%, Adultos 100%
    factor = 0.3 if edad < 20 else (0.6 if edad < 45 else 1.0)
    return base * factor * cantidad

def obtener_balance_pienso(gastos, lotes):
    total_comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo_acumulado = 0
    consumo_hoy = 0
    if not lotes.empty:
        for _, r in lotes.iterrows():
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias_vividos = (datetime.now() - f_lote).days
            # Sumar consumo de cada día pasado
            for d in range(dias_vividos + 1):
                edad_d = r["edad_inicial"] + d
                consumo_acumulado += calcular_consumo_especifico(r['raza'], edad_d, r['cantidad'])
            # Consumo de hoy
            consumo_hoy += calcular_consumo_especifico(r['raza'], r["edad_inicial"] + dias_vividos, r['cantidad'])
    return max(0, total_comprado - consumo_acumulado), consumo_hoy

# =================================================================
# BLOQUE 3: VISTAS (TODO INTEGRADO)
# =================================================================

def vista_dashboard(prod, ventas, gastos, lotes):
    st.title("🏠 Dashboard Maestro")
    
    # Cálculos Financieros
    coste_animales = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
    otros_gastos = gastos['cantidad'].sum() if not gastos.empty else 0
    inv_total = coste_animales + otros_gastos
    
    ingresos = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    # Cálculos Pienso
    stock_real, c_hoy = obtener_balance_pienso(gastos, lotes)
    dias_margen = stock_real / c_hoy if c_hoy > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💸 Inversión Total", f"{inv_total:.2f} €", help="Lotes + Gastos")
    c2.metric("💰 Beneficio Neto", f"{(ingresos + ahorro) - inv_total:.2f} €")
    c3.metric("🔋 Stock Pienso", f"{stock_real:.1f} kg")
    c4.metric("⏳ Días Comida", f"{int(dias_margen)} d")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📊 Resumen Inversión")
        df_inv = pd.DataFrame({"Concepto": ["Animales", "Pienso/Otros"], "Euros": [coste_animales, otros_gastos]})
        st.bar_chart(df_inv.set_index("Concepto"))
    with col2:
        st.subheader("📈 Tendencia Producción")
        if not prod.empty:
            st.line_chart(prod.tail(10).set_index('fecha')['huevos'])

def vista_crecimiento(lotes):
    st.title("📈 IA Visual y Fotos")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']}"):
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_l).days + r["edad_inicial"]
            st.write(f"📅 Edad: {edad} días | 💡 {CONFIG_IA.get(r['raza'], {}).get('consejo','')}")
            c1, c2 = st.columns(2)
            with c1: cam = st.camera_input(f"Captura {r['id']}", key=f"c_{r['id']}")
            with c2: arch = st.file_uploader("Subir", type=['jpg','png'], key=f"f_{r['id']}")
            
            final = cam if cam else arch
            if final and st.button(f"Guardar Foto {r['id']}", key=f"b_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", (r['id'], datetime.now().strftime("%d/%m/%Y"), final.read())).connection.commit(); st.rerun()
            
            df_fotos = cargar_tabla("fotos")
            if not df_fotos.empty:
                f_lote = df_fotos[df_fotos['lote_id'] == r['id']]
                cols = st.columns(4)
                for i, fr in f_lote.tail(4).iterrows(): cols[f_lote.tail(4).index.get_loc(i)].image(fr['imagen'], caption=fr['fecha'])

# =================================================================
# BLOQUE 4: MENÚS Y NAVEGACIÓN
# =================================================================
inicializar_db()
lotes, ventas, prod, gastos = cargar_tabla("lotes"), cargar_tabla("ventas"), cargar_tabla("produccion"), cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard": vista_dashboard(prod, ventas, gastos, lotes)
elif menu == "📈 Crecimiento": vista_crecimiento(lotes)
elif menu == "🥚 Producción":
    st.title("🥚 Producción")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()

elif menu == "💰 Ventas":
    st.title("💰 Ventas y Salidas")
    with st.form("v"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades (Huevos/Pollos)", 1)
        k = st.number_input("Kg (para carne)", 0.0)
        p = st.number_input("Precio Total €", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades, ilos_finale) VALUES (?,?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), tipo, p, l, u, k)).connection.commit(); st.rerun()

elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Otros"])
        con = st.text_input("Concepto"); i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        f_g = st.date_input("Fecha del Gasto")
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", (f_g.strftime("%d/%m/%Y"), cat, con, i, kg)).connection.commit(); st.rerun()

elif menu == "🎄 Navidad":
    st.title("🎄 Navidad 2026")
    for rz, info in CONFIG_IA.items():
        if "madurez" in info:
            f_llegada = datetime(2026, 12, 20) - timedelta(days=info['madurez'])
            st.info(f"📍 **{rz}**: Para Navidad, comprarlos el **{f_llegada.strftime('%d/%m/%Y')}**")

elif menu == "🐣 Alta Lotes":
    st.title("🐣 Alta de Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad inicial", 0); pr = st.number_input("Precio ud €", 0.0)
        f_a = st.date_input("Fecha de entrada")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f_a.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

elif menu == "📜 Histórico":
    t = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t); st.dataframe(df)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar"): get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

elif menu == "💾 Copias":
    st.title("💾 Copias y Excel")
    if st.button("📥 Descargar Excel"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as w:
            for t in ["lotes", "gastos", "produccion", "ventas"]: cargar_tabla(t).to_excel(w, sheet_name=t, index=False)
        st.download_button("Guardar archivo", out.getvalue(), "Backup_Corral.xlsx")
    
    sub = st.file_uploader("Subir Backup", type="xlsx")
    if sub and st.button("🚀 Restaurar"):
        data = pd.read_excel(sub, sheet_name=None)
        conn = get_conn()
        for t in ["lotes", "gastos", "produccion", "ventas"]:
            if t in data: conn.execute(f"DELETE FROM {t}"); data[t].to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.success("¡Restaurado!"); st.rerun()
