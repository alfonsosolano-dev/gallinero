import streamlit as st
import sqlite3
import pandas as pd
import os
import io
from datetime import datetime, timedelta
import plotly.express as px

# ====================== CONFIGURACIÓN DE PÁGINA ======================
st.set_page_config(page_title="CORRAL MAESTRO PRO", layout="wide", page_icon="🐓")

# ====================== BASE DE DATOS ======================
# Usamos una ruta simple para asegurar compatibilidad en la nube
DB_PATH = "corral_maestro_pro.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    # Lotes
    c.execute("""CREATE TABLE IF NOT EXISTS lotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, 
        cantidad INTEGER, edad_inicial INTEGER, precio_ud REAL, estado TEXT)""")
    # Producción huevos
    c.execute("CREATE TABLE IF NOT EXISTS produccion(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, huevos INTEGER)")
    # Gastos
    c.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, cantidad REAL)")
    # Ventas
    c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, cantidad REAL)")
    # Salud
    c.execute("CREATE TABLE IF NOT EXISTS salud(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, descripcion TEXT)")
    # Bajas
    c.execute("CREATE TABLE IF NOT EXISTS bajas(id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, lote INTEGER, cantidad INTEGER, motivo TEXT)")
    # Primera puesta
    c.execute("CREATE TABLE IF NOT EXISTS primera_puesta(id INTEGER PRIMARY KEY AUTOINCREMENT, lote INTEGER, fecha TEXT)")
    conn.commit()
    conn.close()

inicializar_db()

