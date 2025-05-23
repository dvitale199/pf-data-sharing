import os
import logging
import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import storage
from typing import Optional, Tuple

class AuthUtils:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def verify_gcp_credentials(self) -> Tuple[bool, Optional[str]]:
        """
        Verify GCP credentials are available and valid
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Try to get default credentials
            credentials, project = google.auth.default()
            
            # Test if we can list buckets
            client = storage.Client(credentials=credentials, project=project)
            next(client.list_buckets(max_results=1), None)
            
            return True, None
            
        except DefaultCredentialsError:
            error_msg = ("GCP credentials not found. Set GOOGLE_APPLICATION_CREDENTIALS "
                         "environment variable or run 'gcloud auth application-default login'")
            self.logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Error verifying GCP credentials: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def get_current_project(self) -> Optional[str]:
        """
        Get the current GCP project ID
        
        Returns:
            The project ID or None if not available
        """
        try:
            _, project = google.auth.default()
            return project
        except Exception as e:
            self.logger.error(f"Error getting current project: {str(e)}")
            return None
    
    def get_current_user_email(self) -> Optional[str]:
        """
        Get the current user's email if available
        
        Returns:
            The user email or None if not available
        """
        try:
            credentials, _ = google.auth.default()
            if hasattr(credentials, 'service_account_email'):
                return credentials.service_account_email
                
            # For user credentials, this information might not be available
            return None
        except Exception as e:
            self.logger.error(f"Error getting user email: {str(e)}")
            return None 