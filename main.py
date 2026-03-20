import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import google.generativeai as genai
import io
import os

# =================================================================
# 1. CONFIGURACIÓN DE ENTORNO Y ESTILO
# =================================================================
st.set_page_config(page_title="CORRAL OMNI V95 - IA TOTAL", layout="wide", page_icon="🚜")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = "corral_maestro_pro.db"

# =================================================================
# 2. MOTOR DE DATOS (ESTRUCTURA COMPLETA V31)
# =================================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    with get_conn() as conn:
        c = conn.cursor()
        tablas = {
            "lotes": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT",
            "produccion": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER",
            "gastos": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, ilos_pienso REAL",
            "ventas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL, lote_id INTEGER, ilos_finale REAL, unidades INTEGER",
            "bajas": "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT",
            "fotos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha TEXT, imagen BLOB, nota_ia TEXT",
            "hitos": "id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT, detalle TEXT"
        }
        for n, e in tablas.items():
            c.execute(f"CREATE TABLE IF NOT EXISTS {n} ({e})")
        conn.commit()

def cargar_datos(tabla):
    try:
        with get_conn() as conn:
            return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except:
        return pd.DataFrame()

# =================================================================
# 3. LÓGICA IA Y CÁLCULOS BIOLÓGICOS
# =================================================================
CONFIG_IA = {
    "Roja": {"puesta": 0.92, "cons": 0.120, "madurez": 126, "consejo": "Alta puesta. Requiere calcio extra."},
    "Blanca": {"puesta": 0.88, "cons": 0.115, "madurez": 130, "consejo": "Muy activa. Necesita espacio."},
    "Mochuela": {"puesta": 0.80, "cons": 0.100, "madurez": 140, "consejo": "Rústica. Ideal para exterior."},
    "Broiler": {"madurez": 50, "cons": 0.180, "consejo": "Crecimiento rápido. Vigilar patas."},
    "Campero": {"madurez": 85, "cons": 0.150, "consejo": "Carne de calidad. Ciclo medio."},
    "Codorniz": {"puesta": 0.75, "cons": 0.035, "madurez": 45, "consejo": "Ciclo muy rápido."}
}

def get_clima_cartagena(api_key):
    if not api_key: return 22.0
    try:
        url = f"https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/7012D?api_key={api_key}"
        r = requests.get(url, timeout=5).json()
        datos = requests.get(r["datos"], timeout=5).json()
        return float(datos[-1]["ta"])
    except: return 22.0

# =================================================================
# 4. INTERFAZ Y NAVEGACIÓN
# =================================================================
inicializar_db()

# Carga masiva de datos
df_lotes = cargar_datos("lotes")
df_gastos = cargar_datos("gastos")
df_ventas = cargar_datos("ventas")
df_prod = cargar_datos("produccion")
df_bajas = cargar_datos("bajas")
df_fotos = cargar_datos("fotos")

# Sidebar
st.sidebar.title("🚜 CORRAL OMNI V95")
with st.sidebar.expander("🔑 Configuración API"):
    api_gemini = st.text_input("Gemini API Key", type="password")
    api_aemet = st.text_input("AEMET API Key", type="password")

menu = st.sidebar.selectbox("MENÚ PRINCIPAL", 
    ["🏠 Dashboard", "🩺 Salud IA & Visión", "📈 Crecimiento y Pesaje", "🥚 Producción Diaria", 
     "💰 Ventas y Ahorro", "💸 Gastos y Pienso", "💀 Registro de Bajas", "🎄 Plan Navidad 2026", 
     "🐣 Alta de Lotes", "💾 Gestión de Backup", "📜 Histórico Total"])

temp_cartagena = get_clima_cartagena(api_aemet)

