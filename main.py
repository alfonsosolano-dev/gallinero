import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# Título de prueba para ver si carga
st.title("🚜 Prueba de Conexión")

# Verificamos si los secrets están cargados
if "connections" not in st.secrets:
    st.error("❌ No se encuentran los 'Secrets'. Revisa la configuración en Streamlit Cloud.")
    st.stop()

# Recuperamos la URL del Secret (Asegúrate de haber puesto el puerto 6543 como hablamos antes)
db_url = st.secrets["connections"]["postgresql"]["url"]

# Creamos el motor de base de datos
engine = create_engine(db_url)

try:
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1"))
        st.success("✅ ¡CONECTADO A SUPABASE!")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
