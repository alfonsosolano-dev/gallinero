# app.py - Corral Maestro PRO v1
import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_conn, cargar, eliminar_reg
from calculos import consumo_diario_total, dias_pienso_lotes, balance_total, huevos_por_gallina
from graficos import grafico_produccion, grafico_gastos_categoria
from utils import alertas_pienso, alertas_produccion

# ================== 1. Configuración ==================
st.set_page_config(
    page_title="Corral Maestro PRO",
    page_icon="🐓",
    layout="wide"
)

# ================== 2. Cargar Datos ==================
lotes = cargar("lotes")
produccion = cargar("produccion")
gastos = cargar("gastos")
ventas = cargar("ventas")
bajas = cargar("bajas")
salud = cargar("salud")

# ================== 3. Calculos ==================
consumo_total = consumo_diario_total(lotes, bajas)
dias_pienso = dias_pienso_lotes(lotes, bajas, gastos)
balance = balance_total(ventas, gastos)
t_huevos = produccion["huevos"].sum() if not produccion.empty else 0
huevos_gallina = huevos_por_gallina(produccion, lotes, bajas)

# ================== 4. Alertas ==================
alertas_pienso(dias_pienso)
alertas_produccion(produccion)

# ================== 5. Menú lateral ==================
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", [
    "🏠 Dashboard", "🐣 Alta de Lotes", "📈 Crecimiento y Vejez",
    "🥚 Producción Diaria", "💸 Gastos", "💰 Ventas", 
    "💉 Salud", "📜 Histórico", "💾 Backup"
])

# ================== 6. Dashboard ==================
if menu == "🏠 Dashboard":
    st.title("🏠 Panel de Control Corral Maestro PRO")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock Pienso", f"{dias_pienso:.1f} días")
    c2.metric("Balance Real", f"{balance:.2f} €")
    c3.metric("Huevos Totales", t_huevos)
    c4.metric("Huevos por Gallina", round(huevos_gallina,2))

    st.subheader("📊 Producción Últimos 30 días")
    grafico_produccion(produccion)

    st.subheader("💸 Gastos por Categoría")
    grafico_gastos_categoria(gastos)

# ================== 7. Formularios ==================
elif menu == "🐣 Alta de Lotes":
    st.title("🐣 Registrar Lote")
    with st.form("f_lote"):
        fecha = st.date_input("Fecha")
        especie = st.selectbox("Especie", ["Gallinas","Pollos","Codornices"])
        razas = {"Gallinas":["Roja","Blanca","Chocolate"],
                 "Pollos":["Blanco Engorde","Campero"],
                 "Codornices":["Codorniz"]}
        raza = st.selectbox("Raza", razas[especie])
        cantidad = st.number_input("Cantidad", min_value=1, value=10)
        edad_inicial = st.number_input("Edad inicial", min_value=0)
        if st.form_submit_button("✅ Guardar"):
            conn = get_conn()
            conn.execute("INSERT INTO lotes (fecha, especie, raza, cantidad, edad_inicial, estado) VALUES (?,?,?,?,?,'Activo')",
                         (fecha.strftime("%d/%m/%Y"), especie, raza, cantidad, edad_inicial))
            conn.commit(); conn.close()
            st.success("✔️ Lote registrado")
            st.experimental_rerun()

elif menu == "📜 Histórico":
    st.title("📜 Histórico de Datos")
    tabla = st.selectbox("Tabla", ["produccion","gastos","ventas","salud","bajas","lotes"])
    df_h = cargar(tabla)
    st.dataframe(df_h, use_container_width=True)
    id_borrar = st.number_input("ID a borrar", min_value=1, step=1)
    if st.button("❌ Borrar Registro"):
        if id_borrar in df_h["id"].values:
            eliminar_reg(tabla, id_borrar)
            st.success("Registro eliminado")
            st.experimental_rerun()

# ================== 8. Backup ==================
elif menu == "💾 Backup":
    st.title("💾 Backup Base de Datos")
    from pathlib import Path
    DB_PATH = Path("corral_maestro_pro.db")
    if DB_PATH.exists():
        with open(DB_PATH, "rb") as f:
            st.download_button("📥 Descargar .db", f, file_name="corral_maestro_pro.db")
    up = st.file_uploader("📤 Restaurar .db", type="db")
    if up:
        with open(DB_PATH, "wb") as f:
            f.write(up.getbuffer())
        st.success("Base de datos restaurada")
        st.experimental_rerun()

# ================== 9. Otros menús ==================
# Puedes agregar producción diaria, ventas y salud aquí usando formularios similares
