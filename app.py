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

# CONFIGURACIÓN DE NOMBRES Y HOJA
SPREADSHEET_ID = "1gzkpEijOVCOUqDjkNlyAQRIGpyqH_2j1H4rWGe2NTgM"
NOMBRE_HOJA = "CRUCE"
HOJA_CATALOGO = "CATALOGO"
HOJA_PERSONAL = "PERSONAL DE CAPTURA"

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

@st.cache_resource
def obtener_worksheet(nombre_pestana):
    gc = obtener_cliente_gspread()
    if gc:
        sh = gc.open_by_key(SPREADSHEET_ID)
        return sh.worksheet(nombre_pestana)
    return None

@st.cache_data(ttl=60)
def obtener_datos_cache():
    ws = obtener_worksheet(NOMBRE_HOJA)
    if ws:
        return ws.get_all_values()
    return []

@st.cache_data(ttl=5)
def obtener_opciones_catalogo():
    opciones_base = ["-- Seleccionar Incidencia (Opcional) --"]
    try:
        ws_cat = obtener_worksheet(HOJA_CATALOGO)
        if ws_cat:
            col_a = ws_cat.col_values(1)
            opciones_hoja = [x.strip() for x in col_a[1:] if x.strip()]
            if opciones_hoja:
                return opciones_base + opciones_hoja
    except Exception as e:
        st.error(f"Error al leer la pestaña CATALOGO: {e}")
    
    return opciones_base

@st.cache_data(ttl=5)
def obtener_opciones_personal():
    opciones_base = ["-- Selecciona un Capturista --"]
    try:
        ws_pers = obtener_worksheet(HOJA_PERSONAL)
        if ws_pers:
            col_a = ws_pers.col_values(1)
            personal_hoja = [x.strip() for x in col_a[1:] if x.strip()]
            if personal_hoja:
                return opciones_base + personal_hoja
    except Exception as e:
        st.error(f"Error al leer la pestaña PERSONAL DE CAPTURA: {e}")
    
    return opciones_base

# INICIALIZACIÓN DE VARIABLE DE SESIÓN PARA RECORDAR EL CAPTURISTA DE FORMA ESTÁTICA
if "capturista_fijo" not in st.session_state:
    st.session_state.capturista_fijo = "-- Selecciona un Capturista --"

# BOTÓN EN LA BARRA LATERAL PARA REFRESCAR DATOS AL INSTANTE
with st.sidebar:
    st.header("⚙️ Herramientas")
    if st.button("🔄 Actualizar Datos, Catálogo y Personal"):
        st.cache_data.clear()
        st.success("¡Datos y catálogos actualizados!")
        st.rerun()

ws = obtener_worksheet(NOMBRE_HOJA)

# CREACIÓN DE PESTAÑAS PRINCIPALES EN STREAMLIT
tab_captura, tab_reporte = st.tabs(["📋 Captura y Verificación", "📊 Reporte Diario por Persona"])

