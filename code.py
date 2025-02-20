import streamlit as st
import streamlit.components.v1 as components
import gspread
from gspread import Cell
from datetime import datetime
from google.oauth2 import service_account
import os
import json

# Configuración de la página
st.set_page_config(
    page_title="Estado de Clientes",
    page_icon="👥",
    layout="wide"
)

# --- FUNCIÓN DE DEPURACIÓN ---
def debug_secrets():
    """Función para verificar si los secrets están correctamente configurados."""
    try:
        # Intentar acceder a los secrets y mostrar información de depuración
        st.write("### Verificación de Secrets")
        
        # Comprobar si existe el secret spreadsheet_url
        if "spreadsheet_url" in st.secrets:
            st.success(f"✓ Secret 'spreadsheet_url' encontrado: {st.secrets.spreadsheet_url[:20]}...")
        else:
            st.error("✗ Secret 'spreadsheet_url' no encontrado")
            
        # Comprobar si existe la sección gcp_service_account
        if "gcp_service_account" in st.secrets:
            st.success("✓ Secret 'gcp_service_account' encontrado")
            # Verificar las claves necesarias en gcp_service_account
            required_keys = ["type", "project_id", "private_key_id", "private_key", 
                            "client_email", "client_id", "auth_uri", "token_uri"]
            missing_keys = [key for key in required_keys if key not in st.secrets.gcp_service_account]
            
            if missing_keys:
                st.error(f"✗ Faltan las siguientes claves en gcp_service_account: {', '.join(missing_keys)}")
            else:
                st.success("✓ Todas las claves necesarias están presentes en gcp_service_account")
        else:
            st.error("✗ Secret 'gcp_service_account' no encontrado")
            
        return True
    except Exception as e:
        st.error(f"Error al verificar secrets: {str(e)}")
        return False

# --- CONFIGURACIÓN DE LAS CREDENCIALES Y CONEXIÓN A GOOGLE SHEETS ---
def init_connection():
    """Función para inicializar la conexión con Google Sheets."""
    try:
        # Verificar si existe la sección gcp_service_account en secrets
        if "gcp_service_account" not in st.secrets:
            st.error("No se encontró la sección 'gcp_service_account' en secrets")
            st.info("El formato correcto de secrets.toml debería ser:")
            st.code("""
            spreadsheet_url = "https://docs.google.com/spreadsheets/d/..."
            
            [gcp_service_account]
            type = "service_account"
            project_id = "..."
            private_key_id = "..."
            private_key = "..."
            client_email = "..."
            client_id = "..."
            auth_uri = "..."
            token_uri = "..."
            auth_provider_x509_cert_url = "..."
            client_x509_cert_url = "..."
            """)
            return None
            
        # Convertir la estructura st.secrets.gcp_service_account a un diccionario
        service_account_info = dict(st.secrets.gcp_service_account)
        
        # Obtener credenciales de secrets
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error en la conexión: {str(e)}")
        return None

def load_sheet(client):
    """Función para cargar la hoja de trabajo de Google Sheets."""
    try:
        if "spreadsheet_url" not in st.secrets:
            st.error("No se encontró 'spreadsheet_url' en secrets")
            return None
            
        spreadsheet_url = st.secrets.spreadsheet_url
        return client.open_by_url(spreadsheet_url).sheet1
    except Exception as e:
        st.error(f"Error al cargar la planilla: {str(e)}")
        return None

# --- FUNCIÓN PRINCIPAL CON INTERFAZ STREAMLIT ---
def main():
    st.title("📌 Estado de Clientes")
    
    # Botón para mostrar información de depuración
    if st.button("Diagnosticar Configuración"):
        debug_secrets()
    
    # Inicialización con conexión a Google Sheets
    client = init_connection()
    sheet = None if client is None else load_sheet(client)
    
    # Mostrar instrucciones de configuración si no hay conexión
    if sheet is None:
        st.warning("⚠️ Configuración incompleta")
        st.info("""
        Para usar esta aplicación, necesita configurar correctamente el archivo `.streamlit/secrets.toml`:
        
        ```toml
        spreadsheet_url = "https://docs.google.com/spreadsheets/d/..."
        
        [gcp_service_account]
        type = "service_account"
        project_id = "..."
        private_key_id = "..."
        private_key = "..."
        client_email = "..."
        client_id = "..."
        auth_uri = "..."
        token_uri = "..."
        auth_provider_x509_cert_url = "..."
        client_x509_cert_url = "..."
        ```
        
        Asegúrese de que:
        1. La estructura del archivo es correcta (con la sección [gcp_service_account])
        2. El formato TOML es válido (sin errores de sintaxis)
        3. La URL de la hoja de cálculo es accesible
        4. Las credenciales de servicio tienen permisos adecuados
        
        Para más información: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
        """)
        st.stop()
    
    # Si llegamos aquí, tenemos una conexión exitosa
    st.success("✅ Conexión establecida con Google Sheets")
    
    # Resto del código de la aplicación (versión simplificada para ejemplo)
    try:
        # Obtener los datos de la hoja
        data = sheet.get_all_values()
        st.write(f"Datos recuperados: {len(data)} filas")
        
        # Mostrar un preview de los datos
        if len(data) > 1:
            st.write("Vista previa de datos:")
            headers = data[0]
            preview_data = data[1:min(4, len(data))]
            
            # Crear una tabla para mostrar los datos
            table_data = [headers] + preview_data
            st.table(table_data)
    except Exception as e:
        st.error(f"Error al procesar datos: {str(e)}")

if __name__ == "__main__":
    main()
