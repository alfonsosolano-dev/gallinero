import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# =================================================================
# BLOQUE 1: MOTOR DE DATOS (AUTO-REPARABLE)
# =================================================================
st.set_page_config(page_title="CORRAL IA V44 - FINAL", layout="wide", page_icon="🚜")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Esquema maestro de todas las tablas necesarias
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
        # Parches de seguridad para evitar OperationalError (columnas faltantes)
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
# BLOQUE 2: LÓGICA DE CONSUMO Y COSTES
# =================================================================
CONFIG_IA = {
    "Roja": {"cons_base": 0.110}, "Blanca": {"cons_base": 0.105},
    "Mochuela": {"cons_base": 0.095}, "Blanco Engorde": {"cons_base": 0.180, "madurez": 55},
    "Campero": {"cons_base": 0.140, "madurez": 90}
}

def calcular_consumo_dia_exacto(raza, edad, cantidad):
    base = CONFIG_IA.get(raza, {}).get("cons_base", 0.120)
    # Curva de crecimiento: pollitos (30%), jóvenes (60%), adultos (100%)
    factor = 0.3 if edad < 20 else (0.6 if edad < 45 else 1.0)
    return base * factor * cantidad

def obtener_balance_pienso_real(gastos, lotes):
    total_comprado = gastos['ilos_pienso'].sum() if not gastos.empty else 0
    consumo_historico = 0
    consumo_hoy = 0
    
    if not lotes.empty:
        for _, r in lotes.iterrows():
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias_en_corral = (datetime.now() - f_lote).days
            # Sumamos lo que ha comido cada día desde que llegó
            for d in range(dias_en_corral + 1):
                edad_viva = r["edad_inicial"] + d
                consumo_historico += calcular_consumo_dia_exacto(r['raza'], edad_viva, r['cantidad'])
            # Consumo específico de hoy para la alerta
            consumo_hoy += calcular_consumo_dia_exacto(r['raza'], r["edad_inicial"] + dias_en_corral, r['cantidad'])
            
    return max(0, total_comprado - consumo_historico), consumo_hoy

# =================================================================
# BLOQUE 3: INTERFAZ VISUAL
# =================================================================
def vista_dashboard(prod, ventas, gastos, lotes):
    st.title("🏠 Panel de Control Sincronizado")

    # 1. CÁLCULOS DE DINERO
    coste_animales = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
    otros_gastos = gastos['cantidad'].sum() if not gastos.empty else 0
    inv_total = coste_animales + otros_gastos
    
    ingresos_ventas = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro_casa = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    beneficio = (ingresos_ventas + ahorro_casa) - inv_total

    # 2. CÁLCULOS DE PIENSO
    stock_real, c_hoy = obtener_balance_pienso_real(gastos, lotes)
    dias_stock = stock_real / c_hoy if c_hoy > 0 else 0

    # MÉTRICAS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💸 Inversión Total", f"{inv_total:.2f} €", help="Lotes + Gastos manuales")
    c2.metric("💰 Beneficio Real", f"{beneficio:.2f} €", delta=f"{ahorro_casa:.2f} € Ahorro")
    c3.metric("🔋 Pienso Real", f"{stock_real:.1f} kg", help="Sacos menos consumo acumulado")
    c4.metric("⏳ Autonomía", f"{int(dias_stock)} días")

    if stock_real <= 0:
        st.error("🚨 ALERTA: Sin existencias de pienso en el sistema. Registra una compra en 'Gastos'.")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📊 Distribución de Gastos")
        df_inv = pd.DataFrame({"Concepto": ["Animales", "Pienso/Otros"], "Euros": [coste_animales, otros_gastos]})
        st.bar_chart(df_inv.set_index("Concepto"))
    with col_b:
        st.subheader("📈 Producción de Huevos")
        if not prod.empty:
            df_p = prod.tail(15).copy()
            st.line_chart(df_p.set_index('fecha')['huevos'])

