import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# ====================== 1. CONFIGURACIÓN Y BASE DE DATOS ======================
st.set_page_config(page_title="CORRAL MAESTRO ELITE V13.1", layout="wide", page_icon="🐓")
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_y_reparar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS lotes(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT, perdida_estimada REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS hitos(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, tipo TEXT, fecha TEXT)")
    
    try: c.execute("ALTER TABLE gastos ADD COLUMN kilos_pienso REAL DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE bajas ADD COLUMN perdida_estimada REAL DEFAULT 0")
    except: pass
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try: return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except: return pd.DataFrame()
    finally: conn.close()

def eliminar_reg(tabla, id_reg):
    conn = get_conn()
    conn.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_reg,))
    conn.commit()
    conn.close()

inicializar_y_reparar_db()

# ====================== 2. CARGA Y CÁLCULOS CORREGIDOS ======================
lotes = cargar("lotes"); prod = cargar("produccion"); gastos = cargar("gastos")
ventas = cargar("ventas"); bajas = cargar("bajas"); hitos = cargar("hitos")

def calcular_stock_real(categoria_pienso, especie_filtro):
    kg_comprados = gastos[gastos['categoria'] == categoria_pienso]['kilos_pienso'].sum() if not gastos.empty else 0
    consumo_diario_actual = 0
    total_consumido_historico = 0
    
    if not lotes.empty:
        lotes_esp = lotes[lotes['especie'] == especie_filtro]
        for _, r in lotes_esp.iterrows():
            # 1. Vivas
            b_l = bajas[bajas['lote'] == r['id']]['cantidad'].sum() if not bajas.empty else 0
            vivas = max(0, r['cantidad'] - b_l)
            
            # 2. Fechas
            f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias_desde_alta = (datetime.now() - f_l).days
            edad_hoy = dias_desde_alta + r["edad_inicial"]
            
            # 3. Factor de consumo
            if especie_filtro == "Gallinas": f = 0.120
            elif especie_filtro == "Codornices": f = 0.030
            else: # Pollos dinámico
                f = 0.050 if edad_hoy < 14 else 0.120 if edad_hoy < 30 else 0.180
            
            consumo_diario_actual += (vivas * f)
            # Descontamos consumo desde el día que llegaron hasta hoy
            total_consumido_historico += (vivas * f * max(0, dias_desde_alta))

    disponible = max(0, kg_comprados - total_consumido_historico)
    return disponible, consumo_diario_actual

# Ejecución de cálculos
stock_gal_kg, cons_gal_dia = calcular_stock_real("Pienso Gallinas", "Gallinas")
stock_pol_kg, cons_pol_dia = calcular_stock_real("Pienso Pollos", "Pollos")
stock_cod_kg, cons_cod_dia = calcular_stock_real("Pienso Codornices", "Codornices")

# --- BALANCE FINANCIERO REAL ---
ingresos = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
gastos_totales = gastos['cantidad'].sum() if not gastos.empty else 0
# Coste de los lotes (Cantidad inicial * Precio que costó cada ave)
inversion_lotes = (lotes['cantidad'] * lotes['precio_ud']).sum() if not lotes.empty else 0
balance_final = ingresos - gastos_totales - inversion_lotes

# ====================== 3. INTERFAZ ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard Elite", "🐣 Alta de Lotes", "📈 Crecimiento y Vejez", 
    "🥚 Producción Diaria", "🌟 Primera Puesta", "💸 Gastos e Inventario", 
    "💰 Ventas y Clientes", "💀 Registro de Bajas", "📜 Histórico y Borrar", "💾 SEGURIDAD"
])

if menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control Real")
    
    st.subheader("📦 Almacén de Pienso (Descontando consumo diario)")
    c_g, c_p, c_c = st.columns(3)
    c_g.metric("Gallinas", f"{stock_gal_kg:.1f} kg", f"-{cons_gal_dia:.2f} kg/día")
    c_p.metric("Pollos", f"{stock_pol_kg:.1f} kg", f"-{cons_pol_dia:.2f} kg/día")
    c_c.metric("Codornices", f"{stock_cod_kg:.1f} kg", f"-{cons_cod_dia:.2f} kg/día")

    st.divider()
    st.subheader("💰 Balance Económico")
    f1, f2, f3 = st.columns(3)
    f1.metric("Balance Real", f"{balance_final:.2f} €", help="Ingresos - Gastos - Inversión Lotes")
    f2.metric("Inversión Animales", f"{inversion_lotes:.2f} €")
    f3.metric("Gastos (Pienso/Obra)", f"{gastos_totales:.2f} €")

