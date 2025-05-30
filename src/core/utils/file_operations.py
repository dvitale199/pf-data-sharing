import logging
import os
import csv
import zipfile
import tempfile
from typing import List, Tuple
from ..services.gcs_service import GCSService

class FileOperations:
    def __init__(self, gcs_service: GCSService):
        """Initialize with a GCS service instance"""
        self.gcs_service = gcs_service
        self.logger = logging.getLogger(__name__)
        # Hard-coded gcsfuse mount path
        self.gcsfuse_mount_path = "/mnt/gcs"
        
    def create_zip_from_gcsfuse(self, bucket_name: str, sample_id: str) -> Tuple[str, int]:
        """
        Create a zip file on disk from files in gcsfuse mount
        
        Args:
            bucket_name: The bucket name
            sample_id: The sample ID
            
        Returns:
            Tuple of (path to zip file, number of files included)
        """
        # Get the gcsfuse path for the sample
        sample_path = self.get_sample_path(bucket_name, sample_id)
        
        # Create a temporary file for the zip
        with tempfile.NamedTemporaryFile(mode='w', suffix='.zip', delete=False) as tmp_file:
            zip_path = tmp_file.name
        
        file_count = 0
        
        # Create the zip file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Walk through all files in the sample directory
            for root, dirs, files in os.walk(sample_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate the archive name (relative path within the zip)
                    arcname = os.path.relpath(file_path, sample_path)
                    try:
                        zip_file.write(file_path, arcname)
                        file_count += 1
                        self.logger.info(f"Added {arcname} to zip")
                    except Exception as e:
                        self.logger.error(f"Error adding {file_path} to zip: {str(e)}")
        
        return zip_path, file_count
        
    def process_batch_file(self, file_obj, has_header: bool = True) -> List[str]:
        """
        Process a batch file (CSV or TXT) containing sample IDs
        
        Args:
            file_obj: File-like object containing the batch data
            has_header: Whether the file has a header row
            
        Returns:
            List of sample IDs
        """
        sample_ids = []
        
        # Reset file pointer to beginning
        file_obj.seek(0)
        
        # Try to determine file type from content
        content = file_obj.read(1024).decode('utf-8')
        file_obj.seek(0)
        
        # Check if it's CSV or simple text
        if ',' in content:
            reader = csv.reader(file_obj)
            if has_header:
                next(reader)  # Skip header
            for row in reader:
                if row and row[0].strip():
                    sample_ids.append(row[0].strip())
        else:
            # Treat as simple text file with one sample per line
            for line in file_obj:
                sample_id = line.decode('utf-8').strip()
                if sample_id:
                    sample_ids.append(sample_id)
        
        return sample_ids
    
    def get_sample_path(self, bucket_name: str, sample_id: str) -> str:
        """
        Get the full gcsfuse path for a sample
        
        Args:
            bucket_name: The bucket name
            sample_id: The sample ID
            
        Returns:
            Full path to the sample directory
        """
        return os.path.join(self.gcsfuse_mount_path, bucket_name, "FulgentTF", sample_id)
    
    def clean_filename(self, filename: str) -> str:
        """
        Clean a filename to ensure it's valid for GCS
        
        Args:
            filename: Original filename
            
        Returns:
            Cleaned filename
        """
        # Replace problematic characters
        cleaned = filename.replace('/', '_').replace(' ', '_')
        return cleaned 

    def upload_zip_to_gcsfuse(self, bucket_name: str, sample_id: str, zip_path: str) -> str:
        """
        Upload zip file directly through gcsfuse mount
        
        Returns:
            The relative path of the uploaded file in the bucket
        """
        import uuid
        import shutil
        
        try:
            # Create unique filename
            unique_id = uuid.uuid4().hex[:8]
            zip_filename = f"{sample_id}_{unique_id}.zip"
            
            # Destination path through gcsfuse
            pf_data_returns_path = os.path.join(self.gcsfuse_mount_path, bucket_name, "pf_data_returns")
            
            # Create pf_data_returns directory if it doesn't exist
            self.logger.info(f"Ensuring directory exists: {pf_data_returns_path}")
            os.makedirs(pf_data_returns_path, exist_ok=True)
            
            destination_path = os.path.join(pf_data_returns_path, zip_filename)
            
            # Copy the zip file
            self.logger.info(f"Copying {zip_path} to {destination_path}")
            shutil.copy2(zip_path, destination_path)
            
            self.logger.info(f"Uploaded {zip_filename} via gcsfuse to pf_data_returns/")
            
            return f"pf_data_returns/{zip_filename}"
            
        except Exception as e:
            self.logger.error(f"Error in upload_zip_to_gcsfuse: {str(e)}")
            self.logger.error(f"zip_path: {zip_path}")
            self.logger.error(f"destination_path: {destination_path if 'destination_path' in locals() else 'undefined'}")
            raise 

    def upload_zip_to_gcs_via_gsutil(self, bucket_name: str, sample_id: str, zip_path: str) -> str:
        """
        Upload zip file using gsutil command instead of gcsfuse (better for large files)
        
        Returns:
            The relative path of the uploaded file in the bucket
        """
        import uuid
        import subprocess
        
        try:
            # Create unique filename
            unique_id = uuid.uuid4().hex[:8]
            zip_filename = f"{sample_id}_{unique_id}.zip"
            gcs_path = f"gs://{bucket_name}/pf_data_returns/{zip_filename}"
            
            # Use gsutil to copy
            self.logger.info(f"Uploading {zip_path} to {gcs_path} via gsutil")
            result = subprocess.run(['gsutil', 'cp', zip_path, gcs_path], 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"gsutil copy failed: {result.stderr}")
            
            self.logger.info(f"Uploaded {zip_filename} via gsutil to pf_data_returns/")
            return f"pf_data_returns/{zip_filename}"
            
        except Exception as e:
            self.logger.error(f"Error in upload_zip_to_gcs_via_gsutil: {str(e)}")
            self.logger.error(f"zip_path: {zip_path}")
            raise 