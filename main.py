import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN Y REPARACIÓN DE BASE DE DATOS ---
st.set_page_config(page_title="CORRAL PRO - REPARADO", layout="wide")
conn = sqlite3.connect('corral_v38_final.db', check_same_thread=False)
c = conn.cursor()

def reparar_y_actualizar_db():
    # Estructura base
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL)''')
    
    # REPARACIÓN: Añadir columnas faltantes si no existen
    columnas_nuevas = [
        ('gastos', 'raza', 'TEXT'),
        ('ventas', 'raza', 'TEXT'),
        ('produccion', 'raza', 'TEXT'),
        ('lotes', 'inicio_puesta_real', 'TEXT')
    ]
    
    for tabla, columna, tipo in columnas_nuevas:
        try:
            c.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        except sqlite3.OperationalError:
            pass # La columna ya existe, no hacemos nada
    conn.commit()

reparar_y_actualizar_db()

# --- 2. LÓGICA DE PRECIO SUGERIDO (CON FILTRO DE SEGURIDAD) ---
def calcular_precios_sugeridos():
    try:
        df_g = pd.read_sql("SELECT raza, importe FROM gastos", conn)
        df_l = pd.read_sql("SELECT raza, cantidad FROM lotes WHERE estado='Activo'", conn)
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return pd.DataFrame()
    
    sugerencias = []
    if not df_l.empty:
        # Limpiamos valores Nulos para evitar errores de cálculo
        df_g['raza'] = df_g['raza'].fillna('General')
        
        for raza in df_l['raza'].unique():
            total_gastado = df_g[df_g['raza'] == raza]['importe'].sum()
            total_aves = df_l[df_l['raza'] == raza]['cantidad'].sum()
            
            if total_aves > 0:
                coste_por_ave = total_gastado / total_aves
                # Margen del 30%
                precio_minimo = coste_por_ave * 1.30
                sugerencias.append({
                    "Raza": raza,
                    "Inversión Total (€)": round(total_gastado, 2),
                    "Coste Real/Ave (€)": round(coste_por_ave, 2),
                    "Precio Sugerido (€)": round(precio_minimo, 2)
                })
    return pd.DataFrame(sugerencias)

# --- 3. MENÚ PRINCIPAL ---
menu = st.sidebar.radio("CENTRO DE CONTROL", 
    ["💰 UMBRAL DE PRECIOS", "📊 RENTABILIDAD", "🛒 PLAN DE COMPRAS", "🐣 NUEVO LOTE", "💸 GASTOS", "💰 VENTAS", "🛠️ DATOS"])

if menu == "💰 UMBRAL DE PRECIOS":
    st.title("💰 Análisis de Costes y Precios")
    df_precios = calcular_precios_sugeridos()
    
    if not df_precios.empty:
        st.table(df_precios)
        fig = px.bar(df_precios, x="Raza", y="Coste Real/Ave (€)", color="Raza", title="Inversión por cada ave viva")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Registra primero un lote y sus gastos (pienso/compra) para ver el umbral.")

elif menu == "🐣 NUEVO LOTE":
    st.title("🐣 Entrada de Aves")
    with st.form("lote_n"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Pollos", "Gallinas"])
        raza = st.text_input("Raza (Blanca, Roja, Campero, Chocolate...)")
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio de compra por ave (€)")
        if st.form_submit_button("REGISTRAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?)",
                      (f_s, esp, raza, can, pre, 'Activo'))
            # Gasto inicial automático
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                      (f_s, f"Compra Lote {raza}", can*pre, "Animales", raza))
            conn.commit(); st.success("Registrado y columna de raza actualizada."); st.rerun()

elif menu == "🛠️ DATOS":
    st.title("🛠️ Administración de Tablas")
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t}", conn)
    st.dataframe(df)
    if st.button("Borrar Último Registro"):
        c.execute(f"DELETE FROM {t} WHERE id = (SELECT MAX(id) FROM {t})")
        conn.commit(); st.rerun()

# (Las demás pestañas siguen la lógica de la v38)
