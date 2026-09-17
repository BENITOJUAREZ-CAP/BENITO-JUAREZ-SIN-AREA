from datetime import date, datetime
import time
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

# CONFIGURACIÓN DE PÁGINA
st.set_page_config(
    page_title="Sistema de Captura y Verificación",
    page_icon="📋",
    layout="wide",
)

# CONFIGURACIÓN DE NOMBRES Y HOJA
SPREADSHEET_ID = "1gzkpEijOVCOUqDjkNlyAQRIGpyqH_2j1H4rWGe2NTgM"
NOMBRE_HOJA = "CRUCE"
HOJA_CATALOGO = "CATALOGO"
HOJA_PERSONAL = "PERSONAL DE CAPTURA"

# FECHA DE CUMPLEAÑOS (SOLO HOY)
FECHA_CUMPLE = date(2026, 9, 17)
INTERVALO_GLOBOS_SEGUNDOS = 300  # 5 minutos

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
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
    try:
      sh = gc.open_by_key(SPREADSHEET_ID)
      try:
        return sh.worksheet(nombre_pestana)
      except Exception:
        nombre_normalizado = nombre_pestana.strip().upper().replace("Á", "A")
        for ws_item in sh.worksheets():
          if (
              ws_item.title.strip().upper().replace("Á", "A")
              == nombre_normalizado
          ):
            return ws_item
    except Exception as e:
      st.warning(
          f"Aviso de cuota/conexión al abrir pestaña '{nombre_pestana}': {e}"
      )
  return None


# Caché a 300s para no exceder cuotas de Google API
@st.cache_data(ttl=300)
def obtener_datos_cache():
  ws = obtener_worksheet(NOMBRE_HOJA)
  if ws:
    try:
      return ws.get_all_values()
    except Exception:
      pass
  return []


@st.cache_data(ttl=300)
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
    st.warning("Usando lista local/caché por límite temporal de peticiones.")

  return opciones_base


@st.cache_data(ttl=300)
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
    st.warning("Usando lista local/caché por límite temporal de peticiones.")

  return opciones_base


# INICIALIZACIÓN DE VARIABLES DE SESIÓN
if "capturista_fijo" not in st.session_state:
  st.session_state.capturista_fijo = "-- Selecciona un Capturista --"

if "ultimo_cumple_globos" not in st.session_state:
  st.session_state.ultimo_cumple_globos = 0


def comprobar_y_lanzar_globos():
  """Lanza los globos si han pasado más de 5 minutos (300s)."""
  tiempo_actual = time.time()
  if (
      tiempo_actual - st.session_state.ultimo_cumple_globos
      >= INTERVALO_GLOBOS_SEGUNDOS
  ):
    st.balloons()
    st.snow()
    st.session_state.ultimo_cumple_globos = tiempo_actual