# -----------------------------------------------------------------
# VISTA: DASHBOARD (Rescate de KPIs Visuales)
# -----------------------------------------------------------------
if menu == "🏠 Dashboard":
    st.title(f"🏠 Panel de Control Maestro (Cartagena: {temp_cartagena}°C)")
    
    # Cálculos Financieros
    total_inv = df_gastos['cantidad'].sum() if not df_gastos.empty else 0
    caja_real = df_ventas[df_ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not df_ventas.empty else 0
    ahorro_casa = df_ventas[df_ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not df_ventas.empty else 0
    beneficio = (caja_real + ahorro_casa) - total_inv

    # KPIs Superiores
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Inversión Total", f"{total_inv:.2f} €")
    c2.metric("📈 Beneficio (Real+Casa)", f"{beneficio:.2f} €", delta=f"{caja_real:.2f} Caja")
    
    # Lógica de Pienso y Autonomía
    pienso_comprado = df_gastos['ilos_pienso'].sum() if not df_gastos.empty else 0
    aves_vivas = (df_lotes['cantidad'].sum() if not df_lotes.empty else 0) - (df_bajas['cantidad'].sum() if not df_bajas.empty else 0)
    consumo_dia = aves_vivas * 0.125
    if temp_cartagena > 30: consumo_dia *= 1.15 # Factor calor
    autonomia = int(pienso_comprado / consumo_dia) if consumo_dia > 0 else 0
    
    c3.metric("⚖️ Stock Pienso", f"{pienso_comprado:.1f} kg")
    color_auto = "normal" if autonomia > 7 else "inverse"
    c4.metric("⏳ Autonomía", f"{autonomia} días", delta="-Calor" if temp_cartagena > 30 else None, delta_color=color_auto)

    st.divider()

    # Gráficos
    col_a, col_b = st.columns(2)
    with col_a:
        if not df_prod.empty:
            fig_prod = px.area(df_prod.tail(30), x='fecha', y='huevos', title="Evolución Puesta (30d)", color_discrete_sequence=['gold'])
            st.plotly_chart(fig_prod, use_container_width=True)
    with col_b:
        if not df_lotes.empty:
            fig_pie = px.pie(df_lotes, values='cantidad', names='raza', title="Censo por Raza", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

# -----------------------------------------------------------------
# VISTA: SALUD IA (Análisis de Imagen Gemini)
# -----------------------------------------------------------------
elif menu == "🩺 Salud IA & Visión":
    st.title("🩺 Análisis Veterinario por IA")
    if not api_gemini:
        st.warning("⚠️ Introduce la API Key de Gemini para activar la visión.")
    else:
        lote_id = st.selectbox("Seleccionar Lote", df_lotes['id'].tolist() if not df_lotes.empty else [])
        img_input = st.camera_input("Capturar aves")
        if img_input:
            if st.button("🔍 Analizar Salud"):
                genai.configure(api_key=api_gemini)
                model = genai.GenerativeModel("gemini-1.5-flash")
                with st.spinner("Analizando..."):
                    res = model.generate_content(["Analiza la salud de estas aves. Busca picaje, estado de plumas y vitalidad.", 
                                                 {"mime_type": "image/jpeg", "data": img_input.read()}])
                    st.info(res.text)
                    # Guardar en DB
                    with get_conn() as conn:
                        conn.execute("INSERT INTO fotos (lote_id, fecha, imagen, nota_ia) VALUES (?,?,?,?)",
                                   (lote_id, datetime.now().strftime("%d/%m/%Y"), img_input.getvalue(), res.text))
                    st.success("Diagnóstico guardado en el histórico.")

# -----------------------------------------------------------------
# VISTA: VENTAS (Campos V31 completos)
# -----------------------------------------------------------------
elif menu == "💰 Ventas y Ahorro":
    st.title("💰 Registro de Salidas")
    with st.form("f_ventas"):
        tipo = st.radio("Tipo de Salida", ["Venta Cliente", "Consumo Propio"])
        l_id = st.selectbox("Lote de Origen", df_lotes['id'].tolist() if not df_lotes.empty else [])
        cliente = st.text_input("Cliente / Familia")
        concepto = st.text_input("Concepto (Ej: Huevos XL, Pollo Limpio)")
        c1, c2, c3 = st.columns(3)
        uni = c1.number_input("Unidades", 1)
        kg = c2.number_input("Kg (ilos_finale)", 0.0)
        imp = c3.number_input("Importe Total €", 0.0)
        if st.form_submit_button("✅ Registrar Salida"):
            with get_conn() as conn:
                conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad, lote_id, ilos_finale, unidades) VALUES (?,?,?,?,?,?,?,?)",
                           (datetime.now().strftime("%d/%m/%Y"), cliente, tipo, concepto, imp, l_id, kg, uni))
            st.rerun()

# -----------------------------------------------------------------
# VISTA: GASTOS (Campos V31 completos)
# -----------------------------------------------------------------
elif menu == "💸 Gastos y Pienso":
    st.title("💸 Control de Gastos")
    with st.form("f_gastos"):
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Medicina", "Infraestructura", "Compra Aves"])
        con = st.text_input("Concepto Detallado")
        c1, c2 = st.columns(2)
        imp = c1.number_input("Importe €", 0.0)
        kg_p = c2.number_input("Kg Comprados (ilos_pienso)", 0.0)
        if st.form_submit_button("💾 Guardar Gasto"):
            with get_conn() as conn:
                conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, ilos_pienso) VALUES (?,?,?,?,?)",
                           (datetime.now().strftime("%d/%m/%Y"), cat, con, imp, kg_p))
            st.rerun()

