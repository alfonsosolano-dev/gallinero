import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.2 - MODO SEGURO", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db_blindada():
    # Creamos tablas base con nombres definitivos
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL, destino TEXT)')
    
    # Parches de columnas por si vienes de versiones muy viejas
    for tabla, col, tipo in [('lotes','fecha','TEXT'), ('lotes','precio_ud','REAL'), ('gastos','kilos','REAL'), ('produccion','destino','TEXT')]:
        try: c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
        except: pass
    conn.commit()

inicializar_db_blindada()

# --- UTILIDADES ---
def normalizar_df(df):
    """Fuerza a que el DataFrame tenga los nombres que el código espera"""
    mapeo = {'fecha_entrada': 'fecha', 'cantidad_inicial': 'cantidad', 'precio_compra_ud': 'precio_ud'}
    return df.rename(columns=mapeo)

def calcular_dias(f_str):
    try:
        f = datetime.strptime(f_str, '%d/%m/%Y').date()
        return (datetime.now().date() - f).days
    except: return 0

# --- MENÚ ---
menu = st.sidebar.radio("Navegación:", ["📊 DASHBOARD", "🐣 LOTES", "💰 VENTAS", "🥚 PRODUCCIÓN", "💸 GASTOS", "🛠️ DATOS"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Control de Rentabilidad")
    
    # 1. METRICAS GENERALES
    ing_t = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas_t = pd.read_sql("SELECT SUM(importe) as i FROM gastos", conn)['i'].iloc[0] or 0.0
    st.metric("BENEFICIO NETO TOTAL", f"{round(ing_t - gas_t, 2)} €", delta=f"{round(ing_t, 2)}€ Ingresos")
    st.divider()

    # 2. TABLA POR ESPECIE (Lo que necesitabas)
    st.subheader("🎯 Rendimiento por Especie")
    especies = ["Gallinas", "Pollos", "Codornices"]
    resumen_data = []
    
    for e in especies:
        v_e = pd.read_sql(f"SELECT SUM(total) as t FROM ventas WHERE especie='{e}'", conn)['t'].iloc[0] or 0.0
        g_e = pd.read_sql(f"SELECT SUM(importe) as i FROM gastos WHERE especie='{e}'", conn)['i'].iloc[0] or 0.0
        c_e = pd.read_sql(f"SELECT SUM(cantidad) as c FROM produccion WHERE especie='{e}' AND destino='Casa'", conn)['c'].iloc[0] or 0.0
        resumen_data.append({
            "Especie": e, 
            "Ingresos (€)": round(v_e, 2), 
            "Gastos (€)": round(g_e, 2), 
            "Balance (€)": round(v_e - g_e, 2),
            "Consumo Casa": f"{int(c_e)} uds"
        })
    st.table(pd.DataFrame(resumen_data))

    # 3. ALERTAS DE LOTES
    st.subheader("🐥 Lotes Activos y Alertas")
    df_l = normalizar_df(pd.read_sql("SELECT * FROM lotes WHERE estado='Activo'", conn))
    if not df_l.empty:
        for i, row in df_l.iterrows():
            d = calcular_dias(row['fecha'])
            with st.expander(f"Lote {row['id']} - {row['especie']} ({d} días)"):
                st.write(f"Inversión inicial: {row['cantidad']} aves a {row['precio_ud']}€/ud")
                if row['especie'] == "Pollos" and d >= 90:
                    st.warning("⚠️ ¡Lote listo para venta/sacrificio!")

# --- 2. LOTES ---
elif menu == "🐣 LOTES":
    st.title("🐣 Entrada de Animales")
    with st.form("l", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1); pre = st.number_input("Precio/ud", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f_s, f"Lote {esp}", can*pre, "Animales", esp))
            conn.commit(); st.success("Guardado en Lotes y Gastos")

# --- 4. PRODUCCIÓN ---
elif menu == "🥚 PRODUCCIÓN":
    st.title("🥚 Producción y Casa")
    with st.form("p", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        can = st.number_input("Cantidad", min_value=0.0); dest = st.radio("Destino", ["Venta", "Casa"], horizontal=True)
        if st.form_submit_button("✅ REGISTRAR"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad, destino) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, can, dest))
            conn.commit(); st.success(f"Registrado para {dest}")

# --- RESTO DE PESTAÑAS ---
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
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), "Gasto", imp, cat, esp))
            conn.commit(); st.success("Gasto OK")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = normalizar_df(pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn))
    st.dataframe(df)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