# ====================== FUNCIONES AUXILIARES ======================
def cargar(tabla):
    conn = get_conn()
    try:
        return pd.read_sql(f"SELECT * FROM {tabla}", conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()

# ====================== MENÚ LATERAL ======================
st.sidebar.title("🐓 CORRAL PRO")
menu = st.sidebar.selectbox("MENÚ",[
    "Dashboard", "Alta Animales", "Puesta", "Crecimiento", 
    "Gastos", "Ventas", "Salud", "Bajas", "Rentabilidad", "💾 SEGURIDAD"
])

# ====================== 1. DASHBOARD ======================
if menu=="Dashboard":
    st.title("🏠 Dashboard General")
    lotes = cargar("lotes")
    prod = cargar("produccion")
    gastos = cargar("gastos")
    ventas = cargar("ventas")
    bajas = cargar("bajas")

    total_ani = lotes["cantidad"].sum() if not lotes.empty else 0
    total_bajas = bajas["cantidad"].sum() if not bajas.empty else 0
    aves_vivas = total_ani - total_bajas
    
    total_huevos = prod["huevos"].sum() if not prod.empty else 0
    total_gasto = gastos["cantidad"].sum() if not gastos.empty else 0
    total_venta = ventas["cantidad"].sum() if not ventas.empty else 0
    beneficio = total_venta - total_gasto

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Aves Vivas", int(aves_vivas))
    c2.metric("Huevos", int(total_huevos))
    c3.metric("Ventas", f"{total_venta:.2f}€")
    c4.metric("Gastos", f"{total_gasto:.2f}€")
    c5.metric("Beneficio", f"{beneficio:.2f}€", delta=float(beneficio))

# ====================== 2. ALTA DE ANIMALES (RAZAS ESPECÍFICAS) ======================
elif menu=="Alta Animales":
    st.title("🐣 Entrada de animales")
    
    with st.form("f_alta"):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha = st.date_input("Fecha de llegada")
            especie = st.selectbox("Especie", ["Gallinas", "Pollos", "Codornices"])
            
            # Razas específicas según hablamos
            if especie == "Gallinas":
                raza = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate"])
            elif especie == "Pollos":
                raza = st.selectbox("Raza", ["Blanco Engorde", "Campero"])
            else:
                raza = st.selectbox("Raza", ["Codorniz"])
                
        with col2:
            cantidad = st.number_input("Cantidad de aves", min_value=1, step=1)
            edad = st.number_input("Edad inicial (días)", min_value=0, step=1)
            precio = st.number_input("Precio por unidad (€)", min_value=0.0, format="%.2f")
            
        if st.form_submit_button("✅ GUARDAR LOTE"):
            conn = get_conn()
            conn.execute("""
                INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, precio_ud, estado) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (fecha.strftime("%d/%m/%Y"), especie, raza, int(cantidad), int(edad), precio, "Activo"))
            conn.commit()
            conn.close()
            st.success(f"✅ Lote de {especie} {raza} guardado con éxito.")
            st.balloons()

# ====================== 3. PUESTA ======================
elif menu=="Puesta":
    st.title("🥚 Registro de huevos")
    lotes = cargar("lotes")
    if not lotes.empty:
        with st.form("f_puesta"):
            lote = st.selectbox("Lote ID", lotes["id"])
            fecha = st.date_input("Fecha")
            huevos = st.number_input("Cantidad de Huevos", 0)
            if st.form_submit_button("Guardar Producción"):
                conn = get_conn()
                conn.execute("INSERT INTO produccion (fecha,lote,huevos) VALUES (?,?,?)", (fecha.strftime("%d/%m/%Y"), lote, huevos))
                conn.commit()
                conn.close()
                st.success("✅ Guardado")
    else: st.info("Crea un lote primero")

# ====================== 4. CRECIMIENTO ======================
elif menu=="Crecimiento":
    st.title("📈 Crecimiento / Madurez")
    lotes = cargar("lotes")
    for _, row in lotes.iterrows():
        fecha_ent = datetime.strptime(row["fecha"], "%d/%m/%Y")
        edad_actual = (datetime.now() - fecha_ent).days + row["edad_inicial"]
        meta = 140 if row["especie"]=="Gallinas" else 90
        prog = min(1.0, edad_actual/meta)
        st.write(f"**Lote {row['id']}**: {row['especie']} - {edad_actual} días")
        st.progress(prog)

# ====================== 5. GASTOS / VENTAS / SALUD / BAJAS ======================
elif menu in ["Gastos", "Ventas", "Salud", "Bajas"]:
    st.title(f"📝 Registro de {menu}")
    with st.form("f_generico"):
        fecha = st.date_input("Fecha")
        if menu == "Gastos" or menu == "Ventas":
            concepto = st.text_input("Concepto")
            monto = st.number_input("Importe €", 0.0)
        elif menu == "Salud":
            lote = st.number_input("ID Lote", 1)
            desc = st.text_area("Descripción")
        elif menu == "Bajas":
            lote = st.number_input("ID Lote", 1)
            cant = st.number_input("Cantidad", 1)
            motivo = st.text_input("Motivo")
            
        if st.form_submit_button(f"Registrar {menu}"):
            conn = get_conn()
            if menu=="Gastos": conn.execute("INSERT INTO gastos (fecha,concepto,cantidad) VALUES (?,?,?)",(fecha.strftime("%d/%m/%Y"), concepto, monto))
            elif menu=="Ventas": conn.execute("INSERT INTO ventas (fecha,concepto,cantidad) VALUES (?,?,?)",(fecha.strftime("%d/%m/%Y"), concepto, monto))
            elif menu=="Salud": conn.execute("INSERT INTO salud (fecha,lote,descripcion) VALUES (?,?,?)",(fecha.strftime("%d/%m/%Y"), lote, desc))
            elif menu=="Bajas": conn.execute("INSERT INTO bajas (fecha,lote,cantidad,motivo) VALUES (?,?,?,?)",(fecha.strftime("%d/%m/%Y"), lote, cant, motivo))
            conn.commit()
            conn.close()
            st.success("✅ Registrado")

# ====================== 6. RENTABILIDAD ======================
elif menu=="Rentabilidad":
    st.title("📊 Análisis Económico")
    g = cargar("gastos")
    v = cargar("ventas")
    if not g.empty or not v.empty:
        df = pd.concat([g.assign(Tipo="Gasto"), v.assign(Tipo="Venta")])
        fig = px.bar(df, x="fecha", y="cantidad", color="Tipo", barmode="group", title="Gastos vs Ventas")
        st.plotly_chart(fig, use_container_width=True)

# ====================== 7. 💾 SEGURIDAD (IMPORTANTE) ======================
elif menu=="💾 SEGURIDAD":
    st.title("💾 Gestión de Datos y Seguridad")
    st.warning("En la nube, los datos pueden borrarse si la app se reinicia. ¡Descarga tu copia siempre!")
    
    # Descargar
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 DESCARGAR BASE DE DATOS (.db)", f, file_name="corral_maestro.db")
    
    st.divider()
    
    # Subir
    st.subheader("📤 Restaurar Copia de Seguridad")
    archivo = st.file_uploader("Saca tu archivo .db guardado para recuperar todo", type="db")
    if archivo is not None:
        with open(DB_PATH, "wb") as f:
            f.write(archivo.getbuffer())
        st.success("✅ Datos restaurados correctamente. Refresca la página.")