# ---------------------------------------------------------
# PESTAÑA 1: CAPTURA Y VERIFICACIÓN
# ---------------------------------------------------------
with tab_captura:
    st.title("📋 Verificador de Estatus y Captura (Pestaña CRUCE)")

    if ws:
        try:
            datos = obtener_datos_cache()
            opciones_catalogo = obtener_opciones_catalogo()
            opciones_personal = obtener_opciones_personal()
            
            # CONTROL DE SELECCIÓN DE CAPTURISTA ESTÁTICO (RECORDAR EN SESIÓN)
            idx_actual = 0
            if st.session_state.capturista_fijo in opciones_personal:
                idx_actual = opciones_personal.index(st.session_state.capturista_fijo)
                
            capturista_seleccionado_fuera = st.selectbox(
                "👤 Selecciona tu nombre para mantenerlo fijo durante tu turno:",
                options=opciones_personal,
                index=idx_actual,
                key="select_capturista_global"
            )
            
            st.session_state.capturista_fijo = capturista_seleccionado_fuera
            
            if st.session_state.capturista_fijo and not st.session_state.capturista_fijo.startswith("--"):
                st.info(f"👤 Capturista activo: **{st.session_state.capturista_fijo}** (se mantendrá fijo para los siguientes registros).")
            else:
                st.warning("⚠️ Por favor selecciona tu nombre antes o durante el registro.")

            st.divider()

            if datos:
                with st.form(key="form_busqueda_principal"):
                    busqueda_input = st.text_input(
                        "🔑 Escanea o ingresa la CURP o el ID:", 
                        placeholder="Ej. PARL420507MDFTDR06 o 13305023"
                    ).strip().upper()
                    btn_buscar = st.form_submit_button("🔍 Buscar")
                
                if busqueda_input:
                    es_id = busqueda_input.isdigit()
                    col_busqueda_idx = 1 if es_id else 2
                    tipo_busqueda = "ID" if es_id else "CURP"
                    
                    coincidencias = []
                    for idx_fila, fila in enumerate(datos):
                        if len(fila) > col_busqueda_idx and fila[col_busqueda_idx].strip().upper() == busqueda_input:
                            coincidencias.append({
                                "fila_real": idx_fila + 1,
                                "datos": fila
                            })
                    
                    if coincidencias:
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
                            
                            if filas_a_borrar:
                                if st.button("🧹 Limpiar duplicados automáticamente"):
                                    for f in sorted(filas_a_borrar, reverse=True):
                                        ws.delete_rows(f)
                                    st.success(f"Se eliminaron {len(filas_a_borrar)} registro(s) duplicado(s) sobrante(s).")
                                    st.cache_data.clear()
                                    st.rerun()

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
                        col_h_actual = get_val(7)
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
                                    incidencia_seleccionada = st.selectbox(
                                        "📌 Opciones del Catálogo / Incidencia (Opcional):",
                                        options=opciones_catalogo,
                                        index=0
                                    )
                                    
                                    idx_form_pers = 0
                                    if st.session_state.capturista_fijo in opciones_personal:
                                        idx_form_pers = opciones_personal.index(st.session_state.capturista_fijo)

                                    capturista_seleccionado = st.selectbox(
                                        "👤 Nombre de la persona que captura (Columna J) - *OBLIGATORIO*:",
                                        options=opciones_personal,
                                        index=idx_form_pers
                                    )
                                    
                                    submit = st.form_submit_button("✅ REGISTRAR Y MARCAR CAPTURADO", use_container_width=True)
                                    
                                    if submit:
                                        es_capturista_valido = capturista_seleccionado and not capturista_seleccionado.startswith("--")
                                        
                                        if not es_capturista_valido:
                                            st.error("❌ OBLIGATORIO: Debes seleccionar el nombre de la persona que realiza la captura.")
                                        else:
                                            try:
                                                st.session_state.capturista_fijo = capturista_seleccionado
                                                
                                                fecha_hora_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                                
                                                val_col_h = ""
                                                if incidencia_seleccionada and not incidencia_seleccionada.startswith("--"):
                                                    val_col_h = incidencia_seleccionada
                                                
                                                ws.update(f"G{fila_real}:J{fila_real}", [
                                                    [
                                                        "✓ Capturado",
                                                        val_col_h,
                                                        fecha_hora_actual,
                                                        capturista_seleccionado
                                                    ]
                                                ])
                                                
                                                st.success(f"¡Registro exitoso en la fila {fila_real}! Capturó: {capturista_seleccionado} | Incidencia (Col H): '{val_col_h}'")
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
                            
                            st.write(f"📋 **Incidencia (Columna H):** {col_h_actual if col_h_actual else 'Sin Incidencia'}")
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

# ---------------------------------------------------------
# PESTAÑA 2: REPORTE DIARIO POR PERSONA (PROTEGIDO CON CONTRASEÑA)
# ---------------------------------------------------------
with tab_reporte:
    st.title("🔒 Acceso Restringido - Reporte Diario")
    
    if "autenticado_reporte" not in st.session_state:
        st.session_state.autenticado_reporte = False
        
    if not st.session_state.autenticado_reporte:
        pwd_input = st.text_input("🔑 Ingresa la contraseña para ver los reportes:", type="password")
        if st.button("🔓 Entrar al Reporte"):
            if pwd_input == "Alan.":
                st.session_state.autenticado_reporte = True
                st.success("Acceso concedido.")
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta. Intenta nuevamente.")
    else:
        col_tit, col_logout = st.columns([4, 1])
        with col_tit:
            st.subheader("📊 Avance Diario de Captura por Persona")
        with col_logout:
            if st.button("🔒 Cerrar Sesión"):
                st.session_state.autenticado_reporte = False
                st.rerun()
                
        datos_cruce = obtener_datos_cache()
        if datos_cruce and len(datos_cruce) > 1:
            registros_capturados = []
            for row in datos_cruce[1:]:
                if len(row) >= 10:
                    fecha_raw = row[8].strip()
                    capturista = row[9].strip()
                    if fecha_raw and capturista:
                        fecha_corta = fecha_raw.split(" ")[0]
                        registros_capturados.append({
                            "Fecha": fecha_corta,
                            "Capturista": capturista.upper()
                        })
            
            if registros_capturados:
                df_rep = pd.DataFrame(registros_capturados)
                
                fechas_disponibles = sorted(list(df_rep["Fecha"].unique()), reverse=True)
                fecha_sel = st.selectbox("📅 Selecciona la fecha a consultar:", options=fechas_disponibles)
                
                df_filtrado = df_rep[df_rep["Fecha"] == fecha_sel]
                
                conteo = df_filtrado["Capturista"].value_counts().reset_index()
                conteo.columns = ["Capturista / Persona", "Total Capturados"]
                
                st.metric(label=f"Total de capturas el {fecha_sel}", value=len(df_filtrado))
                
                col_tabla, col_grafica = st.columns([1, 1], gap="medium")
                
                with col_tabla:
                    st.subheader("📋 Detalle por Capturista")
                    st.dataframe(conteo, use_container_width=True, hide_index=True)
                
                with col_grafica:
                    st.subheader("📈 Gráfico de Rendimiento")
                    st.bar_chart(conteo.set_index("Capturista / Persona"))
            else:
                st.info("Aún no hay registros capturados con fecha y nombre guardados.")
        else:
            st.warning("No hay datos disponibles en la pestaña CRUCE.")
