# --- Antes de inicializar la DB ---
def inicializar_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, especie TEXT, raza TEXT,
        tipo_engorde TEXT, cantidad INTEGER, precio_ud REAL, estado TEXT, edad_inicial INTEGER DEFAULT 0, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS produccion (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, raza TEXT, cantidad REAL,
        especie TEXT, usuario TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS puesta_manual (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lote_id INTEGER, fecha_primera_puesta TEXT, usuario TEXT)''')
    # resto de tablas...
    conn.commit()
    conn.close()

# --- En PUESTA ---
elif menu == "🥚 PUESTA":
    st.title("🥚 Registro de Puesta")
    df_l = cargar('lotes')
    razas = df_l['raza'].unique().tolist() if not df_l.empty else ["Roja", "Blanca"]
    
    # Selección de lote y primera puesta
    with st.form("fp"):
        lote_sel = st.selectbox("Seleccionar Lote", df_l['id'].tolist() if not df_l.empty else [0])
        df_puesta = cargar('puesta_manual')
        f1 = None
        if not df_puesta.empty and lote_sel in df_puesta['lote_id'].values:
            f1 = df_puesta[df_puesta['lote_id']==lote_sel]['fecha_primera_puesta'].values[0]
            st.info(f"Fecha primera puesta registrada: {f1}")
        else:
            f1 = st.date_input("Fecha primera puesta")
        
        can = st.number_input("Cantidad de Huevos", min_value=1)
        if st.form_submit_button("Guardar"):
            conn = get_conn(); c = conn.cursor()
            raza = df_l[df_l['id']==lote_sel]['raza'].values[0]
            especie = df_l[df_l['id']==lote_sel]['especie'].values[0]
            # Guardar producción diaria
            c.execute("INSERT INTO produccion (fecha, raza, cantidad, especie, usuario) VALUES (?,?,?,?,?)",
                      (datetime.now().strftime('%d/%m/%Y'), raza, can, especie, st.session_state['usuario']))
            # Guardar primera puesta si no existe
            if not df_puesta.empty and lote_sel in df_puesta['lote_id'].values:
                pass  # ya registrada
            else:
                c.execute("INSERT INTO puesta_manual (lote_id, fecha_primera_puesta, usuario) VALUES (?,?,?)",
                          (lote_sel, f1.strftime('%d/%m/%Y'), st.session_state['usuario']))
            conn.commit(); conn.close()
            st.success("✅ Puesta registrada"); st.rerun()

# --- En CRECIMIENTO ---
elif menu == "📈 CRECIMIENTO":
    st.title("📈 Control de Madurez y Puesta")
    df_l = cargar('lotes')
    df_puesta = cargar('puesta_manual')
    if not df_l.empty:
        for _, r in df_l[df_l['estado']=='Activo'].iterrows():
            f_e = datetime.strptime(r['fecha'], '%d/%m/%Y')
            edad = (datetime.now() - f_e).days + int(r['edad_inicial'])
            info = f"🔹 {r['especie']} {r['raza']} - {edad} días"
            # Mostrar fecha de primera puesta si existe
            if not df_puesta.empty and r['id'] in df_puesta['lote_id'].values:
                f1 = df_puesta[df_puesta['lote_id']==r['id']]['fecha_primera_puesta'].values[0]
                info += f" | Primera puesta: {f1}"
            st.write(info)
            st.progress(min(1.0, edad/120))
