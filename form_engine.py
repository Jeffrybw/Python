import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def get_gsheets_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    
    # Leemos los secretos
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # CORRECCIÓN DE LLAVE: Aseguramos el formato correcto de la llave privada
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    # Autenticación
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def connect_gsheet(sheet_name: str):
    """Conecta al libro de Google Sheets."""
    client = get_gsheets_client()
    return client.open(sheet_name)

def ensure_sheet(sheet, tab_name: str):
    """Verifica si la pestaña existe, si no, la crea."""
    try:
        return sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        # Crea la hoja si no existe con dimensiones por defecto
        return sheet.add_worksheet(title=tab_name, rows="1000", cols="26")

def append_to_sheet(sheet, tab_name: str, df: pd.DataFrame):
    """Agrega datos al final de la hoja de forma optimizada."""
    ws = ensure_sheet(sheet, tab_name)
    datos = df.fillna("").astype(str).values.tolist()
    
    # OPTIMIZACIÓN: Verificamos solo la primera fila en lugar de toda la hoja
    # para decidir si escribimos encabezados.
    first_row = ws.row_values(1)
    
    if not first_row:
        # Si está vacía, agregamos primero las columnas
        ws.append_row(df.columns.tolist())
    
    ws.append_rows(datos)

# --- LECTURA DE DATOS ---
@st.cache_data(ttl=60)
def read_sheet_data(sheet_name: str, tab_name: str) -> pd.DataFrame:
    """Lee datos de la hoja con caché de 60 segundos."""
    try:
        sheet = connect_gsheet(sheet_name)
        ws = ensure_sheet(sheet, tab_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        # Retorna DataFrame vacío en caso de error o hoja vacía
        return pd.DataFrame()

# --- RENDERIZADOR DE CAMPOS ---
def render_field(row, respuestas_dict, geodatos=None):
    """Renderiza un campo de Streamlit basado en la configuración del CSV."""
    tipo = row.get('tipo', '')
    pregunta = row.get('pregunta', '').strip()
    
    if not tipo or not pregunta:
        return 

    raw_opciones = row.get('opciones', '')
    opciones = str(raw_opciones).split(',') if pd.notna(raw_opciones) else []
    opciones = [o.strip() for o in opciones if o.strip() != '']

    # Clave única para el widget
    key = f"{row.name}_{pregunta}" 

    if "text_input" in tipo:
        respuestas_dict[pregunta] = st.text_input(pregunta, key=key)
    elif "selectbox" in tipo:
        respuestas_dict[pregunta] = st.selectbox(pregunta, opciones, index=None, placeholder="Seleccione...", key=key)
    elif "multiselect" in tipo:
        val = st.multiselect(pregunta, opciones, key=key)
        respuestas_dict[pregunta] = ", ".join(val)
    elif "date_input" in tipo:
        val = st.date_input(pregunta, value=None, key=key)
        respuestas_dict[pregunta] = val.strftime("%d/%m/%Y") if val else ""
    elif "text_area" in tipo:
        respuestas_dict[pregunta] = st.text_area(pregunta, key=key)
    elif "number_input" in tipo:
        respuestas_dict[pregunta] = st.number_input(pregunta, step=1, min_value=0, key=key)