def vista_crecimiento(lotes):
    st.title("📈 IA Visual y Seguimiento")
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']} (Ver detalles)"):
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_l).days + r["edad_inicial"]
            st.info(f"📅 Edad actual: {edad} días. Recomendación: {CONFIG_IA.get(r['raza'], {}).get('cons_base', 0)*1000:.0f}g/ave.")
            
            c1, c2 = st.columns(2)
            with c1: cam = st.camera_input(f"Foto hoy {r['id']}", key=f"cam_{r['id']}")
            with c2: sub = st.file_uploader("O subir archivo", type=['jpg','png'], key=f"sub_{r['id']}")
            
            final = cam if cam else sub
            if final and st.button(f"Guardar Foto Lote {r['id']}", key=f"btn_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                   (r['id'], datetime.now().strftime("%d/%m/%Y"), final.read())).connection.commit()
                st.success("¡Foto guardada!"); st.rerun()

# =================================================================
# NAVEGACIÓN Y MENÚS
# =================================================================
inicializar_db()
lotes, ventas, prod, gastos = cargar_tabla("lotes"), cargar_tabla("ventas"), cargar_tabla("produccion"), cargar_tabla("gastos")

menu = st.sidebar.radio("GESTIÓN:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard": 
    vista_dashboard(prod, ventas, gastos, lotes)

elif menu == "📈 Crecimiento": 
    vista_crecimiento(lotes)

elif menu == "🥚 Producción":
    st.title("🥚 Registro de Puesta")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Cantidad de Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()

elif menu == "💰 Ventas":
    st.title("💰 Salida de Productos")
    with st.form("v"):
        tipo = st.radio("Destino", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades", 1); p = st.number_input("Euros (€)", 0.0)
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, tipo_venta, cantidad, lote_id, unidades) VALUES (?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), tipo, p, l, u)).connection.commit(); st.rerun()

elif menu == "💸 Gastos":
    st.title("💸 Compras y Gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Infraestructura", "Otros"])
        con = st.text_input("Concepto (ej: Saco 25kg Ponedoras)")
        i = st.number_input("Importe (€)", 0.0)
        kg = st.number_input("Kilos (solo si es Pienso)", 0.0)
        if st.form_submit_button("Añadir Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg)).connection.commit(); st.rerun()

elif menu == "🎄 Navidad":
    st.title("🎄 Planificador Navidad 2026")
    for rz, info in CONFIG_IA.items():
        if "madurez" in info:
            f_target = datetime(2026, 12, 20) - timedelta(days=info['madurez'])
            st.warning(f"👉 Para tener **{rz}** listos en Navidad, debes comprarlos antes del: {f_target.strftime('%d/%m/%Y')}")

elif menu == "🐣 Alta Lotes":
    st.title("🐣 Entrada de Nuevos Animales")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        cant = st.number_input("Cantidad", 1); ed = st.number_input("Edad inicial (días)", 0)
        pr = st.number_input("Precio por unidad (€)", 0.0)
        f_ent = st.date_input("Fecha de llegada")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (f_ent.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

elif menu == "📜 Histórico":
    st.title("📜 Histórico de Datos")
    t = st.selectbox("Seleccionar Tabla", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t)
    st.write(f"Mostrando {len(df)} registros:")
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID del registro a eliminar", 0)
    if st.button("Eliminar Permanentemente"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()

elif menu == "💾 Copias":
    st.title("💾 Gestión de Seguridad")
    if st.button("📥 Descargar todo en Excel"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for t in ["lotes", "gastos", "produccion", "ventas"]: cargar_tabla(t).to_excel(writer, sheet_name=t, index=False)
        st.download_button("Guardar archivo", output.getvalue(), "Backup_Corral_IA.xlsx")
    
    subida = st.file_uploader("Restaurar desde Excel", type="xlsx")
    if subida and st.button("🚀 Restaurar Sistema"):
        data = pd.read_excel(subida, sheet_name=None)
        conn = get_conn()
        for t in ["lotes", "gastos", "produccion", "ventas"]:
            if t in data:
                conn.execute(f"DELETE FROM {t}")
                data[t].to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.success("Sistema restaurado con éxito."); st.rerun()