elif menu == "🌟 Primera Puesta":
    st.title("🌟 Registro de Primera Puesta")
    with st.form("f_p"):
        l_id = st.selectbox("Lote", lotes[lotes['especie']=='Gallinas']['id'].tolist() if not lotes.empty else [])
        f_h = st.date_input("Fecha primer huevo")
        if st.form_submit_button("Guardar Hito"):
            conn = get_conn()
            conn.execute("INSERT INTO hitos (lote_id, tipo, fecha) VALUES (?, 'Primera Puesta', ?)", (int(l_id), f_h.strftime("%d/%m/%Y")))
            conn.commit(); conn.close(); st.success("Hito registrado."); st.rerun()

elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Crecimiento")
    conf = {"Roja": 140, "Blanca": 155, "Chocolate": 170, "Blanco Engorde": 45, "Campero": 90, "Codorniz": 42}
    for _, r in lotes.iterrows():
        f_l = datetime.strptime(r["fecha"], "%d/%m/%Y")
        edad = (datetime.now() - f_l).days + r["edad_inicial"]
        meta = conf.get(r["raza"], 150)
        porc = min(100, int((edad/meta)*100))
        ya_pone = "🥚" if not hitos[(hitos['lote_id']==r['id']) & (hitos['tipo']=='Primera Puesta')].empty else "⏳"
        with st.expander(f"Lote {r['id']}: {r['raza']} {ya_pone} ({porc}%)"):
            st.progress(porc/100)
            st.write(f"Edad: {edad} días. Meta: {meta} días.")

elif menu == "💸 Gastos e Inventario":
    st.title("💸 Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha"); cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Otros"])
        con = st.text_input("Concepto"); c1, c2 = st.columns(2); imp = c1.number_input("€", 0.0); kg = c2.number_input("Kg", 0.0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close(); st.success("Guardado."); st.rerun()

elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Alta de Lote")
    with st.form("f_a"):
        f = st.date_input("Fecha"); esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        rz = st.selectbox("Raza", ["Roja", "Blanca", "Chocolate", "Blanco Engorde", "Campero", "Codorniz"])
        c1, c2 = st.columns(2); cant = c1.number_input("Cant", 1); ed = c1.number_input("Edad inicial", 0); pr = c2.number_input("Precio Ud", 0.0)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", (f.strftime("%d/%m/%Y"), esp, rz, int(cant), int(ed), pr))
            conn.commit(); conn.close(); st.success("Lote creado."); st.rerun()

elif menu == "📜 Histórico y Borrar":
    st.title("📜 Histórico")
    t_sel = st.selectbox("Tabla", ["lotes", "gastos", "produccion", "ventas", "bajas", "hitos"])
    df = cargar(t_sel); st.dataframe(df)
    id_b = st.number_input("ID a borrar", 1)
    if st.button("Eliminar"): eliminar_reg(t_sel, id_b); st.rerun()

elif menu == "💾 SEGURIDAD":
    st.title("💾 Seguridad")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("Descargar DB", f, "corral.db")
    if st.button("Reiniciar Sistema"):
        if os.path.exists(DB_PATH): os.remove(DB_PATH); st.rerun()

else: # Ventas / Producción / Bajas
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha"); l_id = st.number_input("Lote ID", 1)
        if "Producción" in menu: val = st.number_input("Huevos", 1)
        elif "Bajas" in menu: val = st.number_input("Cant", 1); mot = st.text_input("Motivo")
        elif "Ventas" in menu: cli = st.text_input("Cliente"); pr = st.text_input("Producto"); val = st.number_input("€")
        if st.form_submit_button("Guardar"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
            elif "Bajas" in menu:
                # Calcular pérdida económica de la baja
                l_sel = lotes[lotes['id']==l_id].iloc[0]
                perd = val * l_sel['precio_ud']
                conn.execute("INSERT INTO bajas (fecha, lote, cantidad, motivo, perdida_estimada) VALUES (?,?,?,?,?)", (f_s, int(l_id), int(val), mot, perd))
            elif "Ventas" in menu: conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", (f_s, cli, "Venta Cliente", pr, val))
            conn.commit(); conn.close(); st.success("Hecho."); st.rerun()