def mostrar_tarjeta_cumpleanos():
  """Muestra una tarjeta de felicitación y reproduce audio."""
  st.markdown(
      """
        <div style="
            background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 50%, #a1c4fd 100%);
            padding: 22px;
            border-radius: 18px;
            box-shadow: 0px 6px 20px rgba(0,0,0,0.12);
            text-align: center;
            margin-top: 10px;
            margin-bottom: 15px;
            border: 2px solid #ffffff;
        ">
            <h1 style="color: #6a1b9a; font-family: 'Georgia', serif; font-size: 32px; margin: 0; font-weight: bold;">
                👑 ¡Feliz Cumpleaños Paola! 👑
            </h1>
            <p style="color: #2c3e50; font-size: 18px; margin-top: 8px; font-weight: 500;">
                ✨ Que tengas un día increíble lleno de alegrías, sonrisas y muchos éxitos. ¡Te deseamos lo mejor hoy y siempre! 🎂🎈🎉
            </p>
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.write("🎵 **Reproduciendo: Las Mañanitas - Cepillín** 🎶")
  url_audio = (
      "https://github.com/user-attachments/files/32356096/mananitas.mp3.mp3"
  )
  st.audio(url_audio, format="audio/mp3")


# BOTÓN EN LA BARRA LATERAL PARA REFRESCAR DATOS MANUALMENTE
with st.sidebar:
  st.header("⚙️ Herramientas")
  if st.button("🔄 Actualizar Datos, Catálogo y Personal"):
    st.cache_data.clear()
    st.success("¡Caché limpiado! Actualizando información...")
    time.sleep(1)
    st.rerun()

ws = obtener_worksheet(NOMBRE_HOJA)

# CREACIÓN DE PESTAÑAS PRINCIPALES EN STREAMLIT
tab_captura, tab_reporte = st.tabs(
    ["📋 Captura y Verificación", "📊 Reporte Diario y Catálogo"]
)

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

      # CONTROL DE SELECCIÓN DE CAPTURISTA ESTÁTICO
      idx_actual = 0
      if st.session_state.capturista_fijo in opciones_personal:
        idx_actual = opciones_personal.index(st.session_state.capturista_fijo)

      capturista_seleccionado_fuera = st.selectbox(
          "👤 Selecciona tu nombre para mantenerlo fijo durante tu turno:",
          options=opciones_personal,
          index=idx_actual,
          key="select_capturista_global",
      )

      st.session_state.capturista_fijo = capturista_seleccionado_fuera

      # CONDICIONAL CUMPLEAÑOS
      es_hoy_cumple = datetime.now().date() == FECHA_CUMPLE
      if es_hoy_cumple and "PAOLA" in st.session_state.capturista_fijo.upper():
        comprobar_y_lanzar_globos()
        mostrar_tarjeta_cumpleanos()

      if (
          st.session_state.capturista_fijo
          and not st.session_state.capturista_fijo.startswith("--")
      ):
        st.info(
            f"👤 Capturista activo: **{st.session_state.capturista_fijo}** (se"
            " mantendrá fijo para los siguientes registros)."
        )
      else:
        st.warning(
            "⚠️ Por favor selecciona tu nombre antes o durante el registro."
        )

      st.divider()

      if datos:
        with st.form(key="form_busqueda_principal"):
          busqueda_input = (
              st.text_input(
                  "🔑 Escanea o ingresa la CURP o el ID:",
                  placeholder="Ej. PARL420507MDFTDR06 o 13305023",
              )
              .strip()
              .upper()
          )
          btn_buscar = st.form_submit_button("🔍 Buscar")

        if busqueda_input:
          es_id = busqueda_input.isdigit()
          col_busqueda_idx = 1 if es_id else 2
          tipo_busqueda = "ID" if es_id else "CURP"

          coincidencias = []
          for idx_fila, fila in enumerate(datos):
            if (
                len(fila) > col_busqueda_idx
                and fila[col_busqueda_idx].strip().upper() == busqueda_input
            ):
              coincidencias.append(
                  {"fila_real": idx_fila + 1, "datos": fila}
              )

          if coincidencias:
            if len(coincidencias) > 1:
              st.warning(
                  f"⚠️ Se detectaron **{len(coincidencias)} registros"
                  f" duplicados** para el {tipo_busqueda} `{busqueda_input}`."
              )

              info_filas = []
              for c in coincidencias:
                val_estatus = (
                    c["datos"][6].strip() if len(c["datos"]) > 6 else ""
                )
                info_filas.append(
                    {"fila": c["fila_real"], "estatus": val_estatus}
                )

              capturados = [
                  x
                  for x in info_filas
                  if "CAPTURADO" in x["estatus"].upper()
              ]
              en_blanco = [
                  x
                  for x in info_filas
                  if "CAPTURADO" not in x["estatus"].upper()
              ]

              filas_a_borrar = []
              if len(capturados) > 0:
                filas_a_borrar = [x["fila"] for x in en_blanco]
              else:
                filas_a_borrar = [x["fila"] for x in en_blanco[1:]]

              if filas_a_borrar:
                if st.button("🧹 Limpiar duplicados automáticamente"):
                  for f in sorted(filas_a_borrar, reverse=True):
                    ws.delete_rows(f)
                  st.success(
                      f"Se eliminaron {len(filas_a_borrar)} registro(s)"
                      " duplicado(s) sobrante(s)."
                  )
                  st.cache_data.clear()
                  st.rerun()

            registro_principal = coincidencias[0]
            fila_real = registro_principal["fila_real"]
            valores_fila = registro_principal["datos"]

            def get_val(idx):
              return (
                  valores_fila[idx].strip() if len(valores_fila) > idx else ""
              )

            programa = get_val(0)
            id_registro = get_val(1)
            curp_val = get_val(2)
            nombre = f"{get_val(3)} {get_val(4)} {get_val(5)}".strip()
            estatus_actual = get_val(6)
            col_h_actual = get_val(7)
            fecha_captura = get_val(8)
            capturista_val = get_val(9)

            st.divider()

            necesita_captura = (estatus_actual == "") or (
                "NO CAPTURADO" in estatus_actual.upper()
            )

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
                st.write(
                    "**Estatus actual en Columna G:**"
                    f" `{estatus_actual if estatus_actual else 'Vacío'}`"
                )

              with col_form:
                st.markdown("### Capturar Información")

                incidencia_seleccionada = st.selectbox(
                    "📌 Opciones del Catálogo / Incidencia (Opcional):",
                    options=opciones_catalogo,
                    index=0,
                    key=f"select_cat_{busqueda_input}",
                )

                if (
                    es_hoy_cumple
                    and "PAOLA" in incidencia_seleccionada.upper()
                ):
                  comprobar_y_lanzar_globos()
                  mostrar_tarjeta_cumpleanos()

                with st.form(key=f"form_captura_{busqueda_input}"):
                  idx_form_pers = 0
                  if st.session_state.capturista_fijo in opciones_personal:
                    idx_form_pers = opciones_personal.index(
                        st.session_state.capturista_fijo
                    )

                  capturista_seleccionado = st.selectbox(
                      "👤 Nombre de la persona que captura (Columna J) -"
                      " *OBLIGATORIO*:",
                      options=opciones_personal,
                      index=idx_form_pers,
                  )

                  submit = st.form_submit_button(
                      "✅ REGISTRAR Y MARCAR CAPTURADO", use_container_width=True
                  )

                  if submit:
                    es_capturista_valido = (
                        capturista_seleccionado
                        and not capturista_seleccionado.startswith("--")
                    )

                    if not es_capturista_valido:
                      st.error(
                          "❌ OBLIGATORIO: Debes seleccionar el nombre de la"
                          " persona que realiza la captura."
                      )
                    else:
                      try:
                        st.session_state.capturista_fijo = (
                            capturista_seleccionado
                        )

                        fecha_hora_actual = datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                        val_col_h = ""
                        if (
                            incidencia_seleccionada
                            and not incidencia_seleccionada.startswith("--")
                        ):
                          val_col_h = incidencia_seleccionada

                        ws.update(
                            f"G{fila_real}:J{fila_real}",
                            [[
                                "✓ Capturado",
                                val_col_h,
                                fecha_hora_actual,
                                capturista_seleccionado,
                            ]],
                        )

                        st.success(
                            f"¡Registro exitoso en la fila {fila_real}!"
                            f" Capturó: {capturista_seleccionado} | Incidencia"
                            f" (Col H): '{val_col_h}'"
                        )
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

              st.write(
                  "📋 **Incidencia (Columna H):**"
                  f" {col_h_actual if col_h_actual else 'Sin Incidencia'}"
              )
              st.write(
                  "📅 **Fecha de Captura (Columna I):**"
                  f" {fecha_captura if fecha_captura else 'No registrada'}"
              )
              st.write(
                  "👤 **Capturado por (Columna J):**"
                  f" {capturista_val if capturista_val else 'No registrado'}"
              )

              st.divider()
              st.subheader("📍 Zonas Prioritarias de Benito Juárez")

              zonas_bj = pd.DataFrame({
                  "Sector": [
                      "Sector 1",
                      "Sector 2",
                      "Sector 3",
                      "Sector 4",
                      "Sector 5",
                  ],
                  "Colonias Cobertura": [
                      "Portales Norte, Portales Sur, Portales Oriente",
                      "Alamos, Narvarte Poniente, Narvarte Oriente",
                      "Del Valle Centro, Del Valle Sur, Del Valle Norte",
                      "Mixcoac, Insurgentes Mixcoac, Actipan",
                      "San José Insurgentes, Crédito Constructor, Nápoles",
                  ],
              })
              st.dataframe(
                  zonas_bj, use_container_width=True, hide_index=True
              )
          else:
            st.error(
                f"❌ El {tipo_busqueda} '{busqueda_input}' no se encuentra en"
                " la pestaña CRUCE."
            )
    except Exception as e:
      st.error(f"Ocurrió un error al procesar los datos: {e}")

# ---------------------------------------------------------
# PESTAÑA 2: REPORTE DIARIO, GENERAL Y CONTEO DE CATÁLOGO
# ---------------------------------------------------------
with tab_reporte:
  st.title("🔒 Acceso Restringido - Reporte Diario y Catálogo")

  if "autenticado_reporte" not in st.session_state:
    st.session_state.autenticado_reporte = False

  if not st.session_state.autenticado_reporte:
    pwd_input = st.text_input(
        "🔑 Ingresa la contraseña para ver los reportes:", type="password"
    )
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
      st.subheader("📊 Avance General, Diario y Catálogo de Incidencias")
    with col_logout:
      if st.button("🔒 Cerrar Sesión"):
        st.session_state.autenticado_reporte = False
        st.rerun()

    datos_cruce = obtener_datos_cache()
    if datos_cruce and len(datos_cruce) > 1:
      registros_capturados = []
      for row in datos_cruce[1:]:
        estatus = row[6].strip() if len(row) > 6 else ""
        if "CAPTURADO" in estatus.upper() or estatus == "✓ Capturado":
          incidencia = (
              row[7].strip()
              if len(row) > 7 and row[7].strip()
              else "SIN INCIDENCIA"
          )
          fecha_raw = row[8].strip() if len(row) > 8 else ""
          capturista = row[9].strip() if len(row) > 9 else "NO REGISTRADO"

          fecha_corta = (
              fecha_raw.split(" ")[0] if fecha_raw else "SIN FECHA"
          )

          registros_capturados.append({
              "Fecha": fecha_corta,
              "Incidencia": incidencia.upper(),
              "Capturista": capturista.upper(),
          })

      if registros_capturados:
        df_rep = pd.DataFrame(registros_capturados)

        # 1. MÉTRICAS GENERALES DE CAPTURA
        total_capturas_historico = len(df_rep)

        st.markdown("### 📌 Resumen General")
        m1, m2 = st.columns(2)
        m1.metric(
            label="📦 Total Acumulado Capturado",
            value=total_capturas_historico,
        )

        fechas_disponibles = sorted(
            [f for f in df_rep["Fecha"].unique() if f != "SIN FECHA"],
            reverse=True,
        )

        if fechas_disponibles:
          fecha_sel = st.selectbox(
              "📅 Selecciona la fecha a consultar:", options=fechas_disponibles
          )
          df_filtrado = df_rep[df_rep["Fecha"] == fecha_sel]
          m2.metric(
              label=f"📅 Capturas el {fecha_sel}", value=len(df_filtrado)
          )
        else:
          df_filtrado = df_rep

        st.divider()

        # 2. CONTEO DE CATÁLOGO / INCIDENCIAS (COLUMNA H)
        st.subheader("📋 Conteo del Catálogo de Incidencias (Columna H)")

        conteo_cat_dia = (
            df_filtrado["Incidencia"].value_counts().reset_index()
        )
        conteo_cat_dia.columns = ["Incidencia / Catálogo", "Cantidad (Día)"]

        conteo_cat_gen = df_rep["Incidencia"].value_counts().reset_index()
        conteo_cat_gen.columns = [
            "Incidencia / Catálogo",
            "Cantidad (Total Acumulado)",
        ]

        df_cat_merged = pd.merge(
            conteo_cat_gen, conteo_cat_dia, on="Incidencia / Catálogo", how="left"
        ).fillna(0)
        df_cat_merged["Cantidad (Día)"] = df_cat_merged[
            "Cantidad (Día)"
        ].astype(int)

        col_cat_tab, col_cat_graf = st.columns([1, 1], gap="medium")

        with col_cat_tab:
          st.dataframe(df_cat_merged, use_container_width=True, hide_index=True)

        with col_cat_graf:
          st.bar_chart(
              df_cat_merged.set_index("Incidencia / Catálogo")[
                  ["Cantidad (Día)", "Cantidad (Total Acumulado)"]
              ]
          )

        st.divider()

        # 3. RENDIMIENTO EXCLUSIVO DEL PERSONAL DE CAPTURA
        st.subheader("👤 Rendimiento por Personal de Captura")

        # Obtener lista oficial de la hoja PERSONAL DE CAPTURA
        lista_personal_raw = obtener_opciones_personal()
        lista_personal_oficial = [
            p.upper()
            for p in lista_personal_raw
            if p and not p.startswith("--")
        ]

        if lista_personal_oficial:
          df_base_personal = pd.DataFrame(
              {"Capturista / Persona": lista_personal_oficial}
          )

          # Conteos de captura
          conteo_cap_dia = (
              df_filtrado["Capturista"].value_counts().reset_index()
          )
          conteo_cap_dia.columns = [
              "Capturista / Persona",
              "Total (Día Seleccionado)",
          ]

          conteo_cap_gen = df_rep["Capturista"].value_counts().reset_index()
          conteo_cap_gen.columns = [
              "Capturista / Persona",
              "Total (Acumulado Histórico)",
          ]

          # Filtrar únicamente los nombres que pertenecen al personal oficial
          df_cap_merged = pd.merge(
              df_base_personal, conteo_cap_gen, on="Capturista / Persona", how="left"
          )
          df_cap_merged = pd.merge(
              df_cap_merged, conteo_cap_dia, on="Capturista / Persona", how="left"
          ).fillna(0)

          df_cap_merged["Total (Acumulado Histórico)"] = df_cap_merged[
              "Total (Acumulado Histórico)"
          ].astype(int)
          df_cap_merged["Total (Día Seleccionado)"] = df_cap_merged[
              "Total (Día Seleccionado)"
          ].astype(int)

          # Ordenar descendente por total acumulado
          df_cap_merged = df_cap_merged.sort_values(
              by="Total (Acumulado Histórico)", ascending=False
          )

          col_tabla, col_grafica = st.columns([1, 1], gap="medium")

          with col_tabla:
            st.dataframe(
                df_cap_merged, use_container_width=True, hide_index=True
            )

          with col_grafica:
            st.bar_chart(
                df_cap_merged.set_index("Capturista / Persona")[
                    ["Total (Día Seleccionado)", "Total (Acumulado Histórico)"]
                ]
            )
        else:
          st.warning("No se encontraron nombres en la hoja PERSONAL DE CAPTURA.")
      else:
        st.info("Aún no hay registros marcados como capturados.")
    else:
      st.warning("No hay datos disponibles en la pestaña CRUCE.")
