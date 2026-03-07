import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.1 - RECUPERACIÓN", layout="wide")

# VOLVEMOS AL ARCHIVO ORIGINAL PARA NO PERDER TUS DATOS
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db_pro():
    # Aseguramos que existan todas las tablas
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL, destino TEXT)')
    
    # PARCHE DE COMPATIBILIDAD: Si tus datos viejos usan 'fecha_entrada', creamos 'fecha'
    try:
        c.execute("ALTER TABLE lotes ADD COLUMN fecha TEXT")
    except: pass
    
    # Copiamos datos de la columna vieja a la nueva si es necesario
    try:
        c.execute("UPDATE lotes SET fecha = fecha_entrada WHERE fecha IS NULL")
    except: pass
    
    # Otros parches de columnas que podrían faltar de versiones previas
    columnas_extra = [
        ('gastos', 'kilos', 'REAL DEFAULT 0.0'),
        ('produccion', 'destino', 'TEXT DEFAULT "Venta"'),
        ('lotes', 'precio_ud', 'REAL DEFAULT 0.0')
    ]
    for tabla, col, tipo in columnas_extra:
        try: c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
        except: pass
        
    conn.commit()

inicializar_db_pro()

# --- LÓGICA DE TIEMPO ---
def calcular_edad(fecha_str):
    if not fecha_str: return 0
    try:
        # Intentamos el formato estándar
        f = datetime.strptime(fecha_str, '%d/%m/%Y').date()
        return (datetime.now().date() - f).days
    except: return 0

# --- MENÚ ---
st.sidebar.title("🚜 Gestión Corral V.25.1")
menu = st.sidebar.radio("Ir a:", ["📊 DASHBOARD", "🐣 LOTES", "💰 VENTAS", "🥚 PRODUCCIÓN/CASA", "💸 GASTOS", "🛠️ DATOS"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Análisis de Rendimiento")
    
    # Cargamos datos para métricas
    df_v = pd.read_sql("SELECT total FROM ventas", conn)
    df_g = pd.read_sql("SELECT importe FROM gastos", conn)
    
    ing = df_v['total'].sum() if not df_v.empty else 0.0
    gas = df_g['importe'].sum() if not df_g.empty else 0.0
    
    st.metric("BENEFICIO NETO", f"{round(ing - gas, 2)} €", delta=f"{round(ing, 2)}€ Ingresos")
    st.divider()

    # CONTROL DE LOTES (Con corrección de nombres de columna en el DataFrame)
    st.subheader("🐥 Estado de los Animales")
    df_lotes = pd.read_sql("SELECT * FROM lotes WHERE estado='Activo'", conn)
    
    if not df_lotes.empty:
        # Si la base de datos devolvió 'fecha_entrada' en lugar de 'fecha', lo arreglamos aquí
        if 'fecha' not in df_lotes.columns and 'fecha_entrada' in df_lotes.columns:
            df_lotes.rename(columns={'fecha_entrada': 'fecha'}, inplace=True)
            
        cols = st.columns(len(df_lotes) if len(df_lotes) < 4 else 3)
        for i, row in df_lotes.iterrows():
            with cols[i % 3]:
                dias = calcular_edad(row['fecha'])
                st.info(f"**Lote {row['id']} - {row['especie']}**")
                st.write(f"📅 Edad: {dias} días")
                if row['especie'] == "Pollos" and dias >= 90:
                    st.warning("⚠️ ¡Punto de venta!")
    else:
        st.write("No hay lotes activos.")

# --- 2. LOTES ---
elif menu == "🐣 LOTES":
    st.title("🐣 Registrar Entrada")
    with st.form("f_lote", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR"):
            f_s = f.strftime('%d/%m/%Y')
            total = can * pre
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)", (f_s, f"Compra {can} {esp}", total, "Animales", esp, 0.0))
            conn.commit()
            st.success("✅ Guardado correctamente")

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
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipos"]); imp = st.number_input("Importe €"); kil = st.number_input("Kilos")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), "Gasto manual", imp, cat, esp, kil))
            conn.commit(); st.success("Gasto OK")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
