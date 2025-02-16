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
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope
)
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
    rows = []
    for i, row in enumerate(data[1:]):  # Se omite la fila de encabezado
        match_cuenta = (row[0] == selected_cuenta)
        match_sector = (selected_sector == "Todos" or row[1] == selected_sector)
        if match_cuenta and match_sector:
            rows.append(i + 2)  # +2 para omitir encabezado y ajustar índice (base 1)
    return rows

# --- FUNCIÓN PARA ACTUALIZAR CELDAS (Consultoría, Pasos y Comentarios) ---
def update_steps(rows, steps_updates, consultoria_value, comentarios_value):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cells_to_update = []

    # Actualizar Consultoría (Columna C)
    consultoria_col = 3
    update_consultoria = "" if consultoria_value == "Vacío" else consultoria_value
    for row in rows:
        cells_to_update.append(Cell(row, consultoria_col, update_consultoria))

    # Actualizar cada paso y su fecha (según corresponda)
    for step in steps_updates:
        selected_option = step["value"]
        update_value = "" if selected_option == "Vacío" else selected_option
        step_col = step["step_col"]
        date_col = step["date_col"]
        for row in rows:
            cells_to_update.append(Cell(row, step_col, update_value))
            # Si se registró un avance, se actualiza la fecha
            if update_value in ['Sí', 'Programado', 'Sí (DropControl)', 'Sí (CDTEC IF)']:
                cells_to_update.append(Cell(row, date_col, now))
            else:
                cells_to_update.append(Cell(row, date_col, ''))

    # Actualizar Comentarios (Columna R, número 18)
    comentarios_col = 18
    for row in rows:
        cells_to_update.append(Cell(row, comentarios_col, comentarios_value))

    # Actualizar Última Actualización (Columna S, número 19)
    ultima_actualizacion_col = 19
    for row in rows:
        cells_to_update.append(Cell(row, ultima_actualizacion_col, now))

    try:
        sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
        st.success("✅ Se guardaron los cambios correctamente.")
    except Exception as e:
        st.error(f"❌ Error en la actualización en batch: {e}")

# --- FUNCIÓN PRINCIPAL CON INTERFAZ STREAMLIT ---
def main():
    st.title("📌 Estado de Clientes")

    # Obtener datos de la hoja
    data = get_data()
    if data is None:
        st.stop()

    # Extraer cuentas únicas (Columna A)
    unique_cuentas = sorted(set(row[0] for row in data[1:]))

    st.header("Buscar Registro")
    
    # --- Selección de Cuenta ---
    cuentas_options = ["Seleccione una cuenta"] + unique_cuentas
    selected_cuenta = st.selectbox("Cuenta", cuentas_options, key="cuenta")
    
    # --- Selección de Sector de Riego (solo si se ha seleccionado una cuenta válida) ---
    if selected_cuenta != "Seleccione una cuenta":
        sectores_para_cuenta = [row[1] for row in data[1:] if row[0] == selected_cuenta]
        unique_sectores = sorted(set(sectores_para_cuenta))
        selected_sector = st.selectbox("Sector de Riego", ["Todos"] + unique_sectores, key="sector")
    else:
        selected_sector = "Todos"

    # --- Botón para Buscar Registro ---
    if st.button("Buscar Registro"):
        if selected_cuenta == "Seleccione una cuenta":
            st.error("❌ Por favor, seleccione una cuenta válida.")
            st.session_state.rows = None
        else:
            rows = find_rows(selected_cuenta, selected_sector, data)
            if not rows:
                st.error("❌ No se encontró ninguna fila con los criterios seleccionados.")
                st.session_state.rows = None
            else:
                st.session_state.rows = rows
                st.success(f"Se actualizarán en el registro: {len(rows)} fila(s).")

    if "rows" not in st.session_state:
        st.session_state.rows = None

    # --- Mostrar el Formulario para Actualizar Datos solo si se obtuvo un registro ---
    if st.session_state.rows is not None:
        st.header("Registro:")
        with st.form("update_form"):
            # 1. Consultoría (Columna C)
            consultoria_default = sheet.cell(st.session_state.rows[0], 3).value
            display_consultoria = (
                consultoria_default.strip() if consultoria_default and consultoria_default.strip() != "" else "Vacío"
            )
            consultoria_options = ["Sí", "No"]
            if display_consultoria not in consultoria_options:
                consultoria_options = [display_consultoria] + consultoria_options
            try:
                consultoria_index = consultoria_options.index(display_consultoria)
            except ValueError:
                consultoria_index = 0
            consultoria_value = st.selectbox("Consultoría", options=consultoria_options, index=consultoria_index)

            # 2. Pasos a actualizar (en el orden indicado)
            steps_mapping = [
                {"step_label": "Ingreso a Planilla Clientes Nuevos", "step_col": 4, "date_col": 5},
                {"step_label": "Correo Presentación y Solicitud Información", "step_col": 6, "date_col": 7},
                {"step_label": "Agregar Puntos Críticos", "step_col": 8, "date_col": 9},
                {"step_label": "Generar Capacitación Plataforma", "step_col": 10, "date_col": 11},
                {"step_label": "Generar Documento Power BI", "step_col": 12, "date_col": 13},
                {"step_label": "Generar Capacitación Power BI", "step_col": 14, "date_col": 15},
                {"step_label": "Generar Estrategia de Riego", "step_col": 16, "date_col": 17},
            ]
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
            for i, step in enumerate(steps_mapping):
                step_label = step["step_label"]
                default_val = sheet.cell(st.session_state.rows[0], step["step_col"]).value
                display_val = (
                    default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
                )
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

            # 3. Comentarios (Columna R, número 18)
            comentarios_default = sheet.cell(st.session_state.rows[0], 18).value
            comentarios_value = st.text_area(
                "Comentarios", value=comentarios_default if comentarios_default is not None else ""
            )

            submitted = st.form_submit_button("Guardar Cambios")
            if submitted:
                update_steps(st.session_state.rows, steps_updates, consultoria_value, comentarios_value)

if __name__ == "__main__":
    main()
