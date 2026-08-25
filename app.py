import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

st.set_page_config(
    page_title="Verificador de Estatus y Captura",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Verificador de Estatus y Captura (Pestaña CRUCE)")

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
                    
                    estatus_celda = str(fila_data.get("ESTATUS", "")).strip()
                    estatus_upper = estatus_celda.upper()
                    folio_val = str(fila_data.get("FOLIO", "")).strip()
                    
                    st.divider()
                    
                    # VALIDACIÓN: Permite capturar si la columna G está en blanco O si dice "NO CAPTURADO"
                    esta_vacia = (estatus_celda == "") or (estatus_celda.lower() in ["none", "nan", "null"])
                    es_no_capturado = "NO CAPTURADO" in estatus_upper
                    
                    permite_capturar = esta_vacia or es_no_capturado
                    
                    if permite_capturar:
                        # ---------------------------------------------------------
                        # CASO 1: EN BLANCO O "NO CAPTURADO" -> PERMITE CAPTURAR
                        # ---------------------------------------------------------
                        st.warning("⚠️ **REGISTRO DISPONIBLE PARA CAPTURAR**")
                        
                        st.markdown(f"**Nombre:** {nombre_completo}")
                        st.markdown(f"**Programa:** {fila_data.get('PROGAMA', fila_data.get('OGAMA', ''))} | **ID:** {fila_data.get('ID', '')}")
                        st.markdown(f"**Estatus actual en columna G:** `{estatus_celda if estatus_celda else 'VACÍO'}`")
                        
                        st.divider()
                        
                        col_input, col_btn = st.columns([2, 1])
                        with col_input:
                            nuevo_folio = st.text_input("Ingresa Folio a asignar:", key=f"input_folio_{idx_fila}").strip()
                        
                        with col_btn:
                            st.write("")
                            st.write("")
                            btn_capturar = st.button("✅ CAPTURAR", use_container_width=True, key=f"btn_{idx_fila}")
                            
                        if btn_capturar:
                            num_fila_sheets = idx_fila + 2
                            
                            # Escribe "✓ Capturado" en la Columna 7 (G)
                            ws.update_cell(num_fila_sheets, 7, "✓ Capturado")
                            
                            # Guarda el Folio en la Columna 8 (H) si se ingresó uno
                            if nuevo_folio:
                                ws.update_cell(num_fila_sheets, 8, nuevo_folio)
                                
                            st.success(f"¡Se actualizó la fila {num_fila_sheets} a '✓ Capturado' correctamente!")
                            st.rerun()
                            
                    else:
                        # ---------------------------------------------------------
                        # CASO 2: YA TIENE "CAPTURADO" -> ZONAS PRIORITARIAS BENITO JUÁREZ
                        # ---------------------------------------------------------
                        st.info("ℹ️ **EL REGISTRO YA SE ENCUENTRA CAPTURADO**")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("CURP", curp_busqueda)
                        col2.metric("Nombre", nombre_completo)
                        col3.metric("Estatus (Columna G)", estatus_celda)
                        col4.metric("Folio (Columna H)", folio_val if folio_val else "Sin Folio")
                        
                        st.divider()
                        st.subheader("📍 Zonas Prioritarias de Benito Juárez")
                        
                        zonas_bj = pd.DataFrame({
                            "Zona / Sector": ["Sector 1", "Sector 2", "Sector 3", "Sector 4", "Sector 5"],
                            "Colonias Prioritarias": [
                                "Portales Norte, Portales Sur, Portales Oriente",
                                "Alamos, Narvarte Poniente, Narvarte Oriente",
                                "Del Valle Centro, Del Valle Sur, Del Valle Norte",
                                "Mixcoac, Insurgentes Mixcoac, Actipan",
                                "San José Insurgentes, Crédito Constructor, Nápoles"
                            ]
                        })
                        st.table(zonas_bj)
                        
                else:
                    st.error(f"❌ La CURP **{curp_busqueda}** no existe en la pestaña CRUCE.")
                    
    except Exception as e:
        st.error(f"Error al leer/escribir en Google Sheets: {e}")
