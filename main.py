import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

st.title("🚜 Prueba de Conexión Final")

# Recuperamos la URL limpia de los secrets
db_url = st.secrets["connections"]["postgresql"]["url"]

# Creamos el motor con una configuración más sencilla
engine = create_engine(db_url, connect_args={"connect_timeout": 10})

try:
    with engine.connect() as conn:
        # Intentamos una consulta simple
        res = conn.execute(text("SELECT 1"))
        st.success("✅ ¡CONEXIÓN ESTABLECIDA CON SUPABASE!")
        
        # Verificamos si podemos crear una tabla
        conn.execute(text("CREATE TABLE IF NOT EXISTS test_conexion (id SERIAL PRIMARY KEY)"))
        conn.commit()
        st.info("Estructura de base de datos verificada correctamente.")
        
except Exception as e:
    st.error(f"❌ Error detallado: {e}")
