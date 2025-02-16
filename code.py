import streamlit as st
import gspread
from gspread import Cell
from datetime import datetime
from google.oauth2.service_account import Credentials

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

# --- FUNCIONES AUXILIARES ---

def get_data():
    """Obtiene todos los valores de la hoja."""
    try:
        return sheet.get_all_values()
    except Exception as e:
        st.error(f"❌ Error al obtener los datos: {e}")
        return None

def find_rows(option, id_value, data):
    """
    Busca filas por N° Cuenta o N° Sector de Riego.
    Si option es 'Cuenta', se busca en la primera columna (índice 0);
    si es 'Campo', se busca en la columna 3 (índice 2).
    Retorna una lista con el número de fila (contando desde 1) de cada coincidencia.
    """
    column_index = 0 if option == 'Cuenta' else 2  
    return [i + 2 for i, row in enumerate(data[1:]) if row[column_index] == id_value]

def update_steps(rows, steps_updates, consultoria_value):
    """
    Actualiza en batch las celdas correspondientes a cada paso y a la fecha,
    y además actualiza la columna "Consultoría" (columna 4).
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cells_to_update = []

    # Actualizar cada paso y la fecha asociada
    for step in steps_updates:
        selected_option = step["value"]
        col = step["col"]
        date_col = step["date_col"]
        for row in rows:
            cells_to_update.append(Cell(row, col, selected_option))
            # Si el valor seleccionado indica avance, se actualiza la fecha; de lo contrario se limpia
            if selected_option in ['Sí', 'Programado', 'DropControl', 'CDTEC IF']:
                cells_to_update.append(Cell(row, date_col, now))
            elif selected_option in ['No', 'No aplica']:
                cells_to_update.append(Cell(row, date_col, ''))

    # Actualizar la columna "Consultoría" (columna 4)
    consultoria_col = 4
    for row in rows:
        cells_to_update.append(Cell(row, consultoria_col, consultoria_value))

    try:
        sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
        st.success("✅ Actualización completada correctamente.")
    except Exception as e:
        st.error(f"❌ Error en la actualización en batch: {e}")

# --- FUNCIÓN PRINCIPAL CON INTERFAZ STREAMLIT ---

def main():
    st.title("Actualizador de Planilla (Batch Update)")
    
    # Obtener datos de la hoja
    data = get_data()
    if data is None:
        st.stop()

    # Usar st.session_state para mantener las filas encontradas entre interacciones
    if "rows" not in st.session_state:
        st.session_state.rows = None

    st.header("Buscar Registro")
    option = st.selectbox("Selecciona el tipo de ID", ["Cuenta", "Campo"])
    id_value = st.text_input(f"Ingresa la ID de {option}:")

    if st.button("Buscar Registro"):
        rows = find_rows(option, id_value, data)
        if not rows:
            st.error(f"❌ No se encontró ninguna fila con esa ID de {option}.")
            st.session_state.rows = None
        else:
            st.session_state.rows = rows
            if option == "Cuenta":
                st.warning("⚠️ ADVERTENCIA: Se actualizarán todas las filas asociadas a la ID de la cuenta seleccionada.")
            st.success(f"Se encontró(n) {len(rows)} fila(s).")

    # Si se encontraron filas, se muestra el formulario para actualizar
    if st.session_state.rows:
        st.header("Actualizar Pasos")
        with st.form("update_form"):
            # Definir columnas para los pasos y sus columnas de fecha (contando desde 1)
            step_columns = [5, 7, 9, 11, 13, 15, 17]       # Columnas de los pasos
            date_columns = [6, 8, 10, 12, 14, 16, 18]        # Columnas de las fechas
            consultoria_col = 4                             # Columna de "Consultoría"

            # Opciones para cada paso
            step_options = {
                "Ingreso a Planilla Clientes Nuevos": ['Sí', 'No'],
                "Correo Presentación y Solicitud Información": ['Sí', 'No', 'Programado'],
                "Agregar Puntos Críticos": ['Sí', 'No'],
                "Generar Capacitación Plataforma": ['DropControl', 'CDTEC IF', 'No', 'Programado'],
                "Generar Documento Power BI": ['Sí', 'No', 'Programado', 'No aplica'],
                "Generar Capacitación Power BI": ['Sí', 'No', 'Programado', 'No aplica'],
                "Generar Estrategia de Riego": ['Sí', 'No', 'Programado', 'No aplica']
            }

            steps_updates = []
            # Por cada columna de paso, se obtiene el label desde el encabezado y se crea un selectbox
            for i, col in enumerate(step_columns):
                step_label = sheet.cell(1, col).value  # Encabezado de la columna
                if step_label not in step_options:
                    st.warning(f"❌ Advertencia: '{step_label}' no está en las opciones definidas. Se omitirá.")
                    continue
                # Obtener valor por defecto de la primera fila encontrada
                default_val = sheet.cell(st.session_state.rows[0], col).value
                try:
                    default_index = step_options[step_label].index(default_val)
                except ValueError:
                    default_index = 0
                selected_val = st.selectbox(
                    step_label,
                    options=step_options[step_label],
                    index=default_index,
                    key=f"step_{i}"
                )
                steps_updates.append({
                    "step_label": step_label,
                    "col": col,
                    "date_col": date_columns[i],
                    "value": selected_val
                })

            # Selectbox para "Consultoría"
            consultoria_default = sheet.cell(st.session_state.rows[0], consultoria_col).value
            consultoria_options = ["Sí", "No"]
            try:
                consultoria_index = consultoria_options.index(consultoria_default)
            except ValueError:
                consultoria_index = 0
            consultoria_value = st.selectbox("Consultoría", options=consultoria_options, index=consultoria_index)

            submitted = st.form_submit_button("Actualizar")
            if submitted:
                update_steps(st.session_state.rows, steps_updates, consultoria_value)

# --- EJECUCIÓN DE LA FUNCIÓN PRINCIPAL ---
if __name__ == "__main__":
    main()
