import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Tablas
    c.execute("CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS primera_puesta(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER UNIQUE, fecha_puesta TEXT)")
    
    # Parche por si la tabla gastos es vieja
    try: c.execute("ALTER TABLE gastos ADD COLUMN kilos_pienso REAL DEFAULT 0")
    except: pass
    
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

def eliminar_registro(tabla, id_reg):
    conn = get_conn()
    conn.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_reg,))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 2. MENÚ LATERAL ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard", "🐣 Alta de Lotes", "🥚 Producción", 
    "💸 Gastos e Inventario", "💰 Ventas y Clientes", 
    "💉 Salud y Alertas", "📜 HISTÓRICO (Borrar Datos)", "💾 SEGURIDAD"
])

# --- SECCIÓN NUEVA: HISTÓRICO Y BORRADO ---
if menu == "📜 HISTÓRICO (Borrar Datos)":
    st.title("📜 Histórico de Registros")
    st.info("Aquí puedes revisar lo que has anotado y borrar errores.")
    
    tabla_select = st.selectbox("¿Qué historial quieres ver?", 
                                ["produccion", "gastos", "ventas", "salud", "bajas", "lotes"])
    
    df = cargar(tabla_select)
    
    if df.empty:
        st.write("No hay datos en esta sección.")
    else:
        # Mostrar tabla bonita
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        st.subheader("🗑️ Eliminar un registro")
        id_a_borrar = st.number_input("Introduce el ID del registro que quieres borrar:", min_value=1, step=1)
        
        if st.button("❌ ELIMINAR REGISTRO DEFINITIVAMENTE"):
            if id_a_borrar in df['id'].values:
                eliminar_registro(tabla_select, id_a_borrar)
                st.error(f"Registro {id_a_borrar} eliminado de la tabla {tabla_select}.")
                st.rerun()
            else:
                st.warning("Ese ID no existe en la tabla actual.")

# --- DASHBOARD ---
elif menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control")
    lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos"); ventas = cargar("ventas")
    c1, c2, c3 = st.columns(3)
    c1.metric("Huevos Totales", int(prod['huevos'].sum() if not prod.empty else 0))
    c2.metric("Gasto Total", f"{gastos['cantidad'].sum() if not gastos.empty else 0:.2f}€")
    c3.metric("Ventas Totales", f"{ventas['cantidad'].sum() if not ventas.empty else 0:.2f}€")

# --- ALTA DE LOTES ---
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Registro de Lotes")
    with st.form("f_lote"):
        f_l = st.date_input("Fecha llegada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        cant = st.number_input("Cantidad", 1)
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn()
            conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, estado) VALUES (?,?,?,?,'Activo')", (f_l.strftime("%d/%m/%Y"), esp, rz, int(cant)))
            conn.commit(); conn.close(); st.success("CONFIRMADO: Lote guardado."); st.rerun()

# --- GASTOS E INVENTARIO ---
elif menu == "💸 Gastos e Inventario":
    st.title("💸 Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Infraestructura", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe €", 0.0)
        kg = st.number_input("Kilos (si es pienso)", 0.0)
        if st.form_submit_button("💾 GUARDAR GASTO"):
            conn = get_conn()
            conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close(); st.success(f"CONFIRMADO: Gasto de {imp}€ anotado."); st.rerun()

# --- VENTAS ---
elif menu == "💰 Ventas y Clientes":
    st.title("💰 Ventas")
    with st.form("f_v"):
        f = st.date_input("Fecha"); cli = st.text_input("Cliente"); prod_v = st.text_input("Producto"); imp = st.number_input("€", 0.0)
        if st.form_submit_button("🤝 REGISTRAR"):
            conn = get_conn()
            conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,'Venta Cliente',?,?)", (f.strftime("%d/%m/%Y"), cli, prod_v, imp))
            conn.commit(); conn.close(); st.success("CONFIRMADO: Venta registrada."); st.rerun()

# --- PRODUCCION ---
elif menu == "🥚 Producción":
    st.title("🥚 Producción")
    with st.form("f_p"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1); val = st.number_input("Huevos", 1)
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn()
            conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f.strftime("%d/%m/%Y"), int(l_id), int(val)))
            conn.commit(); conn.close(); st.success(f"CONFIRMADO: {val} huevos anotados."); st.rerun()

# --- SALUD ---
elif menu == "💉 Salud y Alertas":
    st.title("💉 Salud")
    with st.form("f_s"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1); desc = st.text_area("Tratamiento"); prox = st.date_input("Próxima")
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn()
            conn.execute("INSERT INTO salud (fecha, lote, descripcion, proxima_fecha, estado) VALUES (?,?,?,?,'Pendiente')", (f.strftime("%d/%m/%Y"), int(l_id), desc, prox.strftime("%d/%m/%Y")))
            conn.commit(); conn.close(); st.success("CONFIRMADO: Salud registrada."); st.rerun()

# --- SEGURIDAD ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Seguridad")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR COPIA", f, "corral.db")
    up = st.file_uploader("📤 RESTAURAR", type="db")
    if up:
        with open(DB_PATH, "wb") as f: f.write(up.getbuffer())
        st.success("Restaurado."); st.rerun()
