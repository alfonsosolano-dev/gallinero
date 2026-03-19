import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# =================================================================
# BLOQUE 1: MOTOR DE DATOS (CON AUTO-REPARACIÓN DE COLUMNAS)
# =================================================================
st.set_page_config(page_title="CORRAL IA V38.0", layout="wide", page_icon="🚜")
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
        # PARCHE DE SEGURIDAD: Evita errores "OperationalError" si faltan columnas
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
# BLOQUE 2: INTELIGENCIA ARTIFICIAL Y LÓGICA
# =================================================================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons_base": 0.110, "consejo": "Alta puesta. Revisa el aporte de calcio."},
    "Blanca": {"puesta": 140, "cons_base": 0.105, "consejo": "Vuelan mucho. Se recomienda vallado alto."},
    "Mochuela": {"puesta": 210, "cons_base": 0.095, "consejo": "Rústica y muy resistente al clima."},
    "Blanco Engorde": {"madurez": 55, "cons_base": 0.180, "consejo": "Crecimiento rápido. Vigila las patas."},
    "Campero": {"madurez": 90, "cons_base": 0.140, "consejo": "Sabor excelente. Necesita espacio de pasto."}
}

def obtener_consejo(seccion):
    dict_c = {
        "ventas": "💡 IA: Las ventas suelen subir en festivos. Revisa tus existencias de huevos.",
        "gastos": "💡 IA: Comprar sacos de 25kg reduce el gasto anual un 12% frente a los de 5kg.",
        "produccion": "💡 IA: Las horas de luz influyen en la puesta. Mantén un ciclo estable.",
        "crecimiento": "💡 IA: El seguimiento visual ayuda a detectar problemas de plumaje o salud antes de que sea tarde."
    }
    st.info(dict_c.get(seccion, "Gestión optimizada por IA."))

def calcular_consumo_diario(raza, edad, cantidad):
    base = CONFIG_IA.get(raza, {}).get("cons_base", 0.120)
    factor = 0.3 if edad < 20 else (0.6 if edad < 45 else 1.0)
    return base * factor * cantidad

# =================================================================
# BLOQUE 3: VISTAS MODULARES
# =================================================================

def vista_dashboard(prod, ventas, gastos, lotes):
    st.title("🏠 Panel de Control Maestro")
    
    # Cálculos Financieros y de Stock
    t_producido = prod['huevos'].sum() if not prod.empty else 0
    t_salidas = ventas['unidades'].sum() if not ventas.empty else 0
    stock_huevos = t_producido - t_salidas

    v_cliente = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    ahorro_casa = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    inversion = gastos['cantidad'].sum() if not gastos.empty else 0
    beneficio = (v_cliente + ahorro_casa) - inversion

    # Métricas Superiores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🥚 Stock Huevos", f"{int(stock_huevos)} ud")
    c2.metric("💸 Inversión", f"{inversion:.2f} €")
    c3.metric("💰 Caja (Ventas)", f"{v_cliente:.2f} €")
    c4.metric("🏠 Ahorro Casa", f"{ahorro_casa:.2f} €")
    
    st.metric("🚀 Beneficio Neto (Caja + Ahorro - Inversión)", f"{beneficio:.2f} €", delta=f"{beneficio:.2f} €")

    st.divider()

    # Tabla de Consumo hoy
    st.subheader("📊 Consumo de Pienso Estimado (Hoy)")
    if not lotes.empty:
        cons_lista = []
        for _, r in lotes.iterrows():
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_lote).days + r["edad_inicial"]
            c_dia = calcular_consumo_diario(r['raza'], edad, r['cantidad'])
            cons_lista.append({
                "Lote": r['id'], 
                "Especie": r['especie'], 
                "Raza": r['raza'], 
                "Edad": f"{edad} días", 
                "Kg/Día": round(c_dia, 3)
            })
        st.table(pd.DataFrame(cons_lista))
    
    if not prod.empty:
        st.subheader("📈 Evolución de la Puesta")
        st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

def vista_crecimiento(lotes):
    st.title("📈 Crecimiento e IA Visual")
    obtener_consejo("crecimiento")
    if lotes.empty: st.warning("No hay lotes registrados."); return
    
    for _, r in lotes.iterrows():
        with st.expander(f"Lote {r['id']} - {r['raza']} ({r['especie']})", expanded=True):
            f_lote = datetime.strptime(r["fecha"], "%d/%m/%Y")
            edad = (datetime.now() - f_lote).days + r["edad_inicial"]
            st.write(f"📅 **Edad:** {edad} días. | {CONFIG_IA.get(r['raza'], {}).get('consejo', '')}")
            
            c1, c2 = st.columns(2)
            with c1: img_cam = st.camera_input(f"Capturar {r['id']}", key=f"cam_{r['id']}")
            with c2:
                img_file = st.file_uploader("O subir foto historial", type=['jpg','png','jpeg'], key=f"file_{r['id']}")
                f_foto = st.date_input("Fecha de la foto", datetime.now(), key=f"date_{r['id']}")

            img_final = img_cam if img_cam else img_file
            if img_final and st.button(f"Guardar Imagen Lote {r['id']}", key=f"btn_{r['id']}"):
                get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen) VALUES (?,?,?)", 
                                   (r['id'], f_foto.strftime("%d/%m/%Y"), img_final.read())).connection.commit()
                st.success("Foto guardada correctamente."); st.rerun()

            # Galería del Lote
            df_f = cargar_tabla("fotos")
            if not df_f.empty:
                f_lote = df_f[df_f['lote_id'] == r['id']]
                if not f_lote.empty:
                    st.write("Últimas capturas:")
                    cols = st.columns(4)
                    for i, f_row in f_lote.tail(4).iterrows():
                        cols[f_lote.tail(4).index.get_loc(i)].image(f_row['imagen'], caption=f_row['fecha'])

