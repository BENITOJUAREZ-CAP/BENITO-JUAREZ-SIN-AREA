import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

st.set_page_config(
    page_title="Sistema de Captura y Verificación",
    page_icon="📋",
    layout="wide"
)

SPREADSHEET_ID = "1gzkpEijOVCOUqDjkNlyAQRIGpyqH_2j1H4rWGe2NTgM"
NOMBRE_HOJA = "CRUCE"

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def obtener_cliente_gspread():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
            return gspread.authorize(creds)
        st.error("No se encontraron credenciales en los Secrets de Streamlit.")
        return None
    except Exception as e:
        st.error(f"Error de autenticación: {e}")
        return None

gc = obtener_cliente_gspread()

st.title("📋 Verificador de Estatus y Captura (Pestaña CRUCE)")

if gc:
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(NOMBRE_HOJA)
        
        # Cargar todos los datos de la hoja
        datos = ws.get_all_values()
        
        if datos:
            headers = [str(h).strip().upper() for h in datos[0]]
            
            # Crear DataFrame y guardar la fila real de Google Sheets para evitar desfases
            df = pd.DataFrame(datos[1:], columns=headers)
            df["FILA_SHEETS"] = range(2, len(df) + 2)  # La fila 1 son los encabezados
            
            # Limpieza para búsqueda exacta por CURP
            df["CURP_CLEAN"] = df["CURP"].astype(str).str.strip().str.upper()
            
            curp_input = st.text_input("🔑 Escanea o ingresa la CURP:", placeholder="Ej. PARL420507MDFTDR06").strip().upper()
            
            if curp_input:
                registro = df[df["CURP_CLEAN"] == curp_input]
                
                if not registro.empty:
                    fila_info = registro.iloc[0]
                    num_fila = int(fila_info["FILA_SHEETS"])
                    
                    nombre = f"{fila_info.get('NOMBRE', '')} {fila_info.get('APELLIDO 1', '')} {fila_info.get('APELLIDO 2', '')}".strip()
                    estatus_actual = str(fila_info.get("ESTATUS", "")).strip()
                    folio_actual = str(fila_info.get("FOLIO", "")).strip()
                    id_registro = fila_info.get("ID", "")
                    programa = fila_info.get("PROGAMA", fila_info.get("PROGRAMA", ""))
                    
                    st.divider()
                    
                    # Evalúa si requiere captura: si la celda está vacía o contiene "NO CAPTURADO"
                    necesita_captura = (estatus_actual == "") or ("NO CAPTURADO" in estatus_actual.upper())
                    
                    if necesita_captura:
                        # -------------------------------------------------------------
                        # OPCIÓN A: EN BLANCO / NO CAPTURADO -> OPCIÓN DE CAPTURA
                        # -------------------------------------------------------------
                        st.subheader("🟢 Registro Disponible para Captura")
                        
                        col_info, col_form = st.columns([1, 1], gap="large")
                        
                        with col_info:
                            st.markdown("### Datos del Beneficiario")
                            st.write(f"**Nombre:** {nombre}")
                            st.write(f"**CURP:** {curp_input}")
                            st.write(f"**ID:** {id_registro}")
                            st.write(f"**Programa:** {programa}")
                            st.write(f"**Estatus actual en Columna G:** `{estatus_actual if estatus_actual else 'Vacío'}`")
                        
                        with col_form:
                            st.markdown("### Capturar Folio")
                            with st.form(key=f"form_captura_{num_fila}"):
                                folio_nuevo = st.text_input("Folio a asignar (opcional):", key="input_folio").strip()
                                submit = st.form_submit_button("✅ REGISTRAR Y MARCAR CAPTURADO", use_container_width=True)
                                
                                if submit:
                                    try:
                                        # Escribe directo en la fila real de Google Sheets (G=7, H=8)
                                        ws.update_cell(num_fila, 7, "✓ Capturado")
                                        if folio_nuevo:
                                            ws.update_cell(num_fila, 8, folio_nuevo)
                                        
                                        st.success(f"¡Se actualizó con éxito la fila {num_fila} en la hoja de cálculo!")
                                        st.cache_data.clear()
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Error al escribir en Google Sheets: {err}")
                    else:
                        # -------------------------------------------------------------
                        # OPCIÓN B: YA CAPTURADO -> CONSULTA Y ZONAS PRIORITARIAS
                        # -------------------------------------------------------------
                        st.subheader("🔵 Registro Ya Capturado")
                        
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("CURP", curp_input)
                        c2.metric("Nombre", nombre)
                        c3.metric("Estatus (G)", estatus_actual)
                        c4.metric("Folio Asignado (H)", folio_actual if folio_actual else "Sin Folio")
                        
                        st.divider()
                        st.subheader("📍 Zonas Prioritarias de Benito Juárez")
                        
                        zonas_bj = pd.DataFrame({
                            "Sector": ["Sector 1", "Sector 2", "Sector 3", "Sector 4", "Sector 5"],
                            "Colonias Cobertura": [
                                "Portales Norte, Portales Sur, Portales Oriente",
                                "Alamos, Narvarte Poniente, Narvarte Oriente",
                                "Del Valle Centro, Del Valle Sur, Del Valle Norte",
                                "Mixcoac, Insurgentes Mixcoac, Actipan",
                                "San José Insurgentes, Crédito Constructor, Nápoles"
                            ]
                        })
                        st.dataframe(zonas_bj, use_container_width=True, hide_index=True)
                else:
                    st.error(f"❌ La CURP '{curp_input}' no se encuentra en la pestaña CRUCE.")
    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
