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
    c.execute("""CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
        cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, categoria TEXT, concepto TEXT, cantidad REAL, kilos_pienso REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, tipo_venta TEXT, concepto TEXT, cantidad REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT, proxima_fecha TEXT, estado TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS primera_puesta(id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER UNIQUE, fecha_puesta TEXT)")
    
    # Parche de seguridad para columnas nuevas
    try: c.execute("ALTER TABLE gastos ADD COLUMN kilos_pienso REAL DEFAULT 0")
    except: pass
    conn.commit()
    conn.close()

def cargar(tabla):
    conn = get_conn()
    try:
        df = pd.read_sql(f"SELECT * FROM {tabla}", conn)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def eliminar_reg(tabla, id_reg):
    conn = get_conn()
    conn.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_reg,))
    conn.commit()
    conn.close()

inicializar_db()

# ====================== 2. CARGA DE DATOS Y CÁLCULOS ======================
lotes = cargar("lotes")
prod = cargar("produccion")
gastos = cargar("gastos")
ventas = cargar("ventas")
bajas = cargar("bajas")
salud = cargar("salud")

# --- LÓGICA DE STOCK DE PIENSO ---
t_kg = gastos["kilos_pienso"].sum() if not gastos.empty else 0
consumo_diario_total = 0
if not lotes.empty:
    for _, r in lotes.iterrows():
        b_lote = bajas[bajas['lote']==r['id']]['cantidad'].sum() if not bajas.empty else 0
        vivas = r['cantidad'] - b_lote
        # Consumo estimado por especie
        factor = 0.120 if r['especie'] == "Gallinas" else 0.150 if r['especie'] == "Pollos" else 0.030
        consumo_diario_total += vivas * factor
dias_pienso = (t_kg / consumo_diario_total) if consumo_diario_total > 0 else 0

# ====================== 3. MENÚ LATERAL ======================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard Elite", "🐣 Alta de Lotes", "📈 Crecimiento y Vejez", 
    "🥚 Producción Diaria", "🌟 Primera Puesta", "💸 Gastos e Inventario", 
    "💰 Ventas y Clientes", "💉 Salud y Alertas", "📜 Histórico y Borrar", "💾 SEGURIDAD"
])

# --- DASHBOARD ELITE ---
if menu == "🏠 Dashboard Elite":
    st.title("🏠 Panel de Control")
    c1, c2, c3, c4 = st.columns(4)
    
    t_v = ventas[ventas['tipo_venta']=='Venta Cliente']['cantidad'].sum() if not ventas.empty else 0
    t_g = gastos['cantidad'].sum() if not gastos.empty else 0
    t_ahorro = ventas[ventas['tipo_venta']=='Consumo Propio']['cantidad'].sum() if not ventas.empty else 0
    t_h = prod['huevos'].sum() if not prod.empty else 0
    
    c1.metric("Stock Pienso", f"{dias_pienso:.1f} días")
    c2.metric("Balance Real", f"{(t_v - t_g):.2f}€")
    c3.metric("Ahorro Casa", f"{t_ahorro:.2f}€")
    c4.metric("Huevos Totales", int(t_h))

# --- CRECIMIENTO Y VEJEZ (CORREGIDO) ---
elif menu == "📈 Crecimiento y Vejez":
    st.title("📈 Estado de Desarrollo por Raza")
    if lotes.empty:
        st.info("No hay lotes registrados. Ve a 'Alta de Lotes'.")
    else:
        config_r = {
            "Roja": {"meta": 140, "vejez": 700}, 
            "Blanca": {"meta": 155, "vejez": 750},
            "Chocolate": {"meta": 170, "vejez": 800}, 
            "Blanco Engorde": {"meta": 45, "vejez": 60},
            "Campero": {"meta": 90, "vejez": 120}, 
            "Codorniz": {"meta": 42, "vejez": 365}
        }
        for _, r in lotes.iterrows():
            # Cálculo de edad independiente de gastos
            fecha_llegada = datetime.strptime(r["fecha"], "%d/%m/%Y")
            dias_desde_llegada = (datetime.now() - fecha_llegada).days
            edad_actual = dias_desde_llegada + r["edad_inicial"]
            
            conf = config_r.get(r["raza"], {"meta": 150, "vejez": 730})
            
            with st.expander(f"Lote {r['id']}: {r['raza']} ({r['especie']})"):
                col_a, col_b = st.columns(2)
                col_a.write(f"🎂 **Edad actual:** {edad_actual} días")
                col_a.write(f"📅 **Llegada:** {r['fecha']}")
                
                progreso = min(100, int((edad_actual / conf["meta"]) * 100))
                st.progress(progreso / 100)
                st.write(f"Progreso hacia madurez ({conf['meta']} días): **{progreso}%**")
                
                if edad_actual > conf["vejez"]:
                    st.error(f"⚠️ ALERTA VEJEZ: Lote con {edad_actual} días. Supera el límite de {conf['vejez']}.")

# --- GASTOS E INVENTARIO ---
elif menu == "💸 Gastos e Inventario":
    st.title("💸 Registro de Gastos")
    with st.form("f_g"):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Gallinas", "Pienso Pollos", "Pienso Codornices", "Infraestructura", "Salud", "Otros"])
        con = st.text_input("Concepto")
        c1, c2 = st.columns(2)
        imp = c1.number_input("Importe €", 0.0)
        kg = c2.number_input("Kilos (si es pienso)", 0.0)
        if st.form_submit_button("💾 GUARDAR GASTO"):
            conn = get_conn()
            conn.execute("INSERT INTO gastos (fecha, categoria, concepto, cantidad, kilos_pienso) VALUES (?,?,?,?,?)", 
                         (f.strftime("%d/%m/%Y"), cat, con, imp, kg))
            conn.commit(); conn.close()
            st.success(f"✔️ CONFIRMADO: Gasto de {imp}€ en {con} guardado."); st.rerun()

# --- HISTÓRICO Y BORRADO ---
elif menu == "📜 Histórico y Borrar":
    st.title("📜 Histórico de Datos")
    t_sel = st.selectbox("Selecciona tabla para revisar:", ["produccion", "gastos", "ventas", "salud", "bajas", "lotes"])
    df_h = cargar(t_sel)
    if not df_h.empty:
        st.dataframe(df_h, use_container_width=True)
        id_b = st.number_input("ID del registro a eliminar", min_value=1, step=1)
        if st.button("❌ BORRAR REGISTRO DEFINITIVAMENTE"):
            if id_b in df_h['id'].values:
                eliminar_reg(t_sel, id_b)
                st.error(f"Registro {id_b} eliminado."); st.rerun()
            else: st.warning("ID no encontrado.")
    else: st.write("No hay datos todavía.")

# --- SEGURIDAD ---
elif menu == "💾 SEGURIDAD":
    st.title("💾 Copia de Seguridad")
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f: st.download_button("📥 DESCARGAR BASE DE DATOS (.db)", f, "mi_corral.db")
    up = st.file_uploader("📤 RESTAURAR COPIA", type="db")
    if up:
        with open(DB_PATH, "wb") as f: f.write(up.getbuffer())
        st.success("✅ Datos restaurados."); st.rerun()

# --- RESTO DE FUNCIONES (ALTA, PRODUCCION, VENTAS, SALUD) ---
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Alta de Lotes")
    with st.form("f_alta"):
        f_ll = st.date_input("Fecha llegada")
        esp = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
        razas_d = {"Gallinas": ["Roja", "Blanca", "Chocolate"], "Pollos": ["Blanco Engorde", "Campero"], "Codornices": ["Codorniz"]}
        rz = st.selectbox("Raza", razas_d[esp])
        c1, c2 = st.columns(2)
        cant = c1.number_input("Cantidad", 1); edad = c1.number_input("Edad inicial días", 0)
        prec = c2.number_input("Precio ud €", 0.0)
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn()
            conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) VALUES (?,?,?,?,?,?,'Activo')", 
                         (f_ll.strftime("%d/%m/%Y"), esp, rz, int(cant), int(edad), prec))
            conn.commit(); conn.close(); st.success("✔️ CONFIRMADO: Lote guardado."); st.rerun()

elif menu == "💰 Ventas y Clientes":
    st.title("💰 Ventas")
    tipo = st.radio("Destino:", ["Venta Cliente", "Consumo Propio"])
    with st.form("f_v"):
        f = st.date_input("Fecha"); cli = st.text_input("Cliente/Quién", "Familia" if tipo=="Consumo Propio" else "")
        prod_v = st.text_input("Producto"); imp = st.number_input("Euros €", 0.0)
        if st.form_submit_button("🤝 REGISTRAR"):
            conn = get_conn()
            conn.execute("INSERT INTO ventas (fecha, cliente, tipo_venta, concepto, cantidad) VALUES (?,?,?,?,?)", 
                         (f.strftime("%d/%m/%Y"), cli, tipo, prod_v, imp))
            conn.commit(); conn.close(); st.success("✔️ CONFIRMADO: Venta registrada."); st.rerun()

else: # Produccion, Salud, Primera Puesta
    st.title(f"Registro: {menu}")
    with st.form("f_gen"):
        f = st.date_input("Fecha"); l_id = st.number_input("ID Lote", 1)
        if "Producción" in menu: val = st.number_input("Huevos", 1)
        elif "Salud" in menu: desc = st.text_area("Tratamiento"); prox = st.date_input("Próxima")
        elif "Puesta" in menu: f_p = st.date_input("Fecha hito")
        
        if st.form_submit_button("✅ GUARDAR"):
            conn = get_conn(); f_s = f.strftime("%d/%m/%Y")
            if "Producción" in menu: conn.execute("INSERT INTO produccion (fecha, lote, huevos) VALUES (?,?,?)", (f_s, int(l_id), int(val)))
            elif "Salud" in menu: conn.execute("INSERT INTO salud (fecha, lote, descripcion, proxima_fecha, estado) VALUES (?,?,?,?,'Pendiente')", (f_s, int(l_id), desc, prox.strftime("%d/%m/%Y")))
            elif "Puesta" in menu: conn.execute("INSERT OR REPLACE INTO primera_puesta (lote_id, fecha_puesta) VALUES (?,?)", (int(l_id), f_p.strftime("%d/%m/%Y")))
            conn.commit(); conn.close(); st.success("✔️ CONFIRMADO."); st.rerun()
