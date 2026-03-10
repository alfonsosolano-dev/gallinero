import streamlit as st
from sqlalchemy import create_engine, text

st.title("🚜 Intento Final: Puerto Estándar + IP")

# Recuperamos la URL de los secrets
db_url = st.secrets["connections"]["postgresql"]["url"]

# Configuramos el motor con más tiempo de espera
engine = create_engine(
    db_url, 
    connect_args={
        "connect_timeout": 30  # Le damos 30 segundos para conectar
    }
)

try:
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1"))
        st.success("✅ ¡CONEXIÓN ESTABLECIDA!")
        st.balloons()
        
        # Si conecta, mostramos que estamos listos
        st.info("Ya puedes volver a poner el código completo del corral.")
except Exception as e:
    st.error(f"❌ Error con Puerto 5432: {e}")
    st.warning("Si esto falla, el servidor de Streamlit tiene bloqueada la salida a bases de datos externas.")
