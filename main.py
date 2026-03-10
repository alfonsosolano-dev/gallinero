import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text

st.title("🚜 Prueba de Conexión Suprema")

# Obtenemos la URL de los secrets
db_url = st.secrets["connections"]["postgresql"]["url"]

# Crear el motor de conexión manualmente
engine = create_engine(db_url)

try:
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1"))
        st.success("✅ ¡CONECTADO A SUPABASE!")
        
        # Crear tabla de prueba
        conn.execute(text("CREATE TABLE IF NOT EXISTS prueba (id SERIAL PRIMARY KEY, nombre TEXT)"))
        conn.commit()
        st.info("Tabla de prueba creada con éxito.")
        
except Exception as e:
    st.error(f"❌ Sigue fallando. Error: {e}")
    st.info("Intentando modo alternativo...")
