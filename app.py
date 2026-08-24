import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Configuración de la página
st.set_page_config(
    page_title="Verificador de Estatus y Captura",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Verificador de Estatus y Captura (Pestaña CRUCE)")

# ID extraído de tu enlace
SPREADSHEET_ID = "1gzkpEijOVCOUqDjkNlyAQRIGpyqH_2j1H4rWGe2NTgM"
NOMBRE_HOJA = "CRUCE"

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def conectar_sheets():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
            client = gspread.authorize(creds)
            return client
        else:
            st.error("No se encontraron las credenciales en los Secrets de Streamlit.")
            return None
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        return None

gc = conectar_sheets()

if gc:
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(NOMBRE_HOJA)
        
        datos = ws.get_all_values()
        
        if datos:
            headers = [str(h).strip() for h in datos[0]]
            df = pd.DataFrame(datos[1:], columns=headers)
            
            # Limpieza de la columna CURP para asegurar coincidencia
            df["CURP"] = df["CURP"].astype(str).str.strip().str.upper()
            
            curp_busqueda = st.text_input("🔑 Ingresa o escanea la CURP a consultar:").strip().upper()
            
            if curp_busqueda:
                coincidencias = df[df["CURP"] == curp_busqueda]
                
                if not coincidencias.empty:
                    idx_fila = coincidencias.index[0]
                    fila_data = coincidencias.iloc[0]
                    
                    nombre_completo = f"{fila_data.get('NOMBRE', '')} {fila_data.get('APELLIDO 1', '')} {fila_data.get('APELLIDO 2', '')}".strip()
                    estatus_actual = str(fila_data.get("ESTATUS", "")).strip()
                    folio_actual = str(fila_data.get("FOLIO", "")).strip()
                    
                    st.divider()
                    
                    # Evaluación del estatus en la columna G
                    if "CAPTURADO" in estatus_actual.upper():
                        st.success("✅ **YA ESTÁ CAPTURADO**")
                        
                        col1, col2, col3 = st.columns(3)
                        col1.metric("CURP", curp_busqueda)
                        col2.metric("Nombre", nombre_completo)
                        col3.metric("Folio Asignado", folio_actual if folio_actual else "Sin Folio")
                        
                    else:
                        st.warning("⚠️ **PENDIENTE POR CAPTURAR**")
                        st.info(f"**Persona:** {nombre_completo} | **Programa:** {fila_data.get('OGAMA', '')} | **ID:** {fila_data.get('ID', '')}")
                        
                        # Formulario de captura
                        with st.form("form_captura", clear_on_submit=True):
                            st.subheader("📝 Capturar Folio")
                            nuevo_folio = st.text_input("Ingresa el Folio a asignar:").strip()
                            btn_guardar = st.form_submit_button("💾 Guardar Captura")
                            
                            if btn_guardar:
                                if nuevo_folio:
                                    # Número de fila real en Sheets (Fila 1 = Encabezados)
                                    num_fila_sheets = idx_fila + 2
                                    
                                    # Columna 7 = G (ESTATUS), Columna 8 = H (FOLIO)
                                    ws.update_cell(num_fila_sheets, 7, "✓ Capturado")
                                    ws.update_cell(num_fila_sheets, 8, nuevo_folio)
                                    
                                    st.success(f"¡Se actualizó correctamente a '✓ Capturado' con Folio **{nuevo_folio}**!")
                                    st.rerun()
                                else:
                                    st.error("Debes ingresar un Folio para completar el registro.")
                else:
                    st.error(f"❌ La CURP **{curp_busqueda}** no existe en la pestaña CRUCE.")
                    
    except Exception as e:
        st.error(f"Error al abrir la hoja de cálculo: {e}")
