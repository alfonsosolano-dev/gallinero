import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL V.25.5 - AUTOCONSUMO", layout="wide")
conn = sqlite3.connect('corral_v24_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, especie TEXT, kilos REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, especie TEXT, tipo_venta TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, cantidad REAL)')
    
    # Parche para la nueva columna 'tipo_venta'
    try: c.execute("ALTER TABLE ventas ADD COLUMN tipo_venta TEXT DEFAULT 'Externa'")
    except: pass
    conn.commit()

def limpiar_df(df):
    if df.empty: return df
    df = df.rename(columns={'fecha_entrada': 'fecha', 'cantidad_inicial': 'cantidad'})
    return df.loc[:, ~df.columns.duplicated()]

inicializar_db()

# --- MENÚ ---
menu = st.sidebar.radio("MENÚ", ["📊 DASHBOARD", "🐣 LOTES", "💰 SALIDAS (VENTA/CASA)", "🥚 PRODUCCIÓN", "💸 GASTOS", "🛠️ DATOS"])

# --- 1. DASHBOARD ---
if menu == "📊 DASHBOARD":
    st.title("📊 Resumen Contable")
    
    # Cálculos
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    ing_reales = df_v[df_v['tipo_venta'] == 'Externa']['total'].sum()
    ahorro_casa = df_v[df_v['tipo_venta'] == 'Consumo Propio'].shape[0] # Conteo simple o podrías valorar por precio
    gas_total = pd.read_sql("SELECT SUM(importe) as i FROM gastos", conn)['i'].iloc[0] or 0.0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("DINERO EN CAJA", f"{round(ing_reales, 2)} €")
    c2.metric("GASTOS TOTALES", f"{round(gas_total, 2)} €")
    c3.metric("BALANCE NETO", f"{round(ing_reales - gas_total, 2)} €")

    st.divider()
    
    # Rentabilidad por Especie
    st.subheader("🎯 Beneficio por Especie")
    resumen = []
    for e in ["Gallinas", "Pollos", "Codornices"]:
        v_ext = df_v[(df_v['especie'] == e) & (df_v['tipo_venta'] == 'Externa')]['total'].sum()
        g_ext = pd.read_sql(f"SELECT SUM(importe) as i FROM gastos WHERE especie='{e}'", conn)['i'].iloc[0] or 0.0
        c_casa = df_v[(df_v['especie'] == e) & (df_v['tipo_venta'] == 'Consumo Propio')]['cantidad'].sum()
        resumen.append({"Especie": e, "Ventas (€)": v_ext, "Gastos (€)": g_ext, "Neto (€)": round(v_ext-g_ext,2), "Consumo Casa": f"{int(c_casa)} uds"})
    st.table(pd.DataFrame(resumen))

# --- 3. VENTAS Y AUTOCONSUMO ---
elif menu == "💰 SALIDAS (VENTA/CASA)":
    st.title("💰 Registro de Salidas")
    st.info("Registra aquí tanto lo que vendes como lo que consumes en casa.")
    with st.form("f_v", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        tipo = col1.selectbox("Tipo de Salida", ["Externa", "Consumo Propio"])
        esp = col2.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        pro = col2.text_input("Producto (ej: Huevos)")
        can = col1.number_input("Cantidad", min_value=1)
        
        # El precio solo importa si es venta externa
        pre_sugerido = 0.0 if tipo == "Consumo Propio" else 0.50
        tot = col2.number_input("Total Cobrado (€)", min_value=0.0, value=pre_sugerido)
        
        if st.form_submit_button("✅ CONFIRMAR SALIDA"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, especie, tipo_venta) VALUES (?,?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), pro, can, tot, esp, tipo))
            conn.commit()
            color = "verde" if tipo == "Externa" else "azul"
            st.success(f"✅ REGISTRADO: {can} {pro} como {tipo}. Confirmado visualmente en verde.")

# --- 4. PRODUCCIÓN ---
elif menu == "🥚 PRODUCCIÓN":
    st.title("🥚 Producción Diaria (Recogida)")
    with st.form("f_p", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Codornices", "Pollos"])
        can = st.number_input("Cantidad Recogida", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR RECOGIDA"):
            c.execute("INSERT INTO produccion (fecha, especie, cantidad) VALUES (?,?,?)", (f.strftime('%d/%m/%Y'), esp, can))
            conn.commit(); st.success(f"✅ Producción de {can} unidades anotada.")

# --- RESTO DE PESTAÑAS (Mantenidas por consistencia) ---
elif menu == "🐣 LOTES":
    with st.form("l", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        can = st.number_input("Cantidad", min_value=1); pre = st.number_input("Precio/ud")
        if st.form_submit_button("✅ GUARDAR LOTE"):
            f_s = f.strftime('%d/%m/%Y'); c.execute("INSERT INTO lotes (fecha, especie, cantidad, precio_ud, estado) VALUES (?,?,?,?,?)", (f_s, esp, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,'Animales',?)", (f_s, f"Lote {esp}", can*pre, esp))
            conn.commit(); st.success("✅ Lote y Gasto registrados.")

elif menu == "💸 GASTOS":
    with st.form("g", clear_on_submit=True):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices", "General"])
        cat = st.selectbox("Categoría", ["Pienso", "Salud", "Equipos"]); imp = st.number_input("Importe €")
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, especie) VALUES (?,?,?,?,?)", (f.strftime('%d/%m/%Y'), "Gasto", imp, cat, esp))
            conn.commit(); st.success("✅ Gasto anotado.")

elif menu == "🛠️ DATOS":
    t = st.selectbox("Tabla", ["lotes", "gastos", "ventas", "produccion"])
    df = limpiar_df(pd.read_sql(f"SELECT * FROM {t} ORDER BY id DESC", conn))
    st.dataframe(df, use_container_width=True)
    idx = st.number_input("ID a borrar", min_value=0)
    if st.button("❌ BORRAR"):
        c.execute(f"DELETE FROM {t} WHERE id={idx}"); conn.commit(); st.rerun()
