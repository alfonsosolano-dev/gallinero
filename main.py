import streamlit as st
from sqlalchemy import create_engine, text

st.title("🚜 Intento de Conexión por IP Directa")

# Recuperamos la URL con la IP
db_url = st.secrets["connections"]["postgresql"]["url"]

# Creamos el motor forzando IPv4 y tiempos de espera cortos
engine = create_engine(
    db_url, 
    connect_args={
        "connect_timeout": 10,
        "sslmode": "prefer"
    }
)

try:
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1"))
        st.success("✅ ¡CONECTADO POR FIN!")
        st.balloons()
except Exception as e:
    st.error(f"❌ Error con IP: {e}")
    st.info("Si esto falla, el firewall de Streamlit está bloqueando la salida al puerto 6543.")
