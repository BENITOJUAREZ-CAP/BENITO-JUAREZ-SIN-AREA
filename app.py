import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

st.set_page_config(
    page_title="Verificador de Estatus y Captura",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Verificador de Estatus y Captura")

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
        st.error(f"Error de conexión: {e}")
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
            
            df["CURP"] = df["CURP"].astype(str).str.strip().str.upper()
            
            curp_busqueda = st.text_input("🔑 Ingresa o escanea la CURP a consultar:").strip().upper()
            
            if curp_busqueda:
                coincidencias = df[df["CURP"] == curp_busqueda]
                
                if not coincidencias.empty:
                    idx_fila = coincidencias.index[0]
                    fila_data = coincidencias.iloc[0]
                    
                    nombre_completo = f"{fila_data.get('NOMBRE', '')} {fila_data.get('APELLIDO 1', '')} {fila_data.get('APELLIDO 2', '')}".strip()
                    estatus_val = str(fila_data.get("ESTATUS", "")).strip().upper()
                    folio_val = str(fila_data.get("FOLIO", "")).strip()
                    
                    st.divider()
                    
                    # Evalúa si la celda de la columna G contiene la palabra "CAPTURADO" y NO contiene "NO CAPTURADO"
                    ya_capturado = ("CAPTURADO" in estatus_val) and ("NO CAPTURADO" not in estatus_val)
                    
                    if ya_capturado:
                        # CASO 1: YA ESTÁ CAPTURADO (Solo lo muestra)
                        st.success("✅ **REGISTRO CAPTURADO**")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("CURP", curp_busqueda)
                        col2.metric("Nombre", nombre_completo)
                        col3.metric("Estatus Actual", fila_data.get("ESTATUS", "CAPTURADO"))
                        col4.metric("Folio", folio_val if folio_val else "Sin Folio")
                        
                    else:
                        # CASO 2: NO ESTÁ CAPTURADO (Lo muestra y habilita formulario para capturar)
                        st.warning("⚠️ **PENDIENTE POR CAPTURAR**")
                        
                        st.markdown(f"**Nombre:** {nombre_completo}")
                        st.markdown(f"**Programa:** {fila_data.get('OGAMA', '')} | **ID:** {fila_data.get('ID', '')}")
                        st.markdown(f"**Estatus actual en columna G:** `{fila_data.get('ESTATUS', 'Sin Estatus')}`")
                        
                        st.divider()
                        
                        with st.form("form_captura", clear_on_submit=True):
                            st.subheader("✍️ Marcar como Capturado")
                            nuevo_folio = st.text_input("Ingresa el Folio a asignar (opcional):").strip()
                            btn_guardar = st.form_submit_button("💾 Confirmar Captura")
                            
                            if btn_guardar:
                                num_fila_sheets = idx_fila + 2
                                
                                # Actualiza Columna G (ESTATUS = 7) y Columna H (FOLIO = 8)
                                ws.update_cell(num_fila_sheets, 7, "✓ Capturado")
                                ws.update_cell(num_fila_sheets, 8, nuevo_folio if nuevo_folio else "")
                                
                                st.success("¡Se ha actualizado la columna G a '✓ Capturado' exitosamente!")
                                st.rerun()
                else:
                    st.error(f"❌ La CURP **{curp_busqueda}** no se encuentra registrada en la hoja CRUCE.")
                    
    except Exception as e:
        st.error(f"Error al leer los datos de Google Sheets: {e}")
