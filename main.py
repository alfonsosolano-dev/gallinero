import streamlit as st
import pandas as pd
import sqlite3

# --- CONEXIÓN ---
conn = sqlite3.connect('corral_v42_final.db', check_same_thread=False)
c = conn.cursor()

# Función para cargar datos de forma segura
def cargar_seguro(tabla):
    try:
        df = pd.read_sql(f"SELECT * FROM {tabla} ORDER BY id DESC", conn)
        if 'raza' in df.columns: df['raza'] = df['raza'].fillna("General")
        return df
    except:
        return pd.DataFrame()

menu = st.sidebar.radio("PANEL", ["💸 GASTOS", "💰 VENTAS", "🛠️ ADMINISTRACIÓN", "📊 RESUMEN"])

# --- 1. SECCIÓN GASTOS (CORREGIDA) ---
if menu == "💸 GASTOS":
    st.title("💸 Registro de Gastos")
    st.subheader("Añadir nuevo gasto")
    
    # Formulario para anotar
    with st.form("form_gastos", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f = col1.date_input("Fecha")
        cat = col2.selectbox("Categoría", ["Pienso", "Material/Equipamiento", "Animales", "Salud", "Otros"])
        
        # Obtenemos razas existentes para asignar el gasto
        df_l = cargar_seguro('lotes')
        razas_disponibles = ["General"] + (df_l['raza'].unique().tolist() if not df_l.empty else [])
        rz = st.selectbox("Asignar a Raza", razas_disponibles)
        
        con = st.text_input("Concepto (Ej: Saco de pienso 25kg)")
        imp = st.number_input("Importe (€)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("✅ GUARDAR GASTO"):
            c.execute("INSERT INTO gastos (fecha, concepto, importe, categoria, raza) VALUES (?,?,?,?,?)",
                      (f.strftime('%d/%m/%Y'), con, imp, cat, rz))
            conn.commit()
            st.success("Gasto guardado correctamente.")
            st.rerun()

    st.divider()
    st.subheader("📜 Historial de Gastos")
    df_gastos = cargar_seguro('gastos')
    if not df_gastos.empty:
        st.dataframe(df_gastos, use_container_width=True)
    else:
        st.info("Aún no hay gastos registrados. Usa el formulario de arriba.")

# --- 2. SECCIÓN VENTAS (CORREGIDA) ---
elif menu == "💰 VENTAS":
    st.title("💰 Registro de Ventas")
    st.subheader("Anotar nueva venta")
    
    with st.form("form_ventas", clear_on_submit=True):
        col1, col2 = st.columns(2)
        f_v = col1.date_input("Fecha Venta")
        df_l = cargar_seguro('lotes')
        razas_v = ["General"] + (df_l['raza'].unique().tolist() if not df_l.empty else [])
        rz_v = col2.selectbox("Raza del producto", razas_v)
        
        pro = st.selectbox("Producto", ["Huevos", "Pollo Vivo", "Canal/Carne", "Otros"])
        can = st.number_input("Cantidad", min_value=1)
        tot = st.number_input("Total Cobrado (€)", min_value=0.0, step=0.1)
        
        if st.form_submit_button("✅ REGISTRAR VENTA"):
            c.execute("INSERT INTO ventas (fecha, producto, cantidad, total, raza) VALUES (?,?,?,?,?)",
                      (f_v.strftime('%d/%m/%Y'), pro, can, tot, rz_v))
            conn.commit()
            st.success("Venta registrada.")
            st.rerun()

    st.divider()
    st.subheader("📜 Historial de Ventas")
    df_ventas = cargar_seguro('ventas')
    if not df_ventas.empty:
        st.dataframe(df_ventas, use_container_width=True)
    else:
        st.info("No hay ventas registradas todavía.")

# --- 3. SECCIÓN ADMINISTRACIÓN (CORREGIDA) ---
elif menu == "🛠️ ADMINISTRACIÓN":
    st.title("🛠️ Gestión de Datos (Borrar/Editar)")
    
    tabla_sel = st.selectbox("Selecciona la tabla que quieres gestionar", ["lotes", "gastos", "ventas", "produccion"])
    df_admin = cargar_seguro(tabla_sel)
    
    if not df_admin.empty:
        st.write(f"Datos actuales en la tabla **{tabla_sel}**:")
        st.dataframe(df_admin, use_container_width=True)
        
        st.warning("Acción de borrado:")
        id_a_borrar = st.number_input("Introduce el ID del registro que quieres eliminar", min_value=int(df_admin['id'].min()), max_value=int(df_admin['id'].max()))
        
        if st.button("🗑️ ELIMINAR REGISTRO"):
            c.execute(f"DELETE FROM {tabla_sel} WHERE id = ?", (id_a_borrar,))
            conn.commit()
            st.success(f"Registro {id_a_borrar} eliminado de {tabla_sel}.")
            st.rerun()
    else:
        st.info(f"La tabla {tabla_sel} está vacía.")
