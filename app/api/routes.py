from fastapi import APIRouter, HTTPException, BackgroundTasks
from google.cloud import storage
import zipfile
import tempfile
import os
import uuid
import logging
import shutil
from pydantic import BaseModel, EmailStr
import json
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Centralized path configuration
CONFIG = {
    # Bucket names and default values
    "SOURCE_BUCKET": os.environ.get("SOURCE_BUCKET", "gcp-pf-bucket"),
    "TARGET_BUCKET": os.environ.get("TARGET_BUCKET", "gcp-pf-bucket"),  # Same bucket for returns
    # Path structure
    "SOURCE_PATH": "FulgentTF/",  # Source directory where samples are stored
    "TARGET_PATH": "pf_data_returns/",  # Target directory for shared files
    "SHARE_ID_PREFIX": "share-",  # Prefix for share IDs
    # Special files
    "METADATA_FILE": "_metadata.json",
    "COMPLETE_MARKER": "_COPY_COMPLETE",
    "DOWNLOAD_FILE": "download.zip"
}

# GCS client
storage_client = storage.Client()

# Create API router
api_router = APIRouter()

class SampleShare(BaseModel):
    sample_id: str
    user_email: EmailStr

@api_router.get("/")
def read_root():
    return {"message": "GCS Data Sharing Service API"}

@api_router.get("/samples")
def list_available_samples():
    """List all available samples in the source bucket"""
    try:
        # Get unique sample IDs (e.g., 889-6625) based on folder structure
        samples = set()
        
        # List blobs with the prefix to only look in the base directory
        blobs = storage_client.list_blobs(
            CONFIG["SOURCE_BUCKET"], 
            prefix=CONFIG["SOURCE_PATH"], 
            delimiter='/'
        )
        
        for prefix in blobs.prefixes:
            # Extract sample ID from path, adjusting for the base path prefix
            sample_id = prefix.replace(CONFIG["SOURCE_PATH"], "").rstrip('/')
            if sample_id:  # Only add non-empty IDs
                samples.add(sample_id)
        
        return {"samples": list(samples)}
    except Exception as e:
        logger.error(f"Error listing samples: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list samples: {str(e)}")