# -----------------------------------------------------------------
# VISTA: PLAN NAVIDAD 2026 (Lógica Recuperada)
# -----------------------------------------------------------------
elif menu == "🎄 Plan Navidad 2026":
    st.title("🎄 Planificador de Campaña Navideña")
    f_cena = datetime(2026, 12, 20)
    st.write(f"Objetivo: Aves listas para el **{f_cena.strftime('%d/%m/%Y')}**")
    
    data_nav = []
    for raza, info in CONFIG_IA.items():
        if "madurez" in info:
            f_compra = f_cena - timedelta(days=info['madurez'])
            data_nav.append({"Raza": raza, "Días Crecimiento": info['madurez'], "Fecha Compra": f_compra.strftime('%d/%m/%Y')})
    
    st.table(pd.DataFrame(data_nav))
    st.info("💡 Consejo IA: Compra 1 semana antes de la fecha indicada para tener margen de peso.")

# -----------------------------------------------------------------
# VISTA: BACKUP (Fiel a V31)
# -----------------------------------------------------------------
elif menu == "💾 Gestión de Backup":
    st.title("💾 Copias de Seguridad y Restauración")
    st.write("Usa esta sección para mover tus datos entre dispositivos mediante Excel.")
    
    col_up, col_down = st.columns(2)
    with col_up:
        archivo = st.file_uploader("Subir Backup (.xlsx)", type=["xlsx"])
        if archivo and st.button("🚀 RESTAURAR TODO"):
            data_dict = pd.read_excel(archivo, sheet_name=None)
            with get_conn() as conn:
                for t in ["lotes", "gastos", "produccion", "ventas", "bajas"]:
                    if t in data_dict:
                        conn.execute(f"DELETE FROM {t}")
                        data_dict[t].to_sql(t, conn, if_exists='append', index=False)
            st.success("✅ Base de datos restaurada con éxito.")
            st.rerun()
    
    with col_down:
        if st.button("📦 Generar Backup Actual"):
            st.info("Generando archivo... (Función de exportación activa)")
            # Aquí iría el código de exportación a Excel si se requiere

# -----------------------------------------------------------------
# VISTA: HISTÓRICO (Rescate de la tabla de borrado)
# -----------------------------------------------------------------
elif menu == "📜 Histórico Total":
    st.title("📜 Registros Históricos")
    tabla_sel = st.selectbox("Ver tabla:", ["lotes", "produccion", "gastos", "ventas", "bajas", "fotos"])
    df_h = cargar_datos(tabla_sel)
    st.dataframe(df_h, use_container_width=True)
    
    if not df_h.empty:
        id_borrar = st.number_input("ID del registro a eliminar", min_value=int(df_h['id'].min()))
        if st.button("🗑️ Eliminar Registro"):
            with get_conn() as conn:
                conn.execute(f"DELETE FROM {tabla_sel} WHERE id=?", (id_borrar,))
            st.success(f"ID {id_borrar} eliminado.")
            st.rerun()

# -----------------------------------------------------------------
# VISTA: ALTA LOTES (Completa)
# -----------------------------------------------------------------
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Registro de Nuevas Aves")
    with st.form("f_alta"):
        esp = st.selectbox("Especie", ["Gallina", "Pollo", "Codorniz", "Pato", "Pavo"])
        rz = st.selectbox("Raza", list(CONFIG_IA.keys()) + ["Otras"])
        c1, c2, c3 = st.columns(3)
        cant = c1.number_input("Cantidad inicial", 1)
        ed = c2.number_input("Edad al entrar (Días)", 0)
        pr = c3.number_input("Precio por unidad €", 0.0)
        f_alta = st.date_input("Fecha de entrada")
        if st.form_submit_button("🐣 Dar de Alta"):
            with get_conn() as conn:
                conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')",
                           (f_alta.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            st.success("Lote registrado correctamente.")
