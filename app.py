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

# Sin @st.cache_resource para evitar que se congele la llamada al objeto worksheet
def obtener_worksheet():
    gc = obtener_cliente_gspread()
    if gc:
        sh = gc.open_by_key(SPREADSHEET_ID)
        return sh.worksheet(NOMBRE_HOJA)
    return None

# OPTIMIZACIÓN EN CACHÉ: Guarda los datos en RAM durante 60 segundos
@st.cache_data(ttl=60)
def obtener_datos_cache():
    ws = obtener_worksheet()
    if ws:
        return ws.get_all_values()
    return []

st.title("📋 Verificador de Estatus y Captura (Pestaña CRUCE)")

# Carga rápida en segundo plano con indicador
with st.spinner("Conectando con Google Sheets y sincronizando base de datos..."):
    datos = obtener_datos_cache()

if datos:
    try:
        ws = obtener_worksheet()
        
        # FORMULARIO DE BÚSQUEDA (Evita peticiones por cada carácter escrito)
        with st.form(key="form_busqueda_principal"):
            busqueda_input = st.text_input(
                "🔑 Escanea o ingresa la CURP o el ID:", 
                placeholder="Ej. PARL420507MDFTDR06 o 13305023"
            ).strip().upper()
            btn_buscar = st.form_submit_button("🔍 Buscar")
        
        if busqueda_input:
            es_id = busqueda_input.isdigit()
            # Columna B es ID (índice 1 en Python), Columna C es CURP (índice 2 en Python)
            col_busqueda_idx = 1 if es_id else 2
            tipo_busqueda = "ID" if es_id else "CURP"
            
            # Búsqueda instantánea en RAM
            coincidencias = []
            for idx_fila, fila in enumerate(datos):
                if len(fila) > col_busqueda_idx and fila[col_busqueda_idx].strip().upper() == busqueda_input:
                    coincidencias.append({
                        "fila_real": idx_fila + 1,  # Fila real en la hoja de Google Sheets
                        "datos": fila
                    })
            
            if coincidencias:
                filas_encontradas = [c["fila_real"] for c in coincidencias]
                
                # GESTIÓN DE DUPLICADOS EN RAM
                if len(coincidencias) > 1:
                    st.warning(f"⚠️ Se detectaron **{len(coincidencias)} registros duplicados** para el {tipo_busqueda} `{busqueda_input}`.")
                    
                    info_filas = []
                    for c in coincidencias:
                        val_estatus = c["datos"][6].strip() if len(c["datos"]) > 6 else ""
                        info_filas.append({"fila": c["fila_real"], "estatus": val_estatus})
                    
                    capturados = [x for x in info_filas if "CAPTURADO" in x["estatus"].upper()]
                    en_blanco = [x for x in info_filas if "CAPTURADO" not in x["estatus"].upper()]
                    
                    filas_a_borrar = []
                    if len(capturados) > 0:
                        filas_a_borrar = [x["fila"] for x in en_blanco]
                    else:
                        filas_a_borrar = [x["fila"] for x in en_blanco[1:]]
                    
                    if filas_a_borrar and ws:
                        if st.button("🧹 Limpiar duplicados automáticamente"):
                            for f in sorted(filas_a_borrar, reverse=True):
                                ws.delete_rows(f)
                            st.success(f"Se eliminaron {len(filas_a_borrar)} registro(s) duplicado(s) sobrante(s).")
                            st.cache_data.clear()
                            st.rerun()

                # Tomar la primera coincidencia activa
                registro_principal = coincidencias[0]
                fila_real = registro_principal["fila_real"]
                valores_fila = registro_principal["datos"]
                
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
                                        
                                        # OPTIMIZACIÓN DE ESCRITURA: Actualización en 1 solo bloque (Columnas G, H, I, J)
                                        # Rango G{fila}:J{fila}
                                        nuevos_valores = [
                                            [
                                                "✓ Capturado",             # Columna G (7)
                                                folio_nuevo if folio_nuevo else folio_actual, # Columna H (8)
                                                fecha_hora_actual,         # Columna I (9)
                                                capturista_input           # Columna J (10)
                                            ]
                                        ]
                                        
                                        if ws:
                                            ws.update(f"G{fila_real}:J{fila_real}", nuevos_valores)
                                            
                                            st.success(f"¡Registro exitoso en la fila {fila_real}! Fecha: {fecha_hora_actual} | Capturó: {capturista_input}")
                                            st.cache_data.clear()
                                            st.rerun()
                                        else:
                                            st.error("No se pudo conectar con la hoja de Google Sheets.")
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
