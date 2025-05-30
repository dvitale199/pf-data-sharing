from google.cloud import storage
from google.cloud.storage import Bucket, Blob
import datetime
import logging
from typing import List, Dict, Optional, Union
import subprocess
import os

class GCSService:
    def __init__(self):
        """Initialize the Google Cloud Storage client"""
        # Check if a service account key file is available
        key_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '/home/vitaled2/data-tecnica-8d915e1082d7.json')
        if os.path.exists(key_file):
            self.client = storage.Client.from_service_account_json(key_file)
            self.logger = logging.getLogger(__name__)
            self.logger.info(f"Using service account key file: {key_file}")
        else:
            self.client = storage.Client()
            self.logger = logging.getLogger(__name__)
            self.logger.info("Using default application credentials")
    
    def bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists, handling permission errors gracefully"""
        try:
            return self.client.bucket(bucket_name).exists()
        except Exception as e:
            # Log the error but don't fail completely
            self.logger.warning(f"Cannot check bucket existence for {bucket_name}: {str(e)}")
            # If we can't check, assume it doesn't exist so we can try to create it
            return False
    
    def create_bucket(self, bucket_name: str, location: str = "us-central1") -> Bucket:
        """Create a new bucket with the specified name"""
        bucket = self.client.bucket(bucket_name)
        bucket.create(location=location)
        self.logger.info(f"Created bucket {bucket_name} in {location}")
        return bucket
    
    def get_bucket(self, bucket_name: str) -> Bucket:
        """Get a bucket by name"""
        return self.client.bucket(bucket_name)
    
    def list_objects(self, bucket_name: str, prefix: str = "") -> List[Blob]:
        """List objects in a bucket with optional prefix"""
        bucket = self.get_bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        return blobs
    
    def copy_object(self, source_bucket: str, source_object: str, 
                   destination_bucket: str, destination_object: str) -> Blob:
        """Copy an object from source bucket to destination bucket"""
        try:
            source_bucket_obj = self.get_bucket(source_bucket)
            source_blob = source_bucket_obj.blob(source_object)
            
            destination_bucket_obj = self.get_bucket(destination_bucket)
            
            # Copy the blob
            copied_blob = source_bucket_obj.copy_blob(
                source_blob, destination_bucket_obj, destination_object
            )
            
            self.logger.info(f"Copied {source_object} to {destination_bucket}/{destination_object}")
            return copied_blob
        except Exception as e:
            self.logger.error(f"Error copying object: {str(e)}")
            raise
    
    def upload_from_file(self, bucket_name: str, file_obj, destination_blob_name: str) -> Blob:
        """Upload data from a file-like object to a GCS bucket"""
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_file(file_obj)
        self.logger.info(f"Uploaded file to {bucket_name}/{destination_blob_name}")
        return blob
    
    def upload_from_string(self, bucket_name: str, data: str, destination_blob_name: str) -> Blob:
        """Upload data from a string to a GCS bucket"""
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(data)
        self.logger.info(f"Uploaded data to {bucket_name}/{destination_blob_name}")
        return blob
    
    def generate_signed_url(self, bucket_name: str, object_name: str, 
                           expiration: int = 7) -> str:
        """Generate a signed URL for an object with expiration in days"""
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(days=expiration),
            method="GET"
        )
        
        return url
    
    def generate_signed_url_via_gsutil(self, bucket_name: str, object_name: str, 
                                      expiration: int = 7) -> str:
        """Generate a signed URL using gsutil (works with Compute Engine service accounts)"""
        # Calculate expiration time in gsutil format (e.g., "7d" for 7 days)
        expiration_str = f"{expiration}d"
        gcs_path = f"gs://{bucket_name}/{object_name}"
        
        try:
            result = subprocess.run([
                'gsutil', 'signurl', '-d', expiration_str, 
                '/dev/null',  # Dummy key file (gsutil will use service account)
                gcs_path
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                # Try alternative approach for service accounts
                result = subprocess.run([
                    'gsutil', 'signurl', '-d', expiration_str, 
                    gcs_path
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"gsutil signurl failed: {result.stderr}")
            
            # Parse the output to extract the URL
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.startswith('https://'):
                    return line.strip()
            
            # If no direct URL found, try to extract from the last line
            if lines:
                parts = lines[-1].split('\t')
                if len(parts) >= 2:
                    return parts[-1].strip()
            
            raise Exception("Could not parse signed URL from gsutil output")
            
        except Exception as e:
            self.logger.error(f"Error generating signed URL via gsutil: {str(e)}")
            raise
    
    def set_lifecycle_policy(self, bucket_name: str, days_to_deletion: int = 30) -> None:
        """Set lifecycle policy for a bucket to delete objects after specified days"""
        bucket = self.get_bucket(bucket_name)
        
        # Use the raw dictionary format that GCS expects
        bucket.lifecycle_rules = [
            {
                "action": {
                    "type": "Delete"
                },
                "condition": {
                    "age": days_to_deletion
                }
            }
        ]
        
        bucket.patch()
        self.logger.info(f"Set lifecycle policy for {bucket_name} to delete objects after {days_to_deletion} days")
    
    def make_public(self, bucket_name: str, object_name: str) -> str:
        """Make an object publicly accessible and return its public URL"""
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(object_name)
        blob.make_public()
        return blob.public_url
    
    def grant_access(self, bucket_name: str, email: str, role: str = "roles/storage.objectViewer") -> None:
        """Grant access to a bucket for a user with the specified role"""
        bucket = self.get_bucket(bucket_name)
        
        policy = bucket.get_iam_policy()
        policy.bindings.append(
            {"role": role, "members": [f"user:{email}"]}
        )
        
        bucket.set_iam_policy(policy)
        self.logger.info(f"Granted {role} access to {email} for bucket {bucket_name}")
    
    def grant_object_access(self, bucket_name: str, object_name: str, email: str, role: str = "roles/storage.objectViewer") -> None:
        """Grant access to a specific object for a user with the specified role"""
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        policy = blob.get_iam_policy()
        policy.bindings.append(
            {"role": role, "members": [f"user:{email}"]}
        )
        
        blob.set_iam_policy(policy)
        self.logger.info(f"Granted {role} access to {email} for object {bucket_name}/{object_name}") 