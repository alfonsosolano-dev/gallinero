import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.0 - ESTABLE", layout="wide")
conn = sqlite3.connect('corral_v25_estable.db', check_same_thread=False)
c = conn.cursor()

# --- REPARACIÓN DE BASE DE DATOS (Nombres de Columnas) ---
def inicializar_db():
    # Creamos las tablas con los nombres definitivos
    c.execute('''CREATE TABLE IF NOT EXISTS lotes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL, destino TEXT)''')
    
    # PARCHE PARA EL ERROR 'fecha_entrada' vs 'fecha'
    try:
        c.execute("ALTER TABLE lotes ADD COLUMN fecha TEXT")
    except: pass
    
    # Si existe 'fecha_entrada', pasamos los datos a 'fecha'
    try:
        c.execute("UPDATE lotes SET fecha = fecha_entrada WHERE fecha IS NULL")
    except: pass
    
    conn.commit()

inicializar_db()

# --- FUNCIONES ---
def calcular_edad(fecha_str):
    if not fecha_str: return 0
    try:
        f = datetime.strptime(fecha_str, '%d/%m/%Y').date()
        return (datetime.now().date() - f).days
    except: return 0

# --- MENÚ ---
st.sidebar.title("🚜 Gestión Corral V.25")
menu = st.sidebar.radio("Ir a:", ["📊 DASHBOARD", "🐣 NUEVO LOTE", "💰 VENTAS", "🥚 PRODUCCIÓN/CASA", "💸 GASTOS", "🛠️ DATOS"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Resumen y Alertas")
    
    # Cálculos Generales
    ing = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas = pd.read_sql("SELECT SUM(importe) as i FROM gastos", conn)['i'].iloc[0] or 0.0
    st.metric("BENEFICIO NETO TOTAL", f"{round(ing - gas, 2)} €")

    st.divider()
    
    # Alertas de Lotes (Aquí estaba el error)
    st.subheader("🐥 Control de Lotes Activos")
    df_lotes = pd.read_sql("SELECT * FROM lotes WHERE estado='Activo'", conn)
    
    if not df_lotes.empty:
        # Aseguramos que el nombre de la columna sea 'fecha'
        if 'fecha' not in df_lotes.columns and 'fecha_entrada' in df_lotes.columns:
            df_lotes.rename(columns={'fecha_entrada': 'fecha'}, inplace=True)
            
        for _, row in df_lotes.iterrows():
            dias = calcular_edad(row['fecha'])
            with st.expander(f"Lote {row['id']} - {row['especie']} ({dias} días)"):
                col1, col2 = st.columns(2)
                col1.write(f"**Cantidad:** {row['cantidad']} aves")
                if row['especie'] == "Pollos" and dias >= 90:
                    st.warning(f"⚠️ ¡Atención! Este lote de pollos tiene {dias} días. Recomendado vender/sacrificar.")
    else:
        st.info("No hay lotes registrados.")

# --- 2. NUEVO LOTE ---
elif menu == "🐣 NUEVO LOTE":
    st.title("🐣 Registrar Entrada de Animales")
    with st.form("f_lote", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR LOTE"):
            f_s = f.strftime('%d/%m/%Y')
            total = can * pre
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)", (f_s, f"Compra {can} {esp}", total, "Animales", esp, 0.0))
            conn.commit()
            st.success(f"✅ ¡Guardado! Se ha generado un gasto de {total}€.")

# --- 4. PRODUCCIÓN / CASA ---
elif menu == "🥚 PRODUCCIÓN/CASA":
    st.title("🥚 Producción y Autoconsumo")
    with st.form("f_p", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        can = st.number_input("Cantidad", min_value=0.0)
        dest = st.radio("Destino", ["Venta", "Casa"], horizontal=True)
        if st.form_submit_button("✅ REGISTRAR"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad, destino) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, can, dest))
            conn.commit()
            st.success(f"✅ Registrado {can} para {dest}")

# --- Pestañas de Soporte ---
elif menu == "💰 VENTAS":
    with st.form("v"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro = st.text_input("Producto"); tot = st.number_input("Total €")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO ventas (fecha, producto, total, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, tot, esp))
            conn.commit(); st.success("Venta OK")

elif menu == "💸 GASTOS":
    with st.form("g"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices", "General"])
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipos"]); imp = st.number_input("Importe €")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), "Gasto manual", imp, cat, esp, 0.0))
            conn.commit(); st.success("Gasto OK")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
