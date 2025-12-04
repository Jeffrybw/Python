import streamlit as st
import pandas as pd
from datetime import datetime
import form_engine as engine

st.set_page_config(page_title="Interacciones", page_icon="🤝")
st.title("🤝 Registro de Interacciones")

# --- 1. CARGA DE CONFIGURACIÓN ---
try:
    estructura = pd.read_csv("csv_form_interacciones.csv")
    # CORRECCIÓN CRÍTICA: Normalizamos encabezados a minúsculas
    # Esto asegura compatibilidad con form_engine.render_field que busca 'tipo' y 'pregunta'
    estructura.columns = estructura.columns.str.strip().str.lower()
except FileNotFoundError:
    st.error("No se encuentra el archivo 'csv_form_interacciones.csv'")
    st.stop()

respuestas = {}

# --- 2. CARGAR STAKEHOLDERS DESDE SHEETS ---
st.info("Sincronizando lista de stakeholders...")

# PROTECCIÓN DE MEMORIA: Usamos .copy() para no mutar el caché original
df_stk_raw = engine.read_sheet_data("Clima_Social_Database", "Identificacion")
df_stk = df_stk_raw.copy() if not df_stk_raw.empty else pd.DataFrame()

lista_opciones_stk = []

if not df_stk.empty:
    # Normalizamos columnas a minúsculas para búsqueda robusta
    cols_lower = df_stk.columns.str.lower()
    
    # Buscamos columnas de Nombre y Apellido
    col_nombres = [c for c in df_stk.columns if "nombres" in c.lower()]
    col_paterno = [c for c in df_stk.columns if "paterno" in c.lower()]
    
    if col_nombres:
        nombre_col = col_nombres[0]
        paterno_col = col_paterno[0] if col_paterno else None
        
        # Construcción del nombre completo para el dropdown
        if paterno_col:
            df_stk["_display_name"] = df_stk[nombre_col].astype(str) + " " + df_stk[paterno_col].astype(str)
        else:
            df_stk["_display_name"] = df_stk[nombre_col].astype(str)
            
        lista_opciones_stk = df_stk["_display_name"].unique().tolist()
    else:
        # Fallback si no encuentra columnas claras
        lista_opciones_stk = df_stk.iloc[:, 0].astype(str).tolist()

# --- 3. GENERAR FORMULARIO ---
with st.form("form_interacciones"):
    # Iteramos usando la columna en minúscula 'categoría'
    for categoria in estructura["categoría"].unique():
        st.markdown(f"### {categoria}")
        subset = estructura[estructura["categoría"] == categoria]
        
        for idx, row in subset.iterrows():
            # Accedemos a la columna en minúscula 'pregunta'
            pregunta = row["pregunta"].strip()
            
            # Interceptamos la pregunta del nombre para inyectar la lista dinámica
            # Usamos .lower() en la comparación para ser menos estrictos con el CSV
            if "nombre y apellido del stk" in pregunta.lower():
                respuestas[pregunta] = st.selectbox(
                    pregunta, 
                    options=lista_opciones_stk,
                    index=None,
                    placeholder="Busque el nombre..."
                )
            else:
                # Ahora 'row' tiene claves en minúscula (tipo, pregunta, opciones),
                # por lo que render_field funcionará correctamente.
                engine.render_field(row, respuestas)

    # Botón de envío
    submitted = st.form_submit_button("💾 Guardar Interacción")
    
    if submitted:
        # Validación básica: Buscamos si se llenó el campo de Stakeholder
        found_key = next((k for k in respuestas if "nombre y apellido del stk" in k.lower()), None)
        
        if not found_key or not respuestas.get(found_key):
            st.error("⚠️ Debe seleccionar un Stakeholder.")
        else:
            with st.spinner("Guardando en Google Sheets..."):
                try:
                    respuestas["Fecha_Registro"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df_save = pd.DataFrame([respuestas])
                    
                    sheet = engine.connect_gsheet("Clima_Social_Database")
                    # Nos aseguramos que la hoja destino exista o se cree
                    engine.append_to_sheet(sheet, "Interacciones", df_save)
                    
                    st.success("✅ Interacción registrada correctamente!")
                    
                    # Opcional: Reiniciar el script para limpiar el formulario
                    # st.rerun() 
                    
                except Exception as e:
                    st.error(f"Error al guardar: {e}")