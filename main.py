import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.24.9 - ANALÍTICA PRO", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

# --- REPARACIÓN Y ESTRUCTURA DE BASE DE DATOS ---
def asegurar_db():
    # Creación de tablas base
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL, destino TEXT)')
    
    # Parche de seguridad para columnas nuevas
    columnas = {
        'produccion': [('destino', 'TEXT DEFAULT "Venta"'), ('especie', 'TEXT DEFAULT "General"')],
        'gastos': [('kilos', 'REAL DEFAULT 0.0'), ('especie', 'TEXT DEFAULT "General"')],
        'lotes': [('precio_ud', 'REAL DEFAULT 0.0')]
    }
    for tabla, cols in columnas.items():
        for col, tipo in cols:
            try: c.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
            except: pass
    conn.commit()

asegurar_db()

# --- FUNCIONES DE APOYO ---
def dias_lote(fecha_str):
    try:
        f = datetime.strptime(fecha_str, '%d/%m/%Y').date()
        return (datetime.now().date() - f).days
    except: return 0

# --- MENÚ ---
st.sidebar.title("🚜 Gestión Corral V.24.9")
menu = st.sidebar.radio("Ir a:", ["📊 DASHBOARD Y GRÁFICOS", "🐣 GESTIÓN DE LOTES", "💰 VENTAS", "🥚 PRODUCCIÓN Y CASA", "💸 GASTOS", "🛠️ MANTENIMIENTO"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD Y GRÁFICOS":
    st.title("📊 Rendimiento y Analítica")
    
    # Métricas Globales
    ing_t = pd.read_sql("SELECT SUM(total) as t FROM ventas", conn)['t'].iloc[0] or 0.0
    gas_t = pd.read_sql("SELECT SUM(importe) as i FROM gastos", conn)['i'].iloc[0] or 0.0
    st.metric("BENEFICIO NETO TOTAL", f"{round(ing_t - gas_t, 2)} €", delta=f"{round(ing_t, 2)} € Ingresos")
    
    st.divider()
    
    # Rentabilidad por Especie
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("🎯 Comparativa por Especie")
        resumen = []
        for e in ["Gallinas", "Pollos", "Codornices"]:
            i = pd.read_sql(f"SELECT SUM(total) as t FROM ventas WHERE especie='{e}'", conn)['t'].iloc[0] or 0.0
            g = pd.read_sql(f"SELECT SUM(importe) as i FROM gastos WHERE especie='{e}'", conn)['i'].iloc[0] or 0.0
            c_casa = pd.read_sql(f"SELECT SUM(cantidad) as c FROM produccion WHERE especie='{e}' AND destino='Casa'", conn)['c'].iloc[0] or 0.0
            resumen.append({"Especie": e, "Ingresos": f"{i}€", "Gastos": f"{g}€", "Balance": f"{round(i-g,2)}€", "Consumo Casa": f"{int(c_casa)} uds"})
        st.table(pd.DataFrame(resumen))

    with col_b:
        st.subheader("🍕 Gastos por Categoría")
        df_cat = pd.read_sql("SELECT categoria, SUM(importe) as total FROM gastos GROUP BY categoria", conn)
        if not df_cat.empty: st.bar_chart(df_cat.set_index('categoria'))

    st.divider()
    
    # Alertas de Lotes
    st.subheader("🐥 Estado de Lotes y Alertas")
    df_lotes = pd.read_sql("SELECT * FROM lotes WHERE estado='Activo'", conn)
    if not df_lotes.empty:
        for _, row in df_lotes.iterrows():
            dias = dias_lote(row['fecha'])
            color = "normal"
            if row['especie'] == "Pollos" and dias >= 90:
                st.warning(f"⚠️ LOTE #{row['id']} ({row['especie']}): ¡Llegó a los {dias} días! Punto óptimo de venta/sacrificio.")
            
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Lote {row['id']} - {row['especie']}**")
            c2.write(f"Edad: {dias} días")
            k_esp = pd.read_sql(f"SELECT SUM(kilos) as k FROM gastos WHERE especie='{row['especie']}'", conn)['k'].iloc[0] or 0.0
            c3.write(f"Pienso: {round(k_esp, 2)} kg")
    else: st.info("No hay lotes activos actualmente.")

# --- 2. GESTIÓN DE LOTES ---
elif menu == "🐣 GESTIÓN DE LOTES":
    st.title("🐣 Ingreso de Lotes")
    with st.form("l", clear_on_submit=True):
        f = st.date_input("Fecha entrada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad de aves", min_value=1)
        pre = st.number_input("Precio por unidad (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR LOTE Y GASTO"):
            f_s = f.strftime('%d/%m/%Y')
            total_g = can * pre
            c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)", (f_s, f"Compra {can} {esp}", total_g, "Animales", esp, 0.0))
            conn.commit()
            st.success(f"✅ ¡ÉXITO! Lote registrado y {total_g}€ cargados a gastos.")

# --- 3. VENTAS ---
elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    with st.form("v", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro = st.text_input("Producto")
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total cobrado (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, especie) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), pro, can, tot, esp))
            conn.commit()
            st.success(f"✅ Venta registrada: {tot}€ ingresados.")

# --- 4. PRODUCCIÓN Y CASA ---
elif menu == "🥚 PRODUCCIÓN Y CASA":
    st.title("🥚 Producción y Autoconsumo")
    with st.form("p", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        can = st.number_input("Cantidad", min_value=0.0)
        dest = st.radio("Destino", ["Venta", "Casa"], horizontal=True)
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad, destino) VALUES (?,?,?,?)", (f.strftime('%d/%m/%Y'), esp, can, dest))
            conn.commit()
            st.success(f"✅ Registrados {can} unidades de {esp} para {dest}.")

# --- 5. GASTOS ---
elif menu == "💸 GASTOS":
    st.title("💸 Gastos Manuales")
    with st.form("g", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Asignar a:", ["Gallinas", "Pollos", "Codornices", "General"])
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipamiento", "Otros"])
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        kil = st.number_input("Kilos de pienso", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie, kilos) VALUES (?,?,?,?,?,?)", (f.strftime('%d/%m/%Y'), con, imp, cat, esp, kil))
            conn.commit()
            st.success(f"✅ Gasto de {imp}€ anotado.")

# --- 6. MANTENIMIENTO ---
elif menu == "🛠️ MANTENIMIENTO":
    st.title("🛠️ Editor de Datos")
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ BORRAR REGISTRO"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}")
        conn.commit()
        st.rerun()
