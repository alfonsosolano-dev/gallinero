import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io

# =================================================================
# BLOQUE 1: CONFIGURACIÓN Y BASE DE DATOS (CON AUTO-REPARACIÓN)
# =================================================================
st.set_page_config(page_title="CORRAL IA PROFESIONAL V40", layout="wide", page_icon="🚜")
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
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
        # Parches de seguridad para columnas nuevas
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
# BLOQUE 2: INTELIGENCIA ARTIFICIAL (LOGICA Y CONSEJOS)
# =================================================================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons_base": 0.110, "consejo": "Alta puesta. Revisa el aporte de calcio."},
    "Blanca": {"puesta": 140, "cons_base": 0.105, "consejo": "Vuelan mucho. Vallado alto recomendado."},
    "Mochuela": {"puesta": 210, "cons_base": 0.095, "consejo": "Rústica y muy resistente."},
    "Blanco Engorde": {"madurez": 55, "cons_base": 0.180, "consejo": "Crecimiento rápido. Vigila humedad cama."},
    "Campero": {"madurez": 90, "cons_base": 0.140, "consejo": "Sabor excelente. Necesita pastoreo."}
}

def obtener_consejo(seccion):
    consejos = {
        "ventas": "💡 IA: Las ventas de huevos suelen subir un 20% en vísperas de festivos.",
        "gastos": "💡 IA: Comprar pienso por palet puede ahorrarte hasta 0.15€/kg.",
        "produccion": "💡 IA: Si la puesta baja repentinamente, revisa el acceso al agua.",
        "crecimiento": "💡 IA: El seguimiento visual permite detectar picaje de plumas a tiempo."
    }
    st.info(consejos.get(seccion, "Gestión optimizada."))

def calcular_consumo_diario(raza, edad, cantidad):
    base = CONFIG_IA.get(raza, {}).get("cons_base", 0.120)
    factor = 0.3 if edad < 20 else (0.6 if edad < 45 else 1.0)
    return base * factor * cantidad

# =================================================================
# BLOQUE 3: VISTAS PRINCIPALES
# =================================================================

def vista_dashboard(prod, ventas, gastos, lotes):
    st.title("🏠 Panel de Control Maestro")
    
    # Cálculos Pro
    t_huevos = prod['huevos'].sum() if not prod.empty else 0
    t_ventas_u = ventas['unidades'].sum() if not ventas.empty else 0
    stock = t_huevos - t_ventas_u
    
    ingresos = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    inversion = gastos['cantidad'].sum() if not gastos.empty else 0
    neto = (ingresos + ahorro) - inversion

    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🥚 Stock Huevos", f"{int(stock)} ud")
    c2.metric("💸 Inversión Total", f"{inversion:.2f} €")
    c3.metric("💰 Caja (Ventas)", f"{ingresos:.2f} €")
    c4.metric("🏠 Ahorro Propio", f"{ahorro:.2f} €")
    
    st.metric("🚀 BENEFICIO REAL (Caja + Ahorro - Gastos)", f"{neto:.2f} €", delta=f"{neto:.2f} €")

    st.divider()
    # Tabla de Consumo por Especie
    if not lotes.empty:
        st.subheader("📊 Consumo de Pienso Estimado (Hoy)")
        detalles = []
        for _, r in lotes.iterrows():
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_l).days + r["edad_inicial"]
            cons = calcular_consumo_diario(r['raza'], edad, r['cantidad'])
            detalles.append({"Lote": r['id'], "Especie": r['especie'], "Raza": r['raza'], "Edad": f"{edad} días", "Kg/Día": round(cons, 3)})
        st.table(pd.DataFrame(detalles))