def vista_produccion(lotes):
    st.title("🥚 Producción")
    obtener_consejo("produccion")
    with st.form("form_prod"):
        f = st.date_input("Fecha")
        l = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        h = st.number_input("Cantidad de Huevos", 1)
        if st.form_submit_button("Registrar Producción"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", 
                               (f.strftime("%d/%m/%Y"), l, h)).connection.commit(); st.rerun()

def vista_ventas(lotes):
    st.title("💰 Ventas y Salidas")
    obtener_consejo("ventas")
    with st.form("form_ventas"):
        tipo = st.radio("Tipo de Salida", ["Venta Cliente", "Consumo Propio"])
        l = st.selectbox("Lote de origen", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades", 1)
        k = c2.number_input("Kg finales (carne)", 0.0)
        p = c3.number_input("Importe Total €", 0.0)
        cli = st.text_input("Cliente o Familia (Destino)")
        if st.form_submit_button("Guardar Registro"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, l, k, u)).connection.commit(); st.rerun()

def vista_gastos():
    st.title("💸 Gastos e Inversión")
    obtener_consejo("gastos")
    with st.form("form_gastos"):
        cat = st.selectbox("Categoría", ["Pienso", "Medicina", "Infraestructura", "Otros"])
        con = st.text_input("Concepto (Ej: Saco 25kg)")
        c1, c2 = st.columns(2)
        imp = c1.number_input("Importe en €", 0.0)
        kg = c2.number_input("Kg de pienso comprados", 0.0)
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)", 
                               (datetime.now().strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

def vista_navidad():
    st.title("🎄 Planificador Navidad 2026")
    st.write("Fechas límite para comprar pollos y que lleguen al peso ideal el 20 de diciembre:")
    f_obj = datetime(2026, 12, 20)
    for raza, info in CONFIG_IA.items():
        if "madurez" in info:
            f_compra = f_obj - timedelta(days=info['madurez'])
            st.success(f"📌 **{raza}**: Debes comprarlos antes del **{f_compra.strftime('%d/%m/%Y')}**")

def vista_alta():
    st.title("🐣 Alta de Nuevos Lotes")
    with st.form("form_alta"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad", 1)
        ed = c2.number_input("Edad inicial (días)", 0)
        pr = c3.number_input("Precio por unidad", 0.0)
        f = st.date_input("Fecha de llegada")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                               (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

# =================================================================
# BLOQUE 4: NAVEGACIÓN Y CARGA
# =================================================================
inicializar_db()
lotes = cargar_tabla("lotes")
ventas = cargar_tabla("ventas")
prod = cargar_tabla("produccion")
gastos = cargar_tabla("gastos")

menu = st.sidebar.radio("MENÚ PRINCIPAL:", ["🏠 Dashboard", "📈 Crecimiento", "🥚 Producción", "💰 Ventas", "💸 Gastos", "🎄 Navidad", "🐣 Alta Lotes", "📜 Histórico", "💾 Copias"])

if menu == "🏠 Dashboard": 
    vista_dashboard(prod, ventas, gastos, lotes)
elif menu == "📈 Crecimiento": 
    vista_crecimiento(lotes)
elif menu == "🥚 Producción": 
    vista_produccion(lotes)
elif menu == "💰 Ventas": 
    vista_ventas(lotes)
elif menu == "💸 Gastos": 
    vista_gastos()
elif menu == "🎄 Navidad": 
    vista_navidad()
elif menu == "🐣 Alta Lotes": 
    vista_alta()
elif menu == "💾 Copias":
    st.title("💾 Copias de Seguridad")
    arch = st.file_uploader("Subir Excel de Restauración", type=["xlsx"])
    if arch and st.button("🚀 Restaurar Datos"):
        data = pd.read_excel(arch, sheet_name=None)
        conn = get_conn()
        for t, df in data.items():
            if t in ["lotes", "gastos", "produccion", "ventas"]:
                conn.execute(f"DELETE FROM {t}")
                df.to_sql(t, conn, if_exists='append', index=False)
        conn.commit(); st.success("Base de datos restaurada."); st.rerun()
elif menu == "📜 Histórico":
    st.title("📜 Histórico y Borrado")
    t = st.selectbox("Selecciona la tabla para revisar:", ["lotes", "gastos", "produccion", "ventas", "fotos"])
    df_h = cargar_tabla(t)
    st.dataframe(df_h, use_container_width=True)
    id_del = st.number_input("ID del registro a eliminar:", 0)
    if st.button("🗑️ Eliminar Registro Permanentemente"):
        get_conn().execute(f"DELETE FROM {t} WHERE id={id_del}").connection.commit()
        st.warning(f"Registro {id_del} eliminado de {t}."); st.rerun()
