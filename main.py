import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
import io
from PIL import Image

# ====================== 1. NÚCLEO DE DATOS Y AUTO-RESTAURACIÓN ======================
st.set_page_config(page_title="CORRAL IA V21.0 - IA VISUAL", layout="wide", page_icon="📸")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_bunker_visual():
    conn = get_conn()
    c = conn.cursor()
    tablas = {
        "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
        "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
        "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL",
        "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, kilos_finales REAL, unidades INTEGER",
        "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT",
        "hitos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT",
        # NUEVA TABLA PARA FOTOS (Usamos BLOB para guardar la imagen dentro de la DB)
        "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota TEXT"
    }
    for n, e in tablas.items(): c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
    
    # --- AUTO-RECUPERACIÓN DE DATOS (Basado en tus capturas) ---
    c.execute("SELECT count(*) FROM lotes")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO lotes (id, fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", [
            (2, '21/02/2026', 'Gallinas', 'Blanca', 3, 80, 7.2, 'Activo'),
            (3, '28/02/2026', 'Gallinas', 'Roja', 2, 80, 7.2, 'Activo'),
            (5, '21/02/2026', 'Gallinas', 'Roja', 2, 80, 7.2, 'Activo'),
            (7, '21/02/2026', 'Pollos', 'Blanco Engorde', 2, 15, 2.4, 'Activo'),
            (8, '21/02/2026', 'Pollos', 'Campero', 2, 15, 2.4, 'Activo'),
            (9, '18/03/2026', 'Gallinas', 'Mochuela', 1, 80, 8.5, 'Activo')
        ])
        c.executemany("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", [
            ('21/02/2026', 'Otros', 'infraestructura', 100.0, 0),
            ('21/02/2026', 'Pienso Gallinas', 'saco', 14.0, 25),
            ('21/02/2026', 'Pienso Pollos', 'saco maiz', 13.0, 30)
        ])
        c.execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (5, 'Primera Puesta', '14/03/2026')")
        conn.commit()
    conn.close()

inicializar_bunker_visual()

# ====================== 2. CONFIGURACIÓN IA BIOLÓGICA ======================
CONFIG_IA = {
    "Roja": {"puesta": 145, "cons": 0.120},
    "Blanca": {"puesta": 140, "cons": 0.115},
    "Mochuela": {"puesta": 210, "cons": 0.100},
    "Blanco Engorde": {"madurez": 55, "cons": 0.210},
    "Campero": {"madurez": 90, "cons": 0.150}
}

def cargar(t, l_id=None):
    with get_conn() as conn:
        if l_id: return pd.read_sql(f"SELECT * FROM {t} WHERE lote_id={l_id} ORDER BY id DESC", conn)
        return pd.read_sql(f"SELECT * FROM {t}", conn)

# ====================== 3. INTERFAZ Y DESPLIEGUE ======================
st.sidebar.title("🤖 CORRAL IA VISUAL V21.0")
menu = st.sidebar.radio("MENÚ:", [
    "🏠 Dashboard", "📈 IA Crecimiento +📸", "🥚 Producción", "🌟 Primera Puesta",
    "💰 Ventas/Consumo", "🎄 IA Navidad", "🐣 Alta Lotes", "💸 Gastos", "📜 Histórico Total", "💾 COPIAS"
])

lotes = cargar("lotes"); ventas = cargar("ventas"); prod = cargar("produccion")
gastos = cargar("gastos"); hitos = cargar("hitos")

