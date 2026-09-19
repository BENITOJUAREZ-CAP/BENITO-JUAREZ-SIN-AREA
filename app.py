import random
import time
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import pytz
import streamlit as st

# =========================================================
# CONFIGURACIÓN INICIAL DE LA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Sistema de Captura y Verificación",
    page_icon="📋",
    layout="wide",
)

# Constante para evento de cumpleaños opcional
FECHA_CUMPLE = datetime(2026, 5, 7).date()


def comprobar_y_lanzar_globos():
  st.balloons()


def mostrar_tarjeta_cumpleanos():
  st.success("🎉 ¡Feliz Cumpleaños! 🎉")


# =========================================================
# AUTENTICACIÓN Y CONEXIÓN A GOOGLE SHEETS
# =========================================================
@st.cache_resource
def conectar_google_sheets():
  try:
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
      creds = Credentials.from_service_account_info(
          st.secrets["gcp_service_account"], scopes=scope
      )
    else:
      creds = Credentials.from_service_account_file(
          "credentials.json", scopes=scope
      )

    client = gspread.authorize(creds)

    # Reemplaza con el nombre de tu archivo de Google Sheets
    spreadsheet = client.open("REGISTRO_CRUCE")
    ws = spreadsheet.worksheet("CRUCE")
    return ws
  except Exception as e:
    st.error(f"Error de conexión con Google Sheets: {e}")
    return None


ws = conectar_google_sheets()

# Initialize session state for persistent user selection
if "capturista_fijo" not in st.session_state:
  st.session_state.capturista_fijo = ""


# =========================================================
# FUNCIONES AUXILIARES CON MANEJO DE RETRY Y CACHÉ
# =========================================================
def ejecutar_con_reintento(
    func, *args, max_intentos=4, espera_base=1.5, **kwargs
):
  """Ejecuta una función de gspread con reintentos aleatorios para evitar colisiones entre usuarios."""
  for intento in range(max_intentos):
    try:
      return func(*args, **kwargs)
    except Exception as e:
      err_msg = str(e).lower()
      if (
          "429" in err_msg
          or "quota" in err_msg
          or "exceeded" in err_msg
          or "rate" in err_msg
      ):
        if intento < max_intentos - 1:
          # Espera aleatoria entre 1.5s y 3.5s para descongestionar la API
          tiempo_espera = espera_base + random.uniform(0.5, 2.0) * (intento + 1)
          time.sleep(tiempo_espera)
        else:
          raise e
      else:
        raise e


@st.cache_data(ttl=60, show_spinner=False)
def obtener_datos_cache():
  """Obtiene todos los datos de la pestaña CRUCE en caché por 60 segundos."""
  if ws:
    try:
      return ejecutar_con_reintento(ws.get_all_values)
    except Exception:
      return []
  return []


@st.cache_data(ttl=120, show_spinner=False)
def obtener_opciones_catalogo():
  """Obtiene las opciones de la columna H o catálogo base."""
  return [
      "-- Selecciona una opción (Opcional) --",
      "INSPECCIÓN FÍSICA APROBADA",
      "DOCUMENTACIÓN INCOMPLETA",
      "BENEFICIARIO NO LOCALIZADO",
      "DUPLICADO EN SISTEMA",
      "PENDIENTE DE VALIDACIÓN",
      "OTRO",
  ]


@st.cache_data(ttl=120, show_spinner=False)
def obtener_opciones_personal():
  """Lista de capturistas disponibles."""
  return [
      "-- Selecciona tu Nombre --",
      "MARCELINO",
      "PAOLA",
      "CARLOS",
      "DANIEL",
      "JUAN",
      "MARÍA",
      "PEDRO",
  ]


