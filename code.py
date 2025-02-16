import streamlit as st
import gspread
from gspread import Cell
from datetime import datetime
from google.oauth2.service_account import Credentials

# Configuración de la página
st.set_page_config(
    page_title="Estado de Clientes",
    page_icon="👥",
    layout="wide"
)

# --- CONFIGURACIÓN DE LAS CREDENCIALES Y CONEXIÓN A GOOGLE SHEETS ---
# Asegúrate de tener en st.secrets el JSON de la cuenta de servicio bajo la clave "gcp_service_account"
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
gc = gspread.authorize(credentials)

SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1d5kxv7lFE9ZZVSfCSvHAcxHuyjsXh8_Jr88btbfcKDM/edit?usp=drive_link'
sheet = gc.open_by_url(SPREADSHEET_URL).sheet1

# --- FUNCIÓN PARA OBTENER LOS DATOS DE LA HOJA ---
def get_data():
    try:
        return sheet.get_all_values()
    except Exception as e:
        st.error(f"❌ Error al obtener los datos: {e}")
        return None

# --- FUNCIÓN PARA BUSCAR FILAS SEGÚN "Cuenta" Y "Sector de Riego" ---
def find_rows(selected_cuenta, selected_sector, data):
    """
    Busca filas en base a la Cuenta (columna A) y Sector de Riego (columna B).
    Para Sector de Riego se permite la opción "Todos" para no filtrar.
    Retorna una lista de números de fila (contando desde 1) donde se cumple la condición.
    """
    rows = []
    for i, row in enumerate(data[1:]):  # omite la fila de encabezado
        match_cuenta = (row[0] == selected_cuenta)
        match_sector = (selected_sector == "Todos" or row[1] == selected_sector)
        if match_cuenta and match_sector:
            rows.append(i + 2)  # +2: una por omitir encabezado y el índice empieza en 0
    return rows

