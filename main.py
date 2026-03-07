import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="CORRAL ESTRATÉGICO V.39", layout="wide")
conn = sqlite3.connect('corral_v38_final.db', check_same_thread=False)
c = conn.cursor()

# --- 2. LÓGICA DE PRECIO SUGERIDO ---
def calcular_precios_sugeridos():
    df_g = pd.read_sql("SELECT raza, importe FROM gastos", conn)
    df_l = pd.read_sql("SELECT raza, cantidad FROM lotes WHERE estado='Activo'", conn)
    
    sugerencias = []
    if not df_l.empty:
        for raza in df_l['raza'].unique():
            total_gastado = df_g[df_g['raza'] == raza]['importe'].sum()
            total_aves = df_l[df_l['raza'] == raza]['cantidad'].sum()
            
            if total_aves > 0:
                coste_por_ave = total_gastado / total_aves
                # Sugerimos un margen del 30% para beneficio
                precio_minimo = coste_por_ave * 1.30
                sugerencias.append({
                    "Raza": raza,
                    "Inversión Total (€)": round(total_gastado, 2),
                    "Coste Real/Ave (€)": round(coste_por_ave, 2),
                    "Precio Sugerido (€)": round(precio_minimo, 2)
                })
    return pd.DataFrame(sugerencias)

# --- 3. MENÚ ---
menu = st.sidebar.radio("CENTRO DE CONTROL", 
    ["💰 UMBRAL DE PRECIOS", "📊 RENTABILIDAD", "🛒 PLAN DE COMPRAS", "🍗 ENGORDE", "🥚 PUESTA", "🐣 NUEVO LOTE", "🛠️ DATOS"])

# --- 4. SECCIÓN: UMBRAL DE PRECIOS (NUEVA) ---
if menu == "💰 UMBRAL DE PRECIOS":
    st.title("💰 ¿A cuánto debo vender mis aves?")
    st.write("Este cálculo suma el precio de compra del lote y el pienso consumido para darte el coste real.")
    
    df_precios = calcular_precios_sugeridos()
    
    if not df_precios.empty:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.table(df_precios.style.highlight_max(subset=['Coste Real/Ave (€)'], color='#ff4b4b'))
        with col2:
            st.info("💡 **Margen del 30%:** El precio sugerido incluye un margen para cubrir imprevistos y tu tiempo de trabajo.")
            
        fig = px.bar(df_precios, x="Raza", y="Coste Real/Ave (€)", title="Coste de Producción por Ave", color="Raza")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Necesitas registrar Gastos (Pienso) asignados a una raza para ver los costes.")

# --- 5. RENTABILIDAD (v38) ---
elif menu == "📊 RENTABILIDAD":
    st.title("📊 Beneficio Neto Acumulado")
    df_v = pd.read_sql("SELECT * FROM ventas", conn)
    df_g = pd.read_sql("SELECT * FROM gastos", conn)
    # (Gráfico de barras Ingresos vs Gastos por raza)
    if not df_v.empty:
        df_plot = df_v.groupby('raza')['total'].sum().reset_index()
        st.plotly_chart(px.pie(df_plot, values='total', names='raza', title="Origen de los Ingresos"))

# --- 6. REGISTRO DE GASTOS (Recordatorio de asignación) ---
elif menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    st.warning("Recuerda asignar el gasto a la **Raza** específica para que el cálculo de precio sea exacto.")
    # (Formulario de gastos v38...)

# --- 7. NUEVO LOTE (v38) ---
elif menu == "🐣 NUEVO LOTE":
    st.title("🐣 Entrada de Lote")
    with st.form("lote_n"):
        f = st.date_input("Fecha")
        esp = st.selectbox("Especie", ["Pollos", "Gallinas"])
        raza = st.text_input("Raza (Blanca, Roja, Chocolate, Campero...)")
        can = st.number_input("Cantidad", min_value=1)
        pre = st.number_input("Precio de compra por ave (€)")
        if st.form_submit_button("REGISTRAR"):
            f_s = f.strftime('%d/%m/%Y')
            c.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, precio_ud, estado) VALUES (?,?,?,?,?,?)",
                      (f_s, esp, raza, can, pre, 'Activo'))
            # Gasto inicial automático para esa raza
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                      (f_s, f"Compra Lote {raza}", can*pre, "Animales", raza))
            conn.commit(); st.success("Registrado.")
