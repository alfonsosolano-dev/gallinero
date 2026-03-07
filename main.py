import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.3 - FIX DUPLICADOS", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db_limpia():
    # Estructura base
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL, destino TEXT)')
    
    # Añadir columnas si faltan
    for tabla, col, tipo in [('lotes','fecha','TEXT'), ('lotes','precio_ud','REAL'), ('gastos','kilos','REAL'), ('produccion', 'destino', 'TEXT')]:
        try: c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
        except: pass
    conn.commit()

inicializar_db_limpia()

# --- FUNCIÓN DE LIMPIEZA CRÍTICA ---
def limpiar_columnas_duplicadas(df):
    """Elimina columnas duplicadas y renombra las antiguas sin chocar"""
    if df.empty: return df
    
    # Si existen ambas, priorizamos los datos de 'fecha_entrada' hacia 'fecha' si 'fecha' está vacío
    if 'fecha_entrada' in df.columns and 'fecha' in df.columns:
        df['fecha'] = df['fecha'].fillna(df['fecha_entrada'])
        df = df.drop(columns=['fecha_entrada'])
    elif 'fecha_entrada' in df.columns:
        df = df.rename(columns={'fecha_entrada': 'fecha'})
        
    # Otros posibles duplicados
    mapeo_extra = {'cantidad_inicial': 'cantidad', 'precio_compra_ud': 'precio_ud'}
    for viejo, nuevo in mapeo_extra.items():
        if viejo in df.columns:
            if nuevo in df.columns:
                df[nuevo] = df[nuevo].fillna(df[viejo])
                df = df.drop(columns=[viejo])
            else:
                df = df.rename(columns={viejo: nuevo})
                
    # Eliminar cualquier columna repetida que haya quedado por error
    df = df.loc[:, ~df.columns.duplicated()]
    return df

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
    
    # Métricas
    ing_t = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas_t = pd.read_sql("SELECT SUM(importe) as i FROM gastos", conn)['i'].iloc[0] or 0.0
    st.metric("BENEFICIO NETO TOTAL", f"{round(ing_t - gas_t, 2)} €")

    st.divider()

    # Tabla Rentabilidad
    st.subheader("🎯 Rendimiento por Especie")
    resumen = []
    for e in ["Gallinas", "Pollos", "Codornices"]:
        v = pd.read_sql(f"SELECT SUM(total) as t FROM ventas WHERE especie='{e}'", conn)['t'].iloc[0] or 0.0
        g = pd.read_sql(f"SELECT SUM(importe) as i FROM gastos WHERE especie='{e}'", conn)['i'].iloc[0] or 0.0
        c_casa = pd.read_sql(f"SELECT SUM(cantidad) as c FROM produccion WHERE especie='{e}' AND destino='Casa'", conn)['c'].iloc[0] or 0.0
        resumen.append({"Especie": e, "Ingresos": v, "Gastos": g, "Balance": round(v-g,2), "Casa": int(c_casa)})
    st.table(pd.DataFrame(resumen))

    # Alertas
    st.subheader("🐥 Lotes Activos")
    df_l = limpiar_columnas_duplicadas(pd.read_sql("SELECT * FROM lotes WHERE estado='Activo'", conn))
    if not df_l.empty:
        for i, row in df_l.iterrows():
            d = calcular_dias(row['fecha'])
            with st.expander(f"Lote {row['id']} - {row['especie']} ({d} días)"):
                if row['especie'] == "Pollos" and d >= 90: st.warning("⚠️ ¡Listo para venta!")
                st.write(f"Cantidad: {row.get('cantidad', 'N/A')} aves")

# --- 2. LOTES ---
elif menu == "🐣 LOTES":
    st.title("🐣 Registrar Lote")
    with st.form("l", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1); pre = st.number_input("Precio/ud", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f_s, f"Compra {esp}", can*pre, "Animales", esp))
            conn.commit(); st.success("Guardado correctamente")

# --- 6. DATOS (Aquí fallaba antes) ---
elif menu == "🛠️ DATOS":
    st.title("🛠️ Gestión de Registros")
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df_raw = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    df_clean = limpiar_columnas_duplicadas(df_raw) # Limpiamos antes de mostrar
    st.dataframe(df_clean, use_container_width=True)
    
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}")
        conn.commit(); st.rerun()

# --- OTROS (VENTAS, PROD, GASTOS) ---
elif menu == "💰 VENTAS":
    with st.form("v"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro = st.text_input("Producto"); tot = st.number_input("Total €")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO ventas (fecha, producto, total, especie) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, tot, esp))
            conn.commit(); st.success("Venta OK")

elif menu == "🥚 PRODUCCIÓN":
    with st.form("p"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        can = st.number_input("Cantidad"); dest = st.radio("Destino", ["Venta", "Casa"], horizontal=True)
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad, destino) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, can, dest))
            conn.commit(); st.success("OK")

elif menu == "💸 GASTOS":
    with st.form("g"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices", "General"])
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipos"]); imp = st.number_input("Importe €")
        if st.form_submit_button("✅"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), "Gasto", imp, cat, esp))
            conn.commit(); st.success("OK")