@api_router.post("/share-sample")
async def share_sample(
    sample_data: SampleShare,
    background_tasks: BackgroundTasks
):
    """Copy a sample to a user-specific folder and grant access"""
    # Create a new share ID
    share_id = f"{CONFIG['SHARE_ID_PREFIX']}{uuid.uuid4()}"
    target_path = f"{CONFIG['TARGET_PATH']}{share_id}/"
    
    try:
        # Get the target bucket
        bucket = storage_client.bucket(CONFIG["TARGET_BUCKET"])
        
        # Check if a lifecycle policy is already configured
        apply_lifecycle_policy(bucket)
        
        # Store metadata for this share
        metadata = {
            "share_id": share_id,
            "sample_id": sample_data.sample_id,
            "user_email": sample_data.user_email,
            "created_at": datetime.datetime.now().isoformat(),  # Add proper timestamp
            "expires_at": (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat(),  # Add expiration date
            "status": "copying",
            "path": target_path
        }
        
        metadata_blob = bucket.blob(f"{target_path}{CONFIG['METADATA_FILE']}")
        metadata_blob.upload_from_string(json.dumps(metadata))
        
        # Copy files in background
        background_tasks.add_task(
            copy_sample_files,
            CONFIG["SOURCE_BUCKET"],
            CONFIG["TARGET_BUCKET"],
            sample_data.sample_id,
            target_path
        )
        
        return {
            "share_id": share_id,
            "path": target_path,
            "status": "copying",
            "sample_id": sample_data.sample_id,
            "download_url": f"/api/download/{share_id}",
            "access_note": "User will need to use the download URL to access files. The URL will be valid for 1 hour after generation."
        }
    
    except Exception as e:
        logger.error(f"Error sharing sample: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to share sample: {str(e)}")

def copy_sample_files(source_bucket_name, target_bucket_name, sample_id, target_path):
    """Copy all files from the sample folder to the target folder"""
    source_bucket = storage_client.bucket(source_bucket_name)
    target_bucket = storage_client.bucket(target_bucket_name)
    
    try:
        # Get sample path prefix with configured source path
        sample_path = f"{CONFIG['SOURCE_PATH']}{sample_id}/"
        logger.info(f"Looking for files in path: {sample_path}")
        
        # List all blobs in the sample folder
        blobs = list(storage_client.list_blobs(source_bucket_name, prefix=sample_path))
        logger.info(f"Found {len(blobs)} files to copy from {sample_path}")
        
        # Copy each blob to the target folder
        copied_count = 0
        for blob in blobs:
            # Preserve the relative path within the sample folder, but in target path
            relative_path = blob.name.replace(sample_path, "", 1)
            target_blob_name = f"{target_path}{relative_path}"
            
            # Use direct copy_blob which is more efficient
            source_bucket.copy_blob(blob, target_bucket, target_blob_name)
            
            logger.info(f"Copied {blob.name} to {target_blob_name}")
            copied_count += 1
        
        logger.info(f"Successfully copied {copied_count} files for sample {sample_id}")
        
        # Update status in metadata
        metadata_blob = target_bucket.blob(f"{target_path}{CONFIG['METADATA_FILE']}")
        if metadata_blob.exists():
            metadata_text = metadata_blob.download_as_text()
            metadata = json.loads(metadata_text)
            metadata["status"] = "completed"
            metadata["files_copied"] = copied_count
            metadata_blob.upload_from_string(json.dumps(metadata))
        
        # Create a marker file indicating the copy is complete
        complete_marker = target_bucket.blob(f"{target_path}{CONFIG['COMPLETE_MARKER']}")
        complete_marker.upload_from_string("")
        
        logger.info(f"Completed copying sample {sample_id} to {target_path}")
    except Exception as e:
        logger.error(f"Error copying files: {str(e)}")
        # Mark as failed in metadata
        try:
            metadata_blob = target_bucket.blob(f"{target_path}{CONFIG['METADATA_FILE']}")
            if metadata_blob.exists():
                metadata_text = metadata_blob.download_as_text()
                metadata = json.loads(metadata_text)
                metadata["status"] = "failed"
                metadata["error"] = str(e)
                metadata_blob.upload_from_string(json.dumps(metadata))
        except:
            pass

@api_router.get("/download/{share_id}")
async def prepare_download(share_id: str, background_tasks: BackgroundTasks):
    """Create a zip file and return a signed URL for download"""
    if not share_id.startswith(CONFIG['SHARE_ID_PREFIX']):
        share_id = f"{CONFIG['SHARE_ID_PREFIX']}{share_id}"
    
    target_path = f"{CONFIG['TARGET_PATH']}{share_id}/"
    
    try:
        # Get the target bucket
        bucket = storage_client.bucket(CONFIG["TARGET_BUCKET"])
        
        # Check if path exists (by checking if metadata file exists)
        metadata_blob = bucket.blob(f"{target_path}{CONFIG['METADATA_FILE']}")
        if not metadata_blob.exists():
            raise HTTPException(status_code=404, detail="Shared data not found")
            
        # Check if copy is complete
        copy_complete = bucket.blob(f"{target_path}{CONFIG['COMPLETE_MARKER']}").exists()
        if not copy_complete:
            # Check status from metadata
            if metadata_blob.exists():
                metadata_text = metadata_blob.download_as_text()
                metadata = json.loads(metadata_text)
                status = metadata.get("status", "unknown")
                if status == "failed":
                    raise HTTPException(status_code=500, detail="File copying failed")
            return {"status": "copying", "message": "Files are still being copied. Please try again later."}
        
        # Check if zip already exists
        zip_blob = bucket.blob(f"{target_path}{CONFIG['DOWNLOAD_FILE']}")
        if zip_blob.exists():
            # Generate signed URL for download (expires in 1 hour)
            signed_url = zip_blob.generate_signed_url(
                version="v4",
                expiration=3600,  # 1 hour
                method="GET"
            )
            return {"download_url": signed_url, "status": "ready"}
        
        # Create zip in background
        background_tasks.add_task(
            create_zip_for_folder,
            target_path
        )
        
        return {"status": "preparing", "message": "Your download is being prepared. Please check back in a few moments."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error preparing download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to prepare download: {str(e)}")

def create_zip_for_folder(target_path):
    """Create a zip file for a folder's contents"""
    try:
        bucket = storage_client.bucket(CONFIG["TARGET_BUCKET"])
        
        # Create a temporary directory to store files
        temp_dir = tempfile.mkdtemp()
        try:
            # Download all blobs to temp directory
            blobs = storage_client.list_blobs(CONFIG["TARGET_BUCKET"], prefix=target_path)
            for blob in blobs:
                blob_name = blob.name
                # Skip metadata and marker files (any file starting with _)
                if os.path.basename(blob_name).startswith("_"):
                    continue
                
                # Create local path, removing the target path prefix
                local_path = os.path.join(temp_dir, blob_name.replace(target_path, ""))
                # Create subdirectories if needed
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                # Download the blob
                blob.download_to_filename(local_path)
            
            # Create a temporary zip file
            zip_path = os.path.join(temp_dir, CONFIG["DOWNLOAD_FILE"])
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file != CONFIG["DOWNLOAD_FILE"]:  # Skip the zip itself
                            file_path = os.path.join(root, file)
                            # Make path relative to temp_dir
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)
            
            # Upload zip to bucket
            zip_blob = bucket.blob(f"{target_path}{CONFIG['DOWNLOAD_FILE']}")
            zip_blob.upload_from_filename(zip_path)
            
            logger.info(f"Created and uploaded zip for folder {target_path}")
            
        finally:
            # Clean up the temporary directory
            shutil.rmtree(temp_dir)
            
    except Exception as e:
        logger.error(f"Error creating zip: {str(e)}")

@api_router.get("/shares")
def list_shares():
    """List all active shares (for admin use)"""
    shares = []
    
    try:
        # List all blobs in the target path that are metadata files
        metadata_prefix = f"{CONFIG['TARGET_PATH']}"
        blobs = storage_client.list_blobs(
            CONFIG["TARGET_BUCKET"], 
            prefix=metadata_prefix
        )
        
        # Process metadata files
        metadata_paths = {}
        for blob in blobs:
            if blob.name.endswith(CONFIG["METADATA_FILE"]):
                folder_path = os.path.dirname(blob.name) + "/"
                if folder_path not in metadata_paths:
                    metadata_paths[folder_path] = blob.name
        
        # Get metadata from each share
        for folder_path, metadata_path in metadata_paths.items():
            metadata_blob = storage_client.bucket(CONFIG["TARGET_BUCKET"]).blob(metadata_path)
            metadata_text = metadata_blob.download_as_text()
            try:
                metadata = json.loads(metadata_text)
                
                # Check if copy is complete
                copy_complete = storage_client.bucket(CONFIG["TARGET_BUCKET"]).blob(
                    f"{folder_path}{CONFIG['COMPLETE_MARKER']}"
                ).exists()
                metadata["status"] = "completed" if copy_complete else metadata.get("status", "unknown")
                
                shares.append(metadata)
            except Exception as json_error:
                logger.warning(f"Error parsing metadata for {folder_path}: {str(json_error)}")
        
        return {"shares": shares}
    except Exception as e:
        logger.error(f"Error listing shares: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list shares: {str(e)}")

@api_router.delete("/shares/{share_id}")
def delete_share(share_id: str):
    """Delete a share folder"""
    if not share_id.startswith(CONFIG['SHARE_ID_PREFIX']):
        share_id = f"{CONFIG['SHARE_ID_PREFIX']}{share_id}"
    
    target_path = f"{CONFIG['TARGET_PATH']}{share_id}/"
    
    try:
        # Delete all objects with the given prefix
        bucket = storage_client.bucket(CONFIG["TARGET_BUCKET"])
        blobs = list(bucket.list_blobs(prefix=target_path))
        
        if not blobs:
            raise HTTPException(status_code=404, detail="Share not found")
        
        # Delete each blob
        for blob in blobs:
            blob.delete()
            logger.info(f"Deleted {blob.name}")
        
        return {"status": "deleted", "share_id": share_id, "path": target_path}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting share: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete share: {str(e)}")

def apply_lifecycle_policy(bucket):
    """Apply a 30-day lifecycle deletion policy to the pf_data_returns/ directory"""
    try:
        # Convert lifecycle rules to a list
        current_rules = list(bucket.lifecycle_rules) if bucket.lifecycle_rules else []
        
        # Check if our rule already exists
        rule_exists = False
        need_update = False
        
        for rule in current_rules:
            if (rule.get('action', {}).get('type') == 'Delete' and 
                CONFIG["TARGET_PATH"] in rule.get('condition', {}).get('matchesPrefix', [])):
                rule_exists = True
                # Update age if different
                if rule.get('condition', {}).get('age') != 30:
                    rule['condition']['age'] = 30
                    need_update = True
                break
        
        # Add our rule if it doesn't exist
        if not rule_exists:
            new_rule = {
                'action': {'type': 'Delete'},
                'condition': {
                    'age': 30,  # 30-day retention
                    'matchesPrefix': [CONFIG["TARGET_PATH"]]
                }
            }
            current_rules.append(new_rule)
            need_update = True
            
        # Only update if needed
        if need_update:
            bucket.lifecycle_rules = current_rules
            bucket.patch()
            logger.info(f"Applied 30-day lifecycle policy to {CONFIG['TARGET_PATH']}")
    except Exception as e:
        logger.warning(f"Failed to set lifecycle policy: {str(e)}")
        # Continue execution even if lifecycle policy fails 