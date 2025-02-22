import streamlit as st
import streamlit.components.v1 as components
import gspread
from gspread import Cell
from datetime import datetime
from google.oauth2.service_account import Credentials
import time
import pandas as pd

# Configuración de la página
st.set_page_config(
    page_title="Estado de Clientes",
    page_icon="👥",
    layout="wide"
)

# Configuración: URL de la hoja de cálculo
SPREADSHEET_URL = st.secrets["spreadsheet_url"]

# Función para reiniciar la búsqueda
def reset_search():
    st.session_state.rows = None

# Configuración de credenciales
scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope
)
gc = gspread.authorize(credentials)
sheet = gc.open_by_url(SPREADSHEET_URL).sheet1

# Manejo de errores de API
def handle_quota_error(e):
    error_str = str(e).lower()
    if "quota" in error_str or "limit" in error_str:
        st.error("❌ Límite de API alcanzado. Reiniciando...")
        time.sleep(1)
        st.rerun()

# Obtener datos con caché
@st.cache_data(ttl=60)
def get_data():
    try:
        return sheet.get_all_values()
    except Exception as e:
        handle_quota_error(e)
        st.error(f"❌ Error: {e}")
        return None

# Buscar filas según cuenta y sectores seleccionados
def find_rows(selected_cuenta, selected_sectores, data):
    rows = []
    for i, row in enumerate(data[1:]):
        match_cuenta = (row[0] == selected_cuenta)
        match_sector = (len(selected_sectores) == 0 or row[1] in selected_sectores)
        if match_cuenta and match_sector:
            rows.append(i + 2)
    return rows

# Actualizar celdas
def update_steps(rows, steps_updates, consultoria_value, comentarios_value):
    now = datetime.now().strftime('%d-%m-%y %H:%M')
    cells_to_update = []

    # Actualizar Consultoría
    consultoria_col = 3
    update_consultoria = "" if consultoria_value == "Vacío" else consultoria_value
    for row in rows:
        cells_to_update.append(Cell(row, consultoria_col, update_consultoria))

    # Actualizar pasos
    for step in steps_updates:
        selected_option = step["value"]
        update_value = "" if selected_option == "Vacío" else selected_option
        step_col = step["step_col"]
        date_col = step["date_col"]
        for row in rows:
            cells_to_update.append(Cell(row, step_col, update_value))
            # Actualizar fecha si hay avance
            if update_value in ['Sí', 'Programado', 'Sí (DropControl)', 'Sí (CDTEC IF)']:
                cells_to_update.append(Cell(row, date_col, now))
            else:
                cells_to_update.append(Cell(row, date_col, ''))

    # Actualizar Comentarios
    comentarios_col = 18
    for row in rows:
        cells_to_update.append(Cell(row, comentarios_col, comentarios_value))

    # Actualizar fecha de última modificación
    ultima_actualizacion_col = 19
    for row in rows:
        cells_to_update.append(Cell(row, ultima_actualizacion_col, now))

    try:
        sheet.update_cells(cells_to_update, value_input_option='USER_ENTERED')
        st.success("✅ Cambios guardados.")
        # Invalidar caché para forzar la recarga de datos
        st.cache_data.clear()
        return True
    except Exception as e:
        handle_quota_error(e)
        st.error(f"❌ Error: {e}")
        return False

# Obtener color según estado
def get_state_color(state):
    colors = {
        'Sí': '#4CAF50',  # Verde
        'No': '#F44336',  # Rojo
        'Programado': '#FFC107',  # Amarillo
        'No aplica': '#9E9E9E',  # Gris
        'Sí (DropControl)': '#2196F3',  # Azul
        'Sí (CDTEC IF)': '#673AB7',  # Morado
        'Vacío': '#E0E0E0',  # Gris claro
    }
    return colors.get(state, '#E0E0E0')

