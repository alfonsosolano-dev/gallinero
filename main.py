import streamlit as st
import pandas as pd
import sqlite3
import io # Para manejar el archivo Excel en memoria
from datetime import datetime

# --- CONFIGURACIÓN ---
conn = sqlite3.connect('corral_v46_final.db', check_same_thread=False)
c = conn.cursor()

def cargar(tabla):
    try: return pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
    except: return pd.DataFrame()

# --- (Mantén el resto del código igual hasta la pestaña ADMIN) ---

# --- SECCIÓN: ADMIN (ACTUALIZADA CON EXCEL) ---
elif menu == "🛠️ ADMIN":
    st.title("🛠️ Gestión y Copia de Seguridad")
    
    # --- BOTÓN DE EXPORTACIÓN ---
    st.subheader("📥 Exportar mis Datos")
    if st.button("Generar Archivo Excel"):
        output = io.BytesIO()
        # Creamos el Excel con varias pestañas
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            cargar('lotes').to_excel(writer, sheet_name='Animales', index=False)
            cargar('gastos').to_excel(writer, sheet_name='Gastos', index=False)
            cargar('ventas').to_excel(writer, sheet_name='Ventas', index=False)
            cargar('produccion').to_excel(writer, sheet_name='Huevos', index=False)
        
        st.download_button(
            label="⬇️ Descargar Excel del Corral",
            data=output.getvalue(),
            file_name=f"Corral_Backup_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.divider()
    # --- BORRADO DE DATOS ---
    t = st.selectbox("Selecciona tabla para corregir errores", ["lotes", "gastos", "ventas", "produccion"])
    df_admin = cargar(t)
    if not df_admin.empty:
        st.dataframe(df_admin)
        id_del = st.number_input("ID a eliminar", min_value=0)
        if st.button("🗑️ BORRAR REGISTRO"):
            c.execute(f"DELETE FROM {t} WHERE id=?", (id_del,))
            conn.commit(); st.rerun()
