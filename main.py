import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import io
from datetime import datetime

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="CORRAL INTELIGENTE V.48", layout="wide")
conn = sqlite3.connect('corral_v48_final.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT, tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, concepto TEXT, importe REAL, categoria TEXT, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, cantidad INTEGER, total REAL, raza TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL, especie TEXT)''')
    
    # Gasto de material inicial (21 Feb)
    c.execute("SELECT COUNT(*) FROM gastos WHERE concepto LIKE '%Material%'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                  ('21/02/2026', 'Compra Material y Equipamiento Inicial', 100.0, 'Infraestructura', 'General'))
    conn.commit()

inicializar_db()

def cargar(tabla):
    try:
        return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except:
        return pd.DataFrame()

# --- 2. MENÚ LATERAL ---
menu = st.sidebar.radio("MENÚ PRINCIPAL", ["📊 RENTABILIDAD", "🍗 CRECIMIENTO", "💸 GASTOS", "💰 VENTAS", "🥚 PUESTA", "🐣 ALTA ANIMALES", "🛠️ ADMIN"])

# --- 3. SECCIONES ---

if menu == "📊 RENTABILIDAD":
    st.title("💰 Análisis de Costes y Beneficios")
    df_l = cargar('lotes')
    df_g = cargar('gastos')
    df_v = cargar('ventas')
    
    if not df_l.empty:
        st.subheader("Coste Real por Animal (Compra + Pienso)")
        datos_coste = []
        for _, lote in df_l[df_l['estado']=='Activo'].iterrows():
            c_compra = lote['cantidad'] * lote['precio_ud']
            # Sumar pienso específico para esta raza
            c_pienso = df_g[(df_g['raza'] == lote['raza']) & (df_g['categoria'].str.contains('Pienso', na=False))]['importe'].sum()
            total = c_compra + c_pienso
            coste_ud = total / lote['cantidad']
            datos_coste.append({
                "Lote": f"{lote['especie']} {lote['raza']}",
                "Inversión Total": f"{total:.2f}€",
                "Coste por Animal": f"{coste_ud:.2f}€"
            })
        st.table(pd.DataFrame(datos_coste))
    
    c1, c2 = st.columns(2)
    c1.metric("Gastos Totales", f"{df_g['importe'].sum():.2f}€")
    c2.metric("Ventas Totales", f"{df_v['total'].sum():.2f}€")

elif menu == "🍗 CRECIMIENTO":
    st.title("📈 Reloj Biológico y Madurez")
    df_l = cargar('lotes')
    if not df_l.empty:
        for _, row in df_l[df_l['estado']=='Activo'].iterrows():
            f_ent = datetime.strptime(row['fecha'], '%d/%m/%Y')
            edad_t = (datetime.now() - f_ent).days + int(row['edad_inicial'] or 0)
            
            if row['especie'] == 'Codornices': meta = 45
            elif row['especie'] == 'Pollos': meta = 60 if "Blanco" in (row['tipo_engorde'] or "") else 110
            else: meta = 140
            
            prog = min(1.0, edad_t/meta)
            with st.expander(f"{row['especie']} {row['raza']} - {edad_t} días", expanded=True):
                st.write(f"Objetivo: {meta} días")
                st.progress(prog)
                if edad_t >= meta: st.success("🎯 ¡LISTO!")

elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    df_l = cargar('lotes')
    opciones_rz = ["General"] + (df_l['raza'].unique().tolist() if not df_l.empty else [])
    
    with st.form("f_gasto", clear_on_submit=True):
        f = st.date_input("Fecha")
        cat = st.selectbox("Categoría", ["Pienso Pollos", "Pienso Gallinas", "Pienso Codornices", "Infraestructura", "Salud"])
        rz = st.selectbox("Asignar a Raza:", opciones_rz)
        con = st.text_input("Concepto")
        imp = st.number_input("Importe (€)", min_value=0.0)
        if st.form_submit_button("✅ GUARDAR"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit(); st.rerun()
    st.dataframe(cargar('gastos'))

elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    with st.form("f_venta", clear_on_submit=True):
        f = st.date_input("Fecha")
        pro = st.selectbox("Producto", ["Huevos", "Pollo Vivo", "Canal/Carne"])
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total (€)")
        if st.form_submit_button("✅ REGISTRAR"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), pro, can, tot, "General"))
            conn.commit(); st.rerun()
    st.dataframe(cargar('ventas'))

elif menu == "🥚 PUESTA":
    st.title("🥚 Diario de Puesta")
    with st.form("f_puesta", clear_on_submit=True):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Gallinas", "Codornices"])
        rz = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate", "Azules", "Codorniz"])
        can = st.number_input("Cantidad", min_value=1)
        if st.form_submit_button("✅ ANOTAR"):
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie) VALUES (?,?,?,?)", 
                      (f.strftime('%d/%m/%Y'), rz, can, esp))
            conn.commit(); st.rerun()
    df_p = cargar('produccion')
    if not df_p.empty:
        cmap = {"Chocolate": "#5D4037", "Roja": "#C62828", "Blanca": "#F5F5F5", "Azules": "#81D4FA", "Codorniz": "#BDBDBD"}
        st.plotly_chart(px.bar(df_p, x='fecha', y='cantidad', color='raza', color_discrete_map=cmap))

elif menu == "🐣 ALTA ANIMALES":
    st.title("🐣 Registro de Lotes")
    with st.form("f_alta"):
        f = st.date_input("Fecha adquisición")
        esp = st.selectbox("Especie", ["Pollos", "Gallinas", "Codornices"])
        rz_sel = st.selectbox("Raza", ["Blanca", "Roja", "Chocolate", "Campero", "Codorniz Japónica", "OTRA"])
        rz_nueva = st.text_input("Si elegiste 'OTRA', escribe el nombre:")
        raza_f = rz_nueva if rz_sel == "OTRA" else rz_sel
        tipo = st.selectbox("Tipo/Uso", ["N/A", "Blanco", "Campero", "Puesta"])
        e_ini = st.number_input("Edad al comprar (días)", value=15)
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio/ud €")
        if st.form_submit_button("✅ REGISTRAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, raza, tipo_engorde, edad_inicial, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?,?,?)", 
                      (f_s, esp, raza_f, tipo, e_ini, can, pre, 'Activo'))
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                      (f_s, f"Compra {can} {raza_f}", can*pre, "Animales", raza_f))
            conn.commit(); st.rerun()
    st.dataframe(cargar('lotes'))

elif menu == "🛠️ ADMIN":
    st.title("🛠️ Gestión de Datos")
    if st.button("📥 Generar Copia Excel"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            cargar('lotes').to_excel(writer, sheet_name='Animales', index=False)
            cargar('gastos').to_excel(writer, sheet_name='Gastos', index=False)
            cargar('ventas').to_excel(writer, sheet_name='Ventas', index=False)
            cargar('produccion').to_excel(writer, sheet_name='Puesta', index=False)
        st.download_button(label="⬇️ Descargar Archivo", data=output.getvalue(), file_name="backup_corral.xlsx")
    
    st.divider()
    tab = st.selectbox("Tabla para borrar", ["lotes", "gastos", "ventas", "produccion"])
    df_ad = cargar(tab)
    if not df_ad.empty:
        st.dataframe(df_ad)
        id_b = st.number_input("ID a eliminar", min_value=0)
        if st.button("🗑️ BORRAR"):
            c.execute(f"DELETE FROM {tab} WHERE id=?", (id_b,))
            conn.commit(); st.rerun()
