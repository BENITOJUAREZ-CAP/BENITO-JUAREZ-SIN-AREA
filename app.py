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
        
        datos = ws.get_all_values()
        
        if datos:
            headers = [str(h).strip().upper() for h in datos[0]]
            df = pd.DataFrame(datos[1:], columns=headers)
            
            df["CURP_CLEAN"] = df["CURP"].astype(str).str.strip().str.upper()
            
            curp_input = st.text_input("🔑 Escanea o ingresa la CURP:", placeholder="Ej. PARL420507MDFTDR06").strip().upper()
            
            if curp_input:
                # Buscar todas las celdas coincidentes por CURP en la columna 3 (C)
                celdas_coincidentes = ws.findall(curp_input, in_column=3)
                
                if celdas_coincidentes:
                    filas_encontradas = [cell.row for cell in celdas_coincidentes]
                    
                    # SI HAY DUPLICADOS -> APLICAR REGLA DE DEPURACIÓN
                    if len(filas_encontradas) > 1:
                        st.warning(f"⚠️ Se detectaron **{len(filas_encontradas)} registros duplicados** para la CURP `{curp_input}`.")
                        
                        # Recolectar estatus de cada fila encontrada
                        info_filas = []
                        for f in filas_encontradas:
                            val_estatus = str(ws.cell(f, 7).value or "").strip()
                            info_filas.append({"fila": f, "estatus": val_estatus})
                        
                        # Separar capturados y en blanco
                        capturados = [x for x in info_filas if "CAPTURADO" in x["estatus"].upper()]
                        en_blanco = [x for x in info_filas if "CAPTURADO" not in x["estatus"].upper()]
                        
                        # Determinar cuáles se deben borrar
                        filas_a_borrar = []
                        if len(capturados) > 0:
                            # Si ya hay capturado(s), se borran TODOS los que están en blanco
                            filas_a_borrar = [x["fila"] for x in en_blanco]
                        else:
                            # Si TODOS están en blanco, dejamos la primera fila y borramos el resto de duplicados
                            filas_a_borrar = [x["fila"] for x in en_blanco[1:]]
                        
                        if filas_a_borrar:
                            if st.button("🧹 Limpiar duplicados automáticamente"):
                                # Se borran de abajo hacia arriba para mantener intactos los índices de fila arriba
                                for f in sorted(filas_a_borrar, reverse=True):
                                    ws.delete_rows(f)
                                st.success(f"Se eliminaron {len(filas_a_borrar)} registro(s) duplicado(s) sobrante(s).")
                                st.cache_data.clear()
                                st.rerun()

                    # Re-obtener la celda activa principal tras la evaluación
                    celda_principal = ws.find(curp_input, in_column=3)
                    fila_real = celda_principal.row
                    
                    valores_fila = ws.row_values(fila_real)
                    
                    def get_val(idx):
                        return valores_fila[idx].strip() if len(valores_fila) > idx else ""
                    
                    programa = get_val(0)
                    id_registro = get_val(1)
                    curp_val = get_val(2)
                    nombre = f"{get_val(3)} {get_val(4)} {get_val(5)}".strip()
                    estatus_actual = get_val(6)
                    folio_actual = get_val(7)
                    
                    st.divider()
                    
                    necesita_captura = (estatus_actual == "") or ("NO CAPTURADO" in estatus_actual.upper())
                    
                    if necesita_captura:
                        st.subheader("🟢 Registro Disponible para Captura")
                        
                        col_info, col_form = st.columns([1, 1], gap="large")
                        
                        with col_info:
                            st.markdown("### Datos del Beneficiario")
                            st.write(f"**Nombre:** {nombre}")
                            st.write(f"**CURP:** {curp_val}")
                            st.write(f"**ID:** {id_registro}")
                            st.write(f"**Programa:** {programa}")
                            st.write(f"**Fila en Sheets:** `{fila_real}`")
                            st.write(f"**Estatus actual en Columna G:** `{estatus_actual if estatus_actual else 'Vacío'}`")
                        
                        with col_form:
                            st.markdown("### Capturar Folio")
                            with st.form(key=f"form_captura_{curp_input}"):
                                folio_nuevo = st.text_input("Folio a asignar (opcional):", key="input_folio").strip()
                                submit = st.form_submit_button("✅ REGISTRAR Y MARCAR CAPTURADO", use_container_width=True)
                                
                                if submit:
                                    try:
                                        ws.update_cell(fila_real, 7, "✓ Capturado")
                                        if folio_nuevo:
                                            ws.update_cell(fila_real, 8, folio_nuevo)
                                        
                                        st.success(f"¡Se actualizó la fila {fila_real} en Google Sheets!")
                                        st.cache_data.clear()
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Error al escribir en Google Sheets: {err}")
                    else:
                        st.subheader("🔵 Registro Ya Capturado")
                        
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("CURP", curp_val)
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