def vista_crecimiento(lotes):
    st.title("📈 Crecimiento e IA Visual")
    obtener_consejo("crecimiento")
    if lotes.empty: st.warning("No hay lotes activos."); return
    
    for _, r in lotes.iterrows():
        with st.expander(f"LOTE {r['id']} - {r['raza']}", expanded=True):
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_l).days + r["edad_inicial"]
            st.write(f"📅 **Edad actual:** {edad} días | {CONFIG_IA.get(r['raza'], {}).get('consejo','')}")
            
            c1, c2 = st.columns(2)
            with c1: img_cam = st.camera_input(f"Captura Lote {r['id']}", key=f"c_{r['id']}")
            with c2: 
                img_f = st.file_uploader("Subir foto", type=['jpg','png','jpeg'], key=f"f_{r['id']}")
                f_f = st.date_input("Fecha foto", datetime.now(), key=f"d_{r['id']}")

            final = img_cam if img_cam else img_f
            if final and st.button(f"Guardar Foto Lote {r['id']}", key=f"b_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                   (r['id'], f_f.strftime("%d/%m/%Y"), final.read())).connection.commit()
                st.success("Foto guardada."); st.rerun()

            # Galería
            df_fotos = cargar_tabla("fotos")
            if not df_fotos.empty:
                f_lote = df_fotos[df_fotos['lote_id'] == r['id']]
                if not f_lote.empty:
                    cols = st.columns(4)
                    for i, fr in f_lote.tail(4).iterrows():
                        cols[f_lote.tail(4).index.get_loc(i)].image(fr['imagen'], caption=fr['fecha'])

# =================================================================
# BLOQUE 4: GESTIÓN DE COPIAS Y EXCEL
# =================================================================
def vista_copias():
    st.title("💾 Copias de Seguridad (Excel)")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📥 Descargar Datos")
        if st.button("Generar Excel de Backup"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
                    cargar_tabla(t).to_excel(writer, sheet_name=t, index=False)
            st.download_button(label="⬇️ Descargar archivo .xlsx", data=output.getvalue(), 
                               file_name=f"Backup_Corral_{datetime.now().strftime('%d_%m_%Y')}.xlsx")
    
    with c2:
        st.subheader("🚀 Restaurar Sistema")
        arch = st.file_uploader("Subir Backup .xlsx", type=["xlsx"])
        if arch and st.button("RESTAURAR AHORA"):
            data = pd.read_excel(arch, sheet_name=None)
            conn = get_conn()
            for t in ["lotes", "gastos", "produccion", "ventas"]:
                if t in data:
                    conn.execute(f"DELETE FROM {t}")
                    data[t].to_sql(t, conn, if_exists='append', index=False)
            conn.commit(); st.success("Sistema restaurado con éxito."); st.rerun()

# =================================================================
# BLOQUE 5: NAVEGACIÓN Y RESTO DE FUNCIONES
# =================================================================
inicializar_db()
lotes, ventas, prod, gastos = cargar_tabla("lotes"), cargar_tabla("ventas"), cargar_tabla("produccion"), cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard": vista_dashboard(prod, ventas, gastos, lotes)
elif menu == "📈 Crecimiento": vista_crecimiento(lotes)
elif menu == "🥚 Producción":
    st.title("🥚 Producción Diaria")
    obtener_consejo("produccion")
    with st.form("p"):
        f = st.date_input("Fecha"); l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Huevos recogidos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()
elif menu == "💰 Ventas":
    st.title("💰 Ventas / Consumo Propio")
    obtener_consejo("ventas")
    with st.form("v"):
        tipo = st.radio("Tipo", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        u = st.number_input("Unidades (Huevos/Pollos)", 1); k = st.number_input("Kg finales", 0.0); p = st.number_input("Euros Total €", 0.0)
        cli = st.text_input("Cliente/Destino")
        if st.form_submit_button("Registrar Salida"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()
elif menu == "💸 Gastos":
    st.title("💸 Gastos e Inversión")
    obtener_consejo("gastos")
    with st.form("g"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Otros"]); con = st.text_input("Concepto")
        i = st.number_input("Importe €", 0.0); kg = st.number_input("Kg Pienso", 0.0)
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y"), cat, con, i, kg)).connection.commit(); st.rerun()
elif menu == "🎄 Navidad":
    st.title("🎄 Plan Navidad 2026")
    f_obj = datetime(2026, 12, 20)
    for rz, info in CONFIG_IA.items():
        if "madurez" in info: st.success(f"📌 **{rz}**: Comprar antes del {(f_obj - timedelta(days=info['madurez'])).strftime('%d/%m/%Y')}")
elif menu == "🐣 Alta Lotes":
    st.title("🐣 Alta de Lote")
    with st.form("a"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"]); rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad", 1); ed = c2.number_input("Edad inicial", 0); pr = c3.number_input("Precio Ud", 0.0)
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (datetime.now().strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()
elif menu == "💾 Copias": vista_copias()
elif menu == "📜 Histórico":
    st.title("📜 Histórico y Borrado")
    t = st.selectbox("Tabla:", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df = cargar_tabla(t)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", 0)
    if st.button("Eliminar Permanentemente"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={idx}").connection.commit(); st.rerun()
