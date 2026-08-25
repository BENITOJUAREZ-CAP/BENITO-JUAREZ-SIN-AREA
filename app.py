import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

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
            
            # Campo de entrada único para CURP o ID
            busqueda_input = st.text_input("🔑 Escanea o ingresa la CURP o el ID:", placeholder="Ej. PARL420507MDFTDR06 o 13305023").strip().upper()
            
            if busqueda_input:
                # Determinar si la búsqueda es por ID (solo números) o por CURP (Columna B = 2, Columna C = 3)
                es_id = busqueda_input.isdigit()
                col_busqueda = 2 if es_id else 3
                tipo_busqueda = "ID" if es_id else "CURP"
                
                # Buscar todas las coincidencias en la columna correspondiente
                celdas_coincidentes = ws.findall(busqueda_input, in_column=col_busqueda)
                
                if celdas_coincidentes:
                    filas_encontradas = [cell.row for cell in celdas_coincidentes]
                    
                    # GESTIÓN DE DUPLICADOS
                    if len(filas_encontradas) > 1:
                        st.warning(f"⚠️ Se detectaron **{len(filas_encontradas)} registros duplicados** para el {tipo_busqueda} `{busqueda_input}`.")
                        
                        info_filas = []
                        for f in filas_encontradas:
                            val_estatus = str(ws.cell(f, 7).value or "").strip()
                            info_filas.append({"fila": f, "estatus": val_estatus})
                        
                        capturados = [x for x in info_filas if "CAPTURADO" in x["estatus"].upper()]
                        en_blanco = [x for x in info_filas if "CAPTURADO" not in x["estatus"].upper()]
                        
                        filas_a_borrar = []
                        if len(capturados) > 0:
                            # Si hay capturado, borramos todos los que están en blanco
                            filas_a_borrar = [x["fila"] for x in en_blanco]
                        else:
                            # Si todos están en blanco, dejamos la primera fila y borramos el resto
                            filas_a_borrar = [x["fila"] for x in en_blanco[1:]]
                        
                        if filas_a_borrar:
                            if st.button("🧹 Limpiar duplicados automáticamente"):
                                for f in sorted(filas_a_borrar, reverse=True):
                                    ws.delete_rows(f)
                                st.success(f"Se eliminaron {len(filas_a_borrar)} registro(s) duplicado(s) sobrante(s).")
                                st.cache_data.clear()
                                st.rerun()

                    # Tomar la primera celda activa válida
                    celda_principal = ws.find(busqueda_input, in_column=col_busqueda)
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
                    fecha_captura = get_val(8)
                    capturista_val = get_val(9)
                    
                    st.divider()
                    
                    necesita_captura = (estatus_actual == "") or ("NO CAPTURADO" in estatus_actual.upper())
                    
                    if necesita_captura:
                        st.subheader("🟢 Registro Disponible para Captura")
                        
                        col_info, col_form = st.columns([1, 1], gap="large")
                        
                        with col_info:
                            st.markdown("### Datos del Beneficiario")
                            st.write(f"**Nombre:** {nombre}")
                            st.write(f"**ID:** {id_registro}")
                            st.write(f"**CURP:** {curp_val}")
                            st.write(f"**Programa:** {programa}")
                            st.write(f"**Fila en Sheets:** `{fila_real}`")
                            st.write(f"**Estatus actual en Columna G:** `{estatus_actual if estatus_actual else 'Vacío'}`")
                        
                        with col_form:
                            st.markdown("### Capturar Información")
                            with st.form(key=f"form_captura_{busqueda_input}"):
                                folio_nuevo = st.text_input("Folio a asignar (opcional):", key="input_folio").strip()
                                capturista_input = st.text_input("👤 Nombre de la persona que captura (Columna J):", placeholder="Ej. Juan Pérez").strip()
                                
                                submit = st.form_submit_button("✅ REGISTRAR Y MARCAR CAPTURADO", use_container_width=True)
                                
                                if submit:
                                    if not capturista_input:
                                        st.error("Por favor ingresa el nombre de la persona que está realizando la captura.")
                                    else:
                                        try:
                                            fecha_hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            
                                            # Columna G (7): Estatus
                                            ws.update_cell(fila_real, 7, "✓ Capturado")
                                            
                                            # Columna H (8): Folio
                                            if folio_nuevo:
                                                ws.update_cell(fila_real, 8, folio_nuevo)
                                            
                                            # Columna I (9): Fecha de Captura
                                            ws.update_cell(fila_real, 9, fecha_hora_actual)
                                            
                                            # Columna J (10): Nombre del Capturista
                                            ws.update_cell(fila_real, 10, capturista_input)
                                            
                                            st.success(f"¡Registro exitoso en la fila {fila_real}! Fecha: {fecha_hora_actual} | Capturó: {capturista_input}")
                                            st.cache_data.clear()
                                            st.rerun()
                                        except Exception as err:
                                            st.error(f"Error al escribir en Google Sheets: {err}")
                    else:
                        st.subheader("🔵 Registro Ya Capturado")
                        
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("ID", id_registro)
                        c2.metric("CURP", curp_val)
                        c3.metric("Nombre", nombre)
                        c4.metric("Estatus (G)", estatus_actual)
                        
                        st.write(f"📋 **Folio Asignado (H):** {folio_actual if folio_actual else 'Sin Folio'}")
                        st.write(f"📅 **Fecha de Captura (Columna I):** {fecha_captura if fecha_captura else 'No registrada'}")
                        st.write(f"👤 **Capturado por (Columna J):** {capturista_val if capturista_val else 'No registrado'}")
                        
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
                    st.error(f"❌ El {tipo_busqueda} '{busqueda_input}' no se encuentra en la pestaña CRUCE.")
    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