# =========================================================
# NAVEGACIÓN Y PESTAÑAS PRINCIPALES
# =========================================================
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
      zona_mx = pytz.timezone("America/Mexico_City")
      es_hoy_cumple = datetime.now(zona_mx).date() == FECHA_CUMPLE
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

      # 📌 EL FORMULARIO DE BÚSQUEDA AHORA SIEMPRE PERMANECE VISIBLE
      with st.form(key="form_busqueda_principal"):
        busqueda_input = st.text_input(
            "🔑 Escanea o ingresa la CURP o el ID:",
            placeholder="Ej. PARL420507MDFTDR06 o 13305023",
        )
        btn_buscar = st.form_submit_button("🔍 Buscar")

      # VALIDACIÓN DE CARGA TEMPORAL DE DATOS
      if not datos:
        st.warning(
            "⚠️ Conectando con Google Sheets para sincronizar la lista por alta"
            " concurrencia... Por favor escribe la CURP y presiona '🔍 Buscar'"
            " nuevamente."
        )
      else:
        if busqueda_input:
          # Limpieza de caracteres y espacios
          busqueda_limpia = (
              busqueda_input.strip()
              .upper()
              .replace(" ", "")
              .replace("\n", "")
              .replace("\r", "")
          )
          es_id = busqueda_limpia.isdigit()
          col_busqueda_idx = 1 if es_id else 2
          tipo_busqueda = "ID" if es_id else "CURP"

          coincidencias = []
          for idx_fila, fila in enumerate(datos):
            if len(fila) > col_busqueda_idx:
              valor_celda = (
                  str(fila[col_busqueda_idx])
                  .strip()
                  .upper()
                  .replace(" ", "")
                  .replace("\n", "")
                  .replace("\r", "")
              )
              if valor_celda == busqueda_limpia:
                coincidencias.append({"fila_real": idx_fila + 1, "datos": fila})

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
                  try:
                    for f in sorted(filas_a_borrar, reverse=True):
                      ejecutar_con_reintento(ws.delete_rows, f)
                    st.success(
                        f"Se eliminaron {len(filas_a_borrar)} registro(s)"
                        " duplicado(s) sobrante(s)."
                    )
                    st.cache_data.clear()
                    st.rerun()
                  except Exception as e_del:
                    st.error(
                        f"No se pudieron eliminar los duplicados debido a alta"
                        f" concurrencia: {e_del}"
                    )

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
                    key=f"select_cat_{busqueda_limpia}",
                )

                if (
                    es_hoy_cumple
                    and "PAOLA" in incidencia_seleccionada.upper()
                ):
                  comprobar_y_lanzar_globos()
                  mostrar_tarjeta_cumpleanos()

                with st.form(key=f"form_captura_{busqueda_limpia}"):
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
                      st.session_state.capturista_fijo = capturista_seleccionado

                      zona_mx = pytz.timezone("America/Mexico_City")
                      fecha_hora_actual = datetime.now(zona_mx).strftime(
                          "%Y-%m-%d %H:%M:%S"
                      )

                      val_col_h = ""
                      if (
                          incidencia_seleccionada
                          and not incidencia_seleccionada.startswith("--")
                      ):
                        val_col_h = incidencia_seleccionada

                      try:
                        res_upd = ejecutar_con_reintento(
                            ws.update,
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
                        st.error(
                            "⚠️ El servidor de Google recibió demasiadas"
                            " peticiones. Por favor, haz clic en 'REGISTRAR' de"
                            f" nuevo. Detalles: {err}"
                        )
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
# PESTAÑA 2: REPORTE DIARIO Y CATÁLOGO
# ---------------------------------------------------------
with tab_reporte:
  st.title("📊 Resumen de Avance de Captura y Catálogos")

  if ws:
    try:
      datos_rep = obtener_datos_cache()

      if datos_rep and len(datos_rep) > 1:
        df = pd.DataFrame(datos_rep[1:], columns=datos_rep[0])

        col_g_nombre = df.columns[6] if len(df.columns) > 6 else None
        col_j_nombre = df.columns[9] if len(df.columns) > 9 else None

        col1, col2, col3 = st.columns(3)

        total_registros = len(df)
        col1.metric("Total de Registros Base", total_registros)

        if col_g_nombre:
          capturados_cnt = len(
              df[df[col_g_nombre].str.contains("Capturado", case=False, na=False)]
          )
          pendientes_cnt = total_registros - capturados_cnt

          col2.metric("Total Capturados", capturados_cnt)
          col3.metric("Pendientes", pendientes_cnt)

          porcentaje = (
              (capturados_cnt / total_registros) * 100
              if total_registros > 0
              else 0
          )
          st.progress(
              porcentaje / 100,
              text=f"Avance de captura: {porcentaje:.2f}% completado",
          )

        st.divider()

        if col_j_nombre:
          st.subheader("👥 Capturas por Capturista")
          conteo_capturistas = (
              df[col_j_nombre]
              .value_counts()
              .reset_index()
              .rename(
                  columns={
                      "index": "Capturista",
                      col_j_nombre: "Total Capturados",
                  }
              )
          )
          st.dataframe(
              conteo_capturistas, use_container_width=True, hide_index=True
          )

      else:
        st.info("No hay datos disponibles para generar el reporte en vivo.")
    except Exception as e_rep:
      st.error(f"Error al generar reporte: {e_rep}")

# ---------------------------------------------------------
# BARRA LATERAL (SIDEBAR)
# ---------------------------------------------------------
with st.sidebar:
  st.header("⚙️ Opciones de Sistema")
  if st.button("🔄 Actualizar Datos Manualmente"):
    st.cache_data.clear()
    st.success("Caché limpiada correctamente.")
    st.rerun()

  st.caption("Sistema de Captura v2.1 — Benito Juárez / Cruce")
