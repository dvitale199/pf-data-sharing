import io
import zipfile
import logging
import os
import csv
from typing import List, Dict, BinaryIO, Tuple, Set, Optional
from ..services.gcs_service import GCSService

class FileOperations:
    def __init__(self, gcs_service: GCSService):
        """Initialize with a GCS service instance"""
        self.gcs_service = gcs_service
        self.logger = logging.getLogger(__name__)
        
    def create_zip_from_gcs_objects(self, source_bucket: str, object_paths: List[str], 
                                   prefix: str = "") -> BinaryIO:
        """
        Create a zip file in memory from GCS objects
        
        Args:
            source_bucket: Source bucket name
            object_paths: List of object paths in the bucket
            prefix: Optional prefix to filter objects
            
        Returns:
            A file-like object containing the zip data
        """
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(file=zip_buffer, mode='a', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zip_file:
            for object_path in object_paths:
                if not object_path.startswith(prefix):
                    continue
                    
                try:
                    # Download the object content
                    content = self.gcs_service.download_as_bytes(source_bucket, object_path)
                    
                    # Remove the prefix for the zip file structure if needed
                    arcname = object_path
                    if prefix and object_path.startswith(prefix):
                        arcname = object_path[len(prefix):]
                        if arcname.startswith('/'):
                            arcname = arcname[1:]
                    
                    # Add to zip
                    zip_file.writestr(arcname, content)
                    self.logger.info(f"Added {object_path} to zip")
                    
                except Exception as e:
                    self.logger.error(f"Error adding {object_path} to zip: {str(e)}")
        
        # Reset the buffer position to the start
        zip_buffer.seek(0)
        return zip_buffer
    
    def create_zip_from_sample_id(self, source_bucket: str, sample_id: str,
                                prefix: str = "") -> Tuple[BinaryIO, int]:
        """
        Create a zip file containing all files for a specific sample ID
        
        Args:
            source_bucket: Source bucket name
            sample_id: The sample ID to filter files
            prefix: Optional additional prefix
            
        Returns:
            Tuple of (file-like zip object, number of files included)
        """
        # Get default prefix from environment if none is provided
        default_prefix = os.environ.get("DEFAULT_SOURCE_PREFIX", "")
        
        # Combine default prefix with any explicitly passed prefix
        if default_prefix and prefix:
            combined_prefix = f"{default_prefix}/{prefix}"
        elif default_prefix:
            combined_prefix = default_prefix
        else:
            combined_prefix = prefix
        
        # Use the combined prefix
        if combined_prefix:
            full_prefix = f"{combined_prefix}/{sample_id}"
        else:
            full_prefix = sample_id
            
        # List all objects for this sample
        objects = self.gcs_service.list_objects(source_bucket, full_prefix)
        object_paths = [obj.name for obj in objects]
        
        # Create zip from these objects
        zip_buffer = self.create_zip_from_gcs_objects(source_bucket, object_paths, "")
        return zip_buffer, len(object_paths)
    
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
    
    def bulk_copy_samples(self, source_bucket: str, destination_bucket: str, 
                        sample_ids: List[str], prefix: str = "") -> Dict[str, int]:
        """
        Copy multiple samples from source to destination bucket
        
        Args:
            source_bucket: Source bucket name
            destination_bucket: Destination bucket name
            sample_ids: List of sample IDs to copy
            prefix: Optional prefix for source objects
            
        Returns:
            Dictionary with sample_id: count of files copied
        """
        results = {}
        
        for sample_id in sample_ids:
            if prefix:
                full_prefix = f"{prefix}/{sample_id}"
            else:
                full_prefix = sample_id
                
            # List all objects for this sample
            objects = self.gcs_service.list_objects(source_bucket, full_prefix)
            
            # Copy each object
            count = 0
            for obj in objects:
                try:
                    self.gcs_service.copy_object(
                        source_bucket, obj.name,
                        destination_bucket, obj.name
                    )
                    count += 1
                except Exception as e:
                    self.logger.error(f"Error copying {obj.name}: {str(e)}")
            
            results[sample_id] = count
            
        return results
    
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