# --- FUNCIÓN PARA ACTUALIZAR LAS CELDAS EN BATCH ---
def update_steps(rows, steps_updates, consultoria_value):
    """
    Actualiza en batch los pasos y sus fechas correspondientes, además de la columna de Consultoría.
    Si en la actualización se mantiene "Vacío" se enviará una cadena vacía a la planilla.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cells_to_update = []

    # Actualizar cada paso y su fecha correspondiente
    for step in steps_updates:
        selected_option = step["value"]
        # Si se muestra "Vacío", se enviará una cadena vacía
        update_value = "" if selected_option == "Vacío" else selected_option
        step_col = step["step_col"]
        date_col = step["date_col"]
        for row in rows:
            cells_to_update.append(Cell(row, step_col, update_value))
            # Actualiza la fecha si el avance se indicó
            if update_value in ['Sí', 'Programado', 'Sí (DropControl)', 'Sí (CDTEC IF)']:
                cells_to_update.append(Cell(row, date_col, now))
            else:
                cells_to_update.append(Cell(row, date_col, ''))

    # Actualizar la columna "Consultoría" (Columna C, número 3)
    consultoria_col = 3
    update_consultoria = "" if consultoria_value == "Vacío" else consultoria_value
    for row in rows:
        cells_to_update.append(Cell(row, consultoria_col, update_consultoria))

    try:
        sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
        st.success("✅ Actualización completada correctamente.")
    except Exception as e:
        st.error(f"❌ Error en la actualización en batch: {e}")

# --- FUNCIÓN PRINCIPAL CON INTERFAZ STREAMLIT ---
def main():
    st.title("🟢 Estado de Clientes")

    # Obtener datos de la hoja
    data = get_data()
    if data is None:
        st.stop()

    # Extraer valores únicos para "Cuenta" (columna A)
    unique_cuentas = sorted(set(row[0] for row in data[1:]))

    st.header("Buscar Registro")
    
    # --- Selección de Cuenta ---
    # Permite buscar y seleccionar una cuenta; se agrega la opción "Seleccione una cuenta" por defecto
    search_cuenta = st.text_input("Buscar en Cuenta:", key="buscar_cuenta")
    if search_cuenta:
        filtered_cuentas = [c for c in unique_cuentas if search_cuenta.lower() in c.lower()]
    else:
        filtered_cuentas = unique_cuentas

    if not filtered_cuentas:
        st.error("No se encontró ninguna cuenta que coincida con la búsqueda.")
        st.stop()

    # Se agrega la opción por defecto
    cuentas_options = ["Seleccione una cuenta"] + filtered_cuentas
    selected_cuenta = st.selectbox("Cuenta", cuentas_options, key="cuenta")
    
    # --- Selección de Sector de Riego (solo si se ha seleccionado una cuenta válida) ---
    if selected_cuenta != "Seleccione una cuenta":
        sectores_para_cuenta = [row[1] for row in data[1:] if row[0] == selected_cuenta]
        unique_sectores = sorted(set(sectores_para_cuenta))
    
        search_sector = st.text_input("Buscar en Sector de Riego:", key="buscar_sector")
        if search_sector:
            filtered_sectores = [s for s in unique_sectores if search_sector.lower() in s.lower()]
        else:
            filtered_sectores = unique_sectores

        # Se agrega "Todos" en el selector de sector para poder omitir este filtro si se desea
        selected_sector = st.selectbox("Sector de Riego", ["Todos"] + filtered_sectores, key="sector")
    else:
        selected_sector = "Todos"  # Valor por defecto cuando no se ha seleccionado cuenta

    if st.button("Buscar Registro"):
        if selected_cuenta == "Seleccione una cuenta":
            st.error("❌ Por favor, seleccione una cuenta válida.")
        else:
            rows = find_rows(selected_cuenta, selected_sector, data)
            if not rows:
                st.error("❌ No se encontró ninguna fila con los criterios seleccionados.")
                st.session_state.rows = None
            else:
                st.session_state.rows = rows
                st.success(f"Actualizando: {len(rows)} fila(s).")

    if "rows" not in st.session_state:
        st.session_state.rows = None

    # --- Formulario para Actualizar Datos ---
    if st.session_state.rows:
        st.header("Actualizar Datos")
        with st.form("update_form"):
            # Mapeo de pasos con las columnas correspondientes:
            # Ejemplo: "Ingreso a Planilla Clientes Nuevos": Columna D (4) y Fecha en Columna E (5)
            steps_mapping = [
                {"step_label": "Ingreso a Planilla Clientes Nuevos", "step_col": 4, "date_col": 5},
                {"step_label": "Correo Presentación y Solicitud Información", "step_col": 6, "date_col": 7},
                {"step_label": "Agregar Puntos Críticos", "step_col": 8, "date_col": 9},
                {"step_label": "Generar Capacitación Plataforma", "step_col": 10, "date_col": 11},
                {"step_label": "Generar Documento Power BI", "step_col": 12, "date_col": 13},
                {"step_label": "Generar Capacitación Power BI", "step_col": 14, "date_col": 15},
                {"step_label": "Generar Estrategia de Riego", "step_col": 16, "date_col": 17},
            ]

            # Opciones permitidas para cada paso
            step_options = {
                "Ingreso a Planilla Clientes Nuevos": ['Sí', 'No'],
                "Correo Presentación y Solicitud Información": ['Sí', 'No', 'Programado'],
                "Agregar Puntos Críticos": ['Sí', 'No'],
                "Generar Capacitación Plataforma": ['Sí (DropControl)', 'Sí (CDTEC IF)', 'No', 'Programado'],
                "Generar Documento Power BI": ['Sí', 'No', 'Programado', 'No aplica'],
                "Generar Capacitación Power BI": ['Sí', 'No', 'Programado', 'No aplica'],
                "Generar Estrategia de Riego": ['Sí', 'No', 'Programado', 'No aplica']
            }

            steps_updates = []
            # Por cada paso, se previsualiza la opción actual de la planilla; si está vacía se muestra "Vacío"
            for i, step in enumerate(steps_mapping):
                step_label = step["step_label"]
                default_val = sheet.cell(st.session_state.rows[0], step["step_col"]).value
                if default_val is None or default_val.strip() == "":
                    display_val = "Vacío"
                else:
                    display_val = default_val
                # Si el valor actual no está en la lista de opciones, se agrega al inicio
                options_for_select = step_options[step_label].copy()
                if display_val not in options_for_select:
                    options_for_select = [display_val] + options_for_select
                default_index = options_for_select.index(display_val)
                selected_val = st.selectbox(
                    step_label,
                    options=options_for_select,
                    index=default_index,
                    key=f"step_{i}"
                )
                steps_updates.append({
                    "step_label": step_label,
                    "step_col": step["step_col"],
                    "date_col": step["date_col"],
                    "value": selected_val
                })

            # --- Selección para "Consultoría" (Columna C) ---
            consultoria_default = sheet.cell(st.session_state.rows[0], 3).value
            if consultoria_default is None or consultoria_default.strip() == "":
                display_consultoria = "Vacío"
            else:
                display_consultoria = consultoria_default
            consultoria_options = ["Sí", "No"]
            if display_consultoria not in consultoria_options:
                consultoria_options = [display_consultoria] + consultoria_options
            try:
                consultoria_index = consultoria_options.index(display_consultoria)
            except ValueError:
                consultoria_index = 0
            consultoria_value = st.selectbox("Consultoría", options=consultoria_options, index=consultoria_index)

            submitted = st.form_submit_button("Actualizar")
            if submitted:
                update_steps(st.session_state.rows, steps_updates, consultoria_value)

# --- EJECUCIÓN DE LA FUNCIÓN PRINCIPAL ---
if __name__ == "__main__":
    main()
