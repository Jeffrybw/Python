# streamlit run Form_Identificacion.py

import streamlit as st
import pandas as pd
from datetime import datetime, date
import form_engine as engine

# Configuración de la página
st.set_page_config(page_title="Identificación", page_icon="👤")
st.title("👤 Registro de Stakeholders")

# --- 0. MANEJO DE ESTADO ---
if "registro_exitoso" not in st.session_state:
    st.session_state.registro_exitoso = False

if st.session_state.registro_exitoso:
    st.success("✅ ¡Stakeholder registrado con éxito!")
    st.session_state.registro_exitoso = False

# --- 1. CARGA DE DATOS ---
@st.cache_data
def load_config():
    # Carga configuración del formulario
    try:
        df = pd.read_csv("csv_form_identificacion.csv")
        df.columns = df.columns.str.strip().str.lower()
        return df
    except FileNotFoundError:
        st.error("No se encontró el archivo 'csv_form_identificacion.csv'.")
        st.stop()

@st.cache_data
def load_geodata():
    # Carga base de datos de Ubigeo
    try:
        # Forzamos tipo string para evitar pérdida de ceros a la izquierda
        df = pd.read_csv("geodir-ubigeo-inei.csv", dtype=str)
        df.columns = df.columns.str.strip()
        return df
    except FileNotFoundError:
        st.error("No se encontró el archivo 'geodir-ubigeo-inei.csv'.")
        st.stop()

try:
    estructura = load_config()
    geodatos = load_geodata()
except Exception as e:
    st.error(f"Error cargando archivos de configuración: {e}")
    st.stop()

respuestas = {}
edad_temporal = 0

# --- 2. GENERACIÓN DEL FORMULARIO ---
lista_categorias = estructura["categoría"].unique()

for cat in lista_categorias:
    st.markdown(f"### {cat}")
    subset = estructura[estructura["categoría"] == cat]
    
    # --- LÓGICA ESPECIAL: DATOS PERSONALES ---
    if cat == "Datos Personales":
        for idx, row in subset.iterrows():
            pregunta_limpia = row["pregunta"].strip()
            
            if "fecha de nacimiento" in pregunta_limpia.lower():
                fecha_nac = st.date_input(
                    pregunta_limpia,
                    value=None,
                    min_value=date(1920, 1, 1),
                    max_value=date.today(),
                    key=f"fecha_nac_{idx}" 
                )
                respuestas[pregunta_limpia] = fecha_nac.strftime("%d/%m/%Y") if fecha_nac else ""
                
                # Cálculo de edad en tiempo real
                if fecha_nac:
                    hoy = date.today()
                    edad_temporal = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
                else:
                    edad_temporal = 0

            elif "edad" in pregunta_limpia.lower():
                st.number_input(
                    pregunta_limpia, 
                    value=edad_temporal, 
                    disabled=True, 
                    key=f"edad_auto_{idx}"
                )
                respuestas[pregunta_limpia] = edad_temporal

            else:
                engine.render_field(row, respuestas)

    # --- LÓGICA ESPECIAL: DOMICILIO (CASCADA) ---
    elif "Domicilio" in cat: 
        col1, col2, col3 = st.columns(3)
        
        # Departamento
        deps = sorted(geodatos["Departamento"].dropna().unique())
        dep_sel = col1.selectbox("Departamento", deps, index=None, key="geo_dep")
        respuestas["Departamento:"] = dep_sel
        
        # Provincia
        provs = []
        if dep_sel:
            provs = sorted(geodatos[geodatos["Departamento"] == dep_sel]["Provincia"].dropna().unique())
        prov_sel = col2.selectbox("Provincia", provs, index=None, key="geo_prov", disabled=not dep_sel)
        respuestas["Provincia:"] = prov_sel
        
        # Distrito
        dists = []
        if prov_sel:
            dists = sorted(geodatos[(geodatos["Departamento"] == dep_sel) & (geodatos["Provincia"] == prov_sel)]["Distrito"].dropna().unique())
        dist_sel = col3.selectbox("Distrito", dists, index=None, key="geo_dist", disabled=not prov_sel)
        respuestas["Distrito:"] = dist_sel

        # Renderizamos el resto de preguntas de Domicilio que NO son geo
        geo_preguntas = ["Departamento:", "Provincia:", "Distrito:"]
        # Filtramos ignorando mayúsculas/minúsculas y espacios
        subset_restante = subset[~subset["pregunta"].str.strip().isin(geo_preguntas)]
        
        for idx, row in subset_restante.iterrows():
            engine.render_field(row, respuestas)

    # --- ESTÁNDAR (RESTO DE CATEGORÍAS) ---
    else:
        for idx, row in subset.iterrows():
            engine.render_field(row, respuestas)

st.markdown("---")

# --- 3. LÓGICA DE VALIDACIÓN Y ENVÍO ---
if st.button("💾 Guardar Registro", type="primary"):
    
    errores = []
    
    # A. Validación Geográfica (Solo si existe la categoría Domicilio)
    if any("Domicilio" in c for c in lista_categorias):
        if not respuestas.get("Departamento:") and not respuestas.get("Departamento"): 
             errores.append("Falta seleccionar Departamento.")
        if not respuestas.get("Provincia:") and not respuestas.get("Provincia"):
             errores.append("Falta seleccionar Provincia.")
    
    # B. Validación de Nombres (Dinámica)
    keys_nombres = [k for k in respuestas.keys() if "Nombre" in k or "Nombres" in k]
    keys_apellidos = [k for k in respuestas.keys() if "Apellido" in k or "Paterno" in k]
    
    if keys_nombres and not any(respuestas[k] for k in keys_nombres):
         errores.append("Falta completar el Nombre.")
    
    if keys_apellidos and not any(respuestas[k] for k in keys_apellidos):
         errores.append("Falta completar el Apellido Paterno.")

    # PASO 2: DECISIÓN
    if errores:
        for err in errores:
            st.error(f"⚠️ {err}")
    else:
        with st.spinner("Enviando a Google Sheets..."):
            try:
                respuestas["Fecha_Registro"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                df_save = pd.DataFrame([respuestas])
                
                sheet = engine.connect_gsheet("Clima_Social_Database")
                engine.append_to_sheet(sheet, "Identificacion", df_save)
                
                # PASO 3: LIMPIEZA SEGURA
                # Identificamos llaves a borrar evitando borrar 'registro_exitoso'
                # Usamos list() para evitar error por modificación durante iteración
                keys_a_borrar = [k for k in st.session_state.keys() if k != "registro_exitoso"]
                for key in keys_a_borrar:
                    del st.session_state[key]
                
                st.session_state.registro_exitoso = True
                st.rerun()
                
            except Exception as e:
                st.error(f"Ocurrió un error técnico al guardar: {e}")