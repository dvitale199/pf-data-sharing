import streamlit as st
import os
import logging
from typing import Dict, Any

# Import services
from src.core.services.gcs_service import GCSService
from src.core.services.email_service import EmailService
from src.core.services.tracking_service import TrackingService

# Import utilities
from src.core.utils.auth import AuthUtils
from src.core.utils.file_operations import FileOperations

# Import UI components
from src.core.components.single_sample import render_single_sample_component
from src.core.components.multi_sample import render_multi_sample_component
from src.core.components.tracking import render_tracking_component

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# App title and configuration
st.set_page_config(
    page_title="GCP Data Sharing Portal",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Application state management
@st.cache_resource
def init_services() -> Dict[str, Any]:
    """Initialize and cache service instances"""
    try:
        # Initialize authentication
        auth = AuthUtils()
        valid_auth, error_msg = auth.verify_gcp_credentials()
        
        if not valid_auth:
            return {"error": error_msg}
        
        # Initialize services
        gcs_service = GCSService()
        tracking_service = TrackingService(gcs_service)
        email_service = EmailService()
        file_ops = FileOperations(gcs_service)
        
        # Get current project
        project_id = auth.get_current_project()
        
        return {
            "auth": auth,
            "gcs_service": gcs_service,
            "email_service": email_service,
            "tracking_service": tracking_service,
            "file_ops": file_ops,
            "project_id": project_id,
            "error": None
        }
    except Exception as e:
        logging.error(f"Error initializing services: {str(e)}")
        return {"error": f"Error initializing application: {str(e)}"}

def main():
    """Main application entry point"""
    # App title
    st.title("GCP Data Sharing Portal")
    
    # Initialize services
    services = init_services()
    
    if services.get("error"):
        st.error(services["error"])
        st.stop()
    
    # Extract initialized services
    auth = services["auth"]
    gcs_service = services["gcs_service"]
    email_service = services["email_service"]
    tracking_service = services["tracking_service"]
    file_ops = services["file_ops"]
    project_id = services["project_id"]
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Home", "Share Single Sample", "Share Multiple Samples", "Track & Manage"]
    )
    
    # Source bucket configuration - get from environment variable only
    source_bucket = os.environ.get("DEFAULT_SOURCE_BUCKET", "")
    
    # Render the selected page
    if page == "Home":
        render_home_page(source_bucket)
    elif page == "Share Single Sample":
        if not source_bucket:
            st.error("Please configure a source bucket in the sidebar first.")
        else:
            render_single_sample_component(
                gcs_service, email_service, tracking_service, file_ops, source_bucket
            )
    elif page == "Share Multiple Samples":
        if not source_bucket:
            st.error("Please configure a source bucket in the sidebar first.")
        else:
            render_multi_sample_component(
                gcs_service, email_service, tracking_service, file_ops, source_bucket
            )
    elif page == "Track & Manage":
        render_tracking_component(tracking_service, gcs_service)

def render_home_page(source_bucket: str):
    """Render the home page with instructions and status"""
    st.header("Welcome to the GCP Data Sharing Portal")
    
    st.markdown("""
    This application allows you to easily share data from GCP buckets with specific recipients:
    
    1. **Share Single Sample** - Create a zip file of a sample and share via email with a signed URL
    2. **Share Multiple Samples** - Copy multiple samples to a new bucket and share access via email
    3. **Track & Manage** - Monitor all shared samples and manage their lifecycle
    
    All shared data is automatically deleted after a configurable expiration period.
    """)

if __name__ == "__main__":
    main() 