# Función principal
def main():
    st.title("📌 Estado de Clientes")
    
    # Botón para abrir planilla
    html_button = f"""
    <div style="text-align: left; margin-bottom: 10px;">
        <a href="{SPREADSHEET_URL}" target="_blank">
            <button style="
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
                border-radius: 5px;
                cursor: pointer;">
                Abrir Planilla de Google
            </button>
        </a>
    </div>
    """
    components.html(html_button, height=50)

    # Inyectar CSS global para reducir márgenes en headers y contenedores
    st.markdown(
        """
        <style>
        h1, h2, h3, h4, h5, h6 {
            margin-top: 10px;
            margin-bottom: 5px;
        }
        .stApp {
            padding-bottom: 0px;
            margin-bottom: 0px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Inicializar estado de actualizaciones
    if "update_successful" not in st.session_state:
        st.session_state.update_successful = False

    # Cargar datos - siempre cargar datos frescos si hubo una actualización exitosa
    if "data" not in st.session_state or st.session_state.update_successful:
        st.session_state.data = get_data()
        st.session_state.update_successful = False
    data = st.session_state.data

    if data is None:
        st.stop()

    # Extraer cuentas únicas
    unique_cuentas = sorted(set(row[0] for row in data[1:]))

    st.header("Buscar Registro")
    
    # Selección de Cuenta
    cuentas_options = ["Seleccione una cuenta"] + unique_cuentas
    selected_cuenta = st.selectbox("Cuenta", cuentas_options, key="cuenta", on_change=reset_search)
    
    # Selección múltiple de Sectores
    if selected_cuenta != "Seleccione una cuenta":
        sectores_para_cuenta = [row[1] for row in data[1:] if row[0] == selected_cuenta]
        unique_sectores = sorted(set(sectores_para_cuenta))
        
        # Inicializar sectores seleccionados en session_state si no existe
        if "selected_sectores" not in st.session_state:
            st.session_state.selected_sectores = []
            
        st.write("Sectores de Riego (seleccione uno o varios):")
        
        # Contenedor para los checkboxes
        checkbox_container = st.container()

        # Botón "Seleccionar Todos" arriba con ancho completo
        if st.button("Seleccionar Todos", use_container_width=True):
            st.session_state.selected_sectores = unique_sectores.copy()
            st.rerun()
        
        # Mostrar checkboxes para sectores
        with checkbox_container:
            for sector in unique_sectores:
                sector_checked = st.checkbox(sector, key=f"sector_{sector}", 
                                             value=sector in st.session_state.selected_sectores)
                if sector_checked and sector not in st.session_state.selected_sectores:
                    st.session_state.selected_sectores.append(sector)
                elif not sector_checked and sector in st.session_state.selected_sectores:
                    st.session_state.selected_sectores.remove(sector)
        
        # Botón "Deseleccionar Todos" abajo con ancho completo
        if st.button("Deseleccionar Todos", use_container_width=True):
            st.session_state.selected_sectores = []
            st.rerun()
    else:
        st.session_state.selected_sectores = []

    # Botón para Buscar Registro (con tipo primary)
    if st.button("Buscar Registro", type="primary", use_container_width=True):
        if selected_cuenta == "Seleccione una cuenta":
            st.error("❌ Seleccione una cuenta válida.")
            st.session_state.rows = None
        elif not st.session_state.selected_sectores:
            st.warning("⚠️ No hay sectores seleccionados. Se mostrarán todos los sectores para esta cuenta.")
            rows = find_rows(selected_cuenta, [], data)
            if not rows:
                st.error("❌ No se encontraron registros.")
                st.session_state.rows = None
            else:
                st.session_state.rows = rows
                st.success(f"Se actualizarán {len(rows)} sector(es).")
        else:
            rows = find_rows(selected_cuenta, st.session_state.selected_sectores, data)
            if not rows:
                st.error("❌ No se encontraron registros.")
                st.session_state.rows = None
            else:
                st.session_state.rows = rows
                st.success(f"Se actualizarán {len(rows)} sector(es).")

    if "rows" not in st.session_state:
        st.session_state.rows = None

    # Mostrar tabla "Estado Actual" con colores
    if st.session_state.rows is not None:
        st.header("Estado Actual")
        
        # Preparar datos para la tabla
        table_data = []
        headers = ["Cuenta", "Sector", "Consultoría", 
                   "Ingreso a Planilla", "Correo Presentación", 
                   "Puntos Críticos", "Capacitación Plataforma", 
                   "Documento Power BI", "Capacitación Power BI", 
                   "Estrategia de Riego", "Última Actualización"]
        
        for row_index in st.session_state.rows:
            row = data[row_index - 1]  # Ajuste de índice
            row_data = [
                row[0],  # Cuenta
                row[1],  # Sector
                row[2],  # Consultoría
                row[3],  # Ingreso a Planilla
                row[5],  # Correo Presentación
                row[7],  # Puntos Críticos
                row[9],  # Capacitación Plataforma
                row[11], # Documento Power BI
                row[13], # Capacitación Power BI
                row[15], # Estrategia de Riego
                row[18] if len(row) > 18 else "",  # Última Actualización
            ]
            table_data.append(row_data)
        
        # Crear DataFrame
        df = pd.DataFrame(table_data, columns=headers)
        
        # Se usa X px de altura por defecto y si el contenido es mayor se extiende a Y px.
        html_table = f"""
        <style>
        .status-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        .status-table th, .status-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }}
        .status-table th {{
            background-color: #f2f2f2;
            position: sticky;
            top: 0;
            margin: 0;
            padding: 8px;
        }}
        .status-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .status-cell {{
            border-radius: 4px;
            color: white;
            padding: 4px 8px;
            display: inline-block;
            width: 90%;
            text-align: center;
        }}
        .date-cell {{
            font-size: 0.85em;
            color: #333;
        }}
        </style>
        <div id="estado_actual">
        <table class="status-table">
            <thead>
                <tr>
        """
        
        # Añadir encabezados
        for header in headers:
            html_table += f"<th>{header}</th>"
        
        html_table += """
                </tr>
            </thead>
            <tbody>
        """
        
        # Añadir filas con colores
        for _, row in df.iterrows():
            html_table += "<tr>"
            for i, cell in enumerate(row):
                if i <= 1:  # Cuenta y Sector sin formato
                    html_table += f"<td>{cell}</td>"
                elif i == len(row) - 1:  # Última columna (fecha de actualización)
                    html_table += f'<td><div class="date-cell">{cell}</div></td>'
                else:
                    cell_value = cell if cell and cell.strip() != "" else "Vacío"
                    color = get_state_color(cell_value)
                    html_table += f"""
                    <td>
                        <div class="status-cell" style="background-color: {color};">
                            {cell_value}
                        </div>
                    </td>
                    """
            html_table += "</tr>"
        
        html_table += """
            </tbody>
        </table>
        </div>
        <script>
          function resizeEstado() {
              var el = document.getElementById("estado_actual");
              var scrollHeight = el.scrollHeight;
              var newHeight = (scrollHeight > 100) ? 100 : 1000;
              if(window.Streamlit) {
                  Streamlit.setFrameHeight(newHeight);
              }
          }
          window.addEventListener('load', resizeEstado);
          window.addEventListener('resize', resizeEstado);
          resizeEstado();
        </script>
        """
        st.components.v1.html(html_table, scrolling=True)

        # Sección: Comentarios por Sector
        st.subheader("Comentarios por Sector")
        
        # Preparar datos para la tabla de comentarios
        comentarios_data = {}
        sectores_encontrados = []
        
        for row_index in st.session_state.rows:
            row = data[row_index - 1]  # Ajuste de índice
            sector = row[1]
            comentario = row[17] if len(row) > 17 and row[17] else "Sin comentarios"
            sectores_encontrados.append(sector)
            comentarios_data[sector] = comentario
        
        # Ordenar sectores alfabéticamente
        sectores_encontrados = sorted(set(sectores_encontrados))
        
        # HTML para la tabla de comentarios con CSS ajustado y sistema dinámico:
        html_comentarios = f"""
        <style>
        .comments-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        .comments-table th, .comments-table td {{
            border: 1px solid #ddd;
            padding: 8px;
        }}
        .comments-table th {{
            background-color: #f2f2f2;
            text-align: center;
            font-weight: bold;
            position: sticky;
            top: 0;
            z-index: 10;
            margin: 0;
            padding: 8px;
        }}
        .comments-table td {{
            text-align: left;
            vertical-align: top;
            background-color: #f9f9f9;
        }}
        </style>
        <div id="comentarios">
        <table class="comments-table">
            <thead>
                <tr>
        """
        
        # Añadir encabezados (sectores)
        for sector in sectores_encontrados:
            html_comentarios += f"<th>{sector}</th>"
        
        html_comentarios += """
                </tr>
            </thead>
            <tbody>
                <tr>
        """
        
        # Añadir comentarios
        for sector in sectores_encontrados:
            comentario = comentarios_data.get(sector, "Sin comentarios")
            html_comentarios += f"<td>{comentario}</td>"
        
        html_comentarios += """
                </tr>
            </tbody>
        </table>
        </div>
        <script>
          function resizeComentarios() {
              var el = document.getElementById("comentarios");
              var scrollHeight = el.scrollHeight;
              var newHeight = (scrollHeight > 60) ? 90 : 60;
              if(window.Streamlit) {
                  Streamlit.setFrameHeight(newHeight);
              }
          }
          window.addEventListener('load', resizeComentarios);
          window.addEventListener('resize', resizeComentarios);
          resizeComentarios();
        </script>
        """
        st.components.v1.html(html_comentarios, scrolling=True)

        # Mostrar formulario de actualización
        st.header("Actualizar Registro")
        fila_index = st.session_state.rows[0] - 1
        fila_datos = data[fila_index]

        with st.form("update_form"):
            # 1. Consultoría
            consultoria_default = fila_datos[2] if len(fila_datos) >= 3 else ""
            display_consultoria = consultoria_default.strip() if consultoria_default and consultoria_default.strip() != "" else "Vacío"
            consultoria_options = ["Sí", "No"]
            if display_consultoria not in consultoria_options:
                consultoria_options = [display_consultoria] + consultoria_options
            try:
                consultoria_index = consultoria_options.index(display_consultoria)
            except ValueError:
                consultoria_index = 0
            consultoria_value = st.selectbox("Consultoría", options=consultoria_options, index=consultoria_index)

            # 2. Pasos a actualizar (en una sola columna)
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
                col_index = step["step_col"] - 1
                default_val = fila_datos[col_index] if len(fila_datos) > col_index else ""
                display_val = default_val.strip() if default_val and default_val.strip() != "" else "Vacío"
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

            # 3. Comentarios
            comentarios_default = fila_datos[17] if len(fila_datos) >= 18 else ""
            comentarios_value = st.text_area("Comentarios", value=comentarios_default if comentarios_default is not None else "")

            submitted = st.form_submit_button("Guardar Cambios", type="primary")
            if submitted:
                success = update_steps(st.session_state.rows, steps_updates, consultoria_value, comentarios_value)
                if success:
                    # Marcar que se realizó una actualización exitosa para recargar datos
                    st.session_state.update_successful = True
                    st.rerun()

if __name__ == "__main__":
    main()