if menu == "🏠 Dashboard":
    st.title("🏠 Control Maestro")
    # Cálculos rápidos
    v_ext = ventas[ventas['tipo_venta'] == 'Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    v_int = ventas[ventas['tipo_venta'] == 'Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos (Caja)", f"{v_ext:.2f} €")
    c2.metric("Ahorro (Casa)", f"{v_int:.2f} €")
    
    if not prod.empty:
        st.subheader("📊 Producción Reciente")
        st.line_chart(prod.tail(15).set_index('fecha')['huevos'])

# ====================== 📈 IA CRECIMIENTO +📸 (LA MEJORA) ======================
elif menu == "📈 IA Crecimiento +📸":
    st.title("📈 Seguimiento Inteligente y Fenotipado Visual")
    
    if lotes.empty: st.info("No hay lotes activos.")
    
    for _, r in lotes.iterrows():
        expander = st.expander(f"**Lote {r['id']} - {r['raza']}** ({r['especie']})", expanded=True)
        with expander:
            # 1. IA Biológa (Anterior)
            info = CONFIG_IA.get(r['raza'], {"puesta": 150, "madurez": 60})
            meta = info.get("puesta") if "puesta" in info else info.get("madurez")
            edad = (datetime.now() - datetime.strptime(r["fecha"], "%d/%m/%Y")).days + r["edad_inicial"]
            prog = min(100, int((edad/meta)*100))
            
            c_ia, c_poner = st.columns([4, 1])
            ya_pone = "🥚" if not hitos[hitos['lote_id']==r['id']].empty else ""
            c_ia.write(f"Edad: {edad} días {ya_pone}")
            c_ia.progress(prog/100)
            
            # 2. IA Visual (NUEVO)
            st.divider()
            c_foto, c_galeria = st.columns([1, 3])
            
            with c_foto:
                st.write("📷 **Subir Foto Actual**")
                # Captura de imagen desde cámara o archivo
                img_file = st.camera_input(f"Foto Lote {r['id']}", key=f"cam_{r['id']}")
                if not img_file: img_file = st.file_uploader(f"Subir", type=['png','jpg'], key=f"file_{r['id']}")
                
                nota = st.text_input("Nota (ej: cresta roja, pluma fea)", key=f"nota_{r['id']}")
                
                if img_file and st.button("Guardar Foto", key=f"btn_{r['id']}"):
                    # Convertir imagen a BLOB para guardarla en la DB
                    img_bytes = img_file.read()
                    get_conn().execute("INSERT INTO fotos (lote_id, fecha, imagen, nota) VALUES (?,?,?,?)",
                                       (int(r['id']), datetime.now().strftime("%d/%m/%Y"), img_bytes, nota)).connection.commit()
                    st.success("Foto guardada en la base de datos visual."); st.rerun()
            
            with c_galeria:
                st.write("🖼️ **Evolución Visual (Galería)**")
                df_fotos = cargar("fotos", r['id'])
                if not df_fotos.empty:
                    # Mostrar las últimas 4 fotos en columnas
                    cols_g = st.columns(min(len(df_fotos), 4))
                    for i, (_, f) in enumerate(df_fotos.tail(4).iterrows()):
                        with cols_g[i]:
                            try:
                                # Convertir BLOB de vuelta a imagen
                                img_view = Image.open(io.BytesIO(f['imagen']))
                                st.image(img_view, caption=f"{f['fecha']}\n{f['nota']}", use_container_width=True)
                            except: st.error("Error cargando foto.")
                else: st.caption("No hay fotos de este lote todavía.")

# ====================== RESTO DE MENÚS (FORTALECIDOS) ======================
elif menu == "🥚 Producción":
    st.title("🥚 Registro de Producción")
    with st.form("p_form"):
        f = st.date_input("Fecha"); l_id = st.selectbox("Lote", lotes['id'].tolist() if not lotes.empty else [])
        cant = st.number_input("Nº Huevos", 1)
        if st.form_submit_button("Guardar"):
            get_conn().execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(cant))).connection.commit(); st.rerun()

elif menu == "🌟 Primera Puesta":
    st.title("🌟 Hito: Primera Puesta")
    with st.form("h_form"):
        l_id = st.selectbox("Lote Gallinas", lotes[lotes['especie']=='Gallinas']['id'].tolist() if not lotes.empty else [])
        f_h = st.date_input("Fecha primer huevo")
        if st.form_submit_button("Registrar Puesta"):
            get_conn().execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?, 'Primera Puesta', ?)", (int(l_id), f_h.strftime("%d/%m/%Y"))).connection.commit(); st.rerun()

elif menu == "💰 Ventas/Consumo":
    st.title("💰 Salidas (Venta y Casa)")
    with st.form("v_form"):
        tipo = st.radio("Destino", ["Venta Cliente", "Consumo Propio"])
        l_id = st.selectbox("Lote Origen", lotes['id'].tolist() if not lotes.empty else [])
        c1, c2, c3 = st.columns(3)
        u = c1.number_input("Unidades/Huevos", 1); k = c2.number_input("Kilos (si aplica)", 0.0); p = c3.number_input("Valor €", 0.0)
        cli = st.text_input("Cliente / Familia")
        if st.form_submit_button("Registrar"):
            get_conn().execute("INSERT INTO ventas (fecha, cliente, tipo_venta, cantidad, lote_id, kilos_finales, unidades) VALUES (?,?,?,?,?,?,?)",
                               (datetime.now().strftime("%d/%m/%Y"), cli, tipo, p, int(l_id), k, u)).connection.commit(); st.rerun()

elif menu == "🐣 Alta Lotes":
    st.title("🐣 Alta Inteligente")
    with st.form("a_form"):
        esp = st.selectbox("Especie", ["Gallinas", "Pollos"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()))
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad", 1); ed = c2.number_input("Edad inicial", 0); pr = c3.number_input("Precio Ud", 0.0)
        f = st.date_input("Fecha")
        if st.form_submit_button("Dar de Alta"):
            get_conn().execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr)).connection.commit(); st.rerun()

elif menu == "💸 Gastos":
    st.title("💸 Gastos")
    with st.form("g_form"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Otros"])
        con = st.text_input("Concepto"); imp = st.number_input("Importe €", 0.0); kg = st.number_input("Kilos", 0.0)
        if st.form_submit_button("Guardar Gasto"):
            get_conn().execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg)).connection.commit(); st.rerun()

elif menu == "💾 COPIAS":
    st.title("💾 Copias de Seguridad Total")
    st.info("⚠️ Al descargar la base de datos .db, ahora incluirás también todas las FOTOS subidas.")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 Descargar Base de Datos Completa (.db)", f, "bunker_visual.db")

elif menu == "📜 Histórico Total":
    st.title("📜 Todas las tablas")
    for t in ["lotes", "gastos", "produccion", "ventas", "hitos", "fotos"]:
        st.subheader(f"Tabla: {t.upper()}")
        st.dataframe(cargar(t), use_container_width=True)
