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
            
            # Limpieza de la columna CURP para búsqueda exacta
            df["CURP"] = df["CURP"].astype(str).str.strip().str.upper()
            
            curp_busqueda = st.text_input("🔑 Ingresa o escanea la CURP a consultar:").strip().upper()
            
            if curp_busqueda:
                coincidencias = df[df["CURP"] == curp_busqueda]
                
                if not coincidencias.empty:
                    idx_fila = coincidencias.index[0]
                    fila_data = coincidencias.iloc[0]
                    
                    nombre_completo = f"{fila_data.get('NOMBRE', '')} {fila_data.get('APELLIDO 1', '')} {fila_data.get('APELLIDO 2', '')}".strip()
                    
                    # Obtenemos el texto de la columna G quitando espacios
                    estatus_celda = str(fila_data.get("ESTATUS", "")).strip()
                    folio_val = str(fila_data.get("FOLIO", "")).strip()
                    
                    st.divider()
                    
                    # VERIFICACIÓN: ¿La celda de la columna G está totalmente en blanco?
                    esta_en_blanco = (estatus_celda == "") or (estatus_celda.lower() in ["none", "nan", "null"])
                    
                    if esta_en_blanco:
                        # ---------------------------------------------------------
                        # PASO 1: COLUMNA G EN BLANCO -> OPCIÓN DE CAPTURAR
                        # ---------------------------------------------------------
                        st.warning("⚠️ **COLUMNA G EN BLANCO: OPCIÓN DE CAPTURA DISPONIBLE**")
                        
                        st.markdown(f"**Nombre:** {nombre_completo}")
                        st.markdown(f"**Programa:** {fila_data.get('PROGAMA', fila_data.get('OGAMA', ''))} | **ID:** {fila_data.get('ID', '')}")
                        
                        st.divider()
                        
                        col_input, col_btn = st.columns([2, 1])
                        with col_input:
                            nuevo_folio = st.text_input("Ingresa Folio a asignar:", key=f"input_folio_{idx_fila}").strip()
                        
                        with col_btn:
                            st.write("")
                            st.write("")
                            btn_capturar = st.button("✅ CAPTURAR", use_container_width=True, key=f"btn_{idx_fila}")
                            
                        if btn_capturar:
                            num_fila_sheets = idx_fila + 2  # Fila 1 = Encabezados
                            
                            # Actualiza Columna 7 (G) con "✓ Capturado"
                            ws.update_cell(num_fila_sheets, 7, "✓ Capturado")
                            
                            # Si ingresó folio, lo guarda en la Columna 8 (H)
                            if nuevo_folio:
                                ws.update_cell(num_fila_sheets, 8, nuevo_folio)
                                
                            st.success(f"¡Se capturó exitosamente en la fila {num_fila_sheets} de la pestaña CRUCE!")
                            st.rerun()
                            
                    else:
                        # ---------------------------------------------------------
                        # PASO 2: COLUMNA G NO ESTÁ EN BLANCO -> ZONAS PRIORITARIAS BENITO JUÁREZ
                        # ---------------------------------------------------------
                        st.info("ℹ️ **EL REGISTRO YA CONTIENE INFORMACIÓN EN LA COLUMNA G**")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("CURP", curp_busqueda)
                        col2.metric("Nombre", nombre_completo)
                        col3.metric("Estatus (Columna G)", estatus_celda)
                        col4.metric("Folio (Columna H)", folio_val if folio_val else "Sin Folio")
                        
                        st.divider()
                        st.subheader("📍 Zonas Prioritarias de Benito Juárez")
                        st.write("Consulta la ubicación o alcaldía/zona prioritaria correspondiente para este registro:")
                        
                        # Tabla de referencia de colonias / zonas prioritarias en Benito Juárez
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
    
