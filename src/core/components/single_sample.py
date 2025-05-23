import streamlit as st
import time
import logging
import uuid
import re
from typing import Tuple, Optional

from ..services.gcs_service import GCSService
from ..services.email_service import EmailService
from ..services.tracking_service import TrackingService
from ..utils.file_operations import FileOperations

def validate_email(email: str) -> bool:
    """Validate email format"""
    email_pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    return bool(email_pattern.match(email))

def validate_sample_id(sample_id: str) -> bool:
    """Validate sample ID (simple non-empty check)"""
    return bool(sample_id and sample_id.strip())

def render_single_sample_component(
    gcs_service: GCSService,
    email_service: EmailService,
    tracking_service: TrackingService,
    file_ops: FileOperations,
    source_bucket: str,
):
    """
    Render the single sample sharing component
    
    Args:
        gcs_service: GCS service instance
        email_service: Email service instance
        tracking_service: Tracking service instance
        file_ops: File operations utility instance
        source_bucket: Source bucket name for samples
    """
    st.header("Share a Single Sample")
    
    # Form for sample sharing
    with st.form("single_sample_form"):
        sample_id = st.text_input("Sample ID", help="Enter the ID of the sample to share")
        recipient_email = st.text_input("Recipient Email", help="Enter the email address of the recipient")
        
        expiration_days = st.slider(
            "Link Expiration (days)", 
            min_value=1, 
            max_value=30, 
            value=7,
            help="How many days until the shared sample expires"
        )
        
        submit_button = st.form_submit_button("Share Sample")
        
    if submit_button:
        if not validate_sample_id(sample_id):
            st.error("Please enter a valid Sample ID")
            return
        
        if not validate_email(recipient_email):
            st.error("Please enter a valid email address")
            return
            
        # Process the sample sharing
        share_single_sample(
            gcs_service=gcs_service,
            email_service=email_service,
            tracking_service=tracking_service,
            file_ops=file_ops,
            source_bucket=source_bucket,
            sample_id=sample_id,
            recipient_email=recipient_email,
            expiration_days=expiration_days
        )

def share_single_sample(
    gcs_service: GCSService,
    email_service: EmailService,
    tracking_service: TrackingService,
    file_ops: FileOperations,
    source_bucket: str,
    sample_id: str,
    recipient_email: str,
    expiration_days: int
):
    """
    Share a single sample with a recipient
    
    Args:
        gcs_service: GCS service instance
        email_service: Email service instance
        tracking_service: Tracking service instance
        file_ops: File operations utility instance
        source_bucket: Source bucket name
        sample_id: Sample ID to share
        recipient_email: Recipient's email address
        expiration_days: Days until the share expires
    """
    logger = logging.getLogger(__name__)
    
    # Show progress
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Update status
        status_text.text("Step 1/4: Creating zip file from sample data...")
        
        # Create zip file in memory
        zip_buffer, file_count = file_ops.create_zip_from_sample_id(
            source_bucket=source_bucket,
            sample_id=sample_id
        )
        
        if file_count == 0:
            st.error(f"No files found for sample ID: {sample_id}")
            return
            
        progress_bar.progress(25)
        
        # Step 2: Update status
        status_text.text("Step 2/4: Creating temporary bucket for shared sample...")
        
        # Create a unique bucket name for this share
        temp_bucket_name = f"temp-share-{sample_id}-{uuid.uuid4().hex[:8]}".lower()
        
        # Check if bucket exists (unlikely but possible)
        if gcs_service.bucket_exists(temp_bucket_name):
            temp_bucket_name = f"temp-share-{sample_id}-{uuid.uuid4().hex}".lower()
            
        print(f"DEBUG: About to create bucket: {temp_bucket_name}")
        
        try:
            # Create the temporary bucket
            gcs_service.create_bucket(temp_bucket_name)
            print("DEBUG: Bucket created successfully")
            
            print("DEBUG: About to set lifecycle policy")
            # Set lifecycle policy for automatic deletion
            gcs_service.set_lifecycle_policy(temp_bucket_name, expiration_days)
            print("DEBUG: Lifecycle policy set successfully")
            
        except Exception as e:
            print(f"DEBUG: Error in bucket operations: {e}")
            raise e
        
        progress_bar.progress(50)
        
        # Step 3: Update status
        status_text.text("Step 3/4: Uploading zipped sample data...")
        
        try:
            # Upload the zip file to the temporary bucket
            zip_filename = f"{sample_id}.zip"
            print(f"DEBUG: About to upload {zip_filename} to {temp_bucket_name}")
            
            gcs_service.upload_from_file(
                bucket_name=temp_bucket_name,
                file_obj=zip_buffer,
                destination_blob_name=zip_filename
            )
            print("DEBUG: Upload successful")
            
            # Generate a signed URL for the zip file
            print("DEBUG: About to generate signed URL")
            signed_url = gcs_service.generate_signed_url(
                bucket_name=temp_bucket_name,
                object_name=zip_filename,
                expiration=expiration_days
            )
            print(f"DEBUG: Signed URL generated: {signed_url[:50]}...")
            
            progress_bar.progress(75)
            
            # Step 4: Update status
            status_text.text("Step 4/4: Sending email notification...")
            
            print("DEBUG: About to send email")
            # Send email with the signed URL
            email_sent = email_service.send_single_sample_notification(
                recipient_email=recipient_email,
                sample_id=sample_id,
                download_url=signed_url,
                expires_days=expiration_days
            )
            print(f"DEBUG: Email sent: {email_sent}")
            
            if not email_sent:
                st.warning("Failed to send email notification, but the sample is shared")
            
            print("DEBUG: About to add tracking record")
            # Add record to tracking service
            tracking_service.add_single_sample_record(
                sample_id=sample_id,
                recipient_email=recipient_email,
                source_bucket=source_bucket,
                temp_bucket=temp_bucket_name,
                expiration_days=expiration_days
            )
            print("DEBUG: Tracking record added successfully")
            
        except Exception as e:
            print(f"DEBUG: Error occurred at: {e}")
            raise e
        
        progress_bar.progress(100)
        status_text.text("Sample shared successfully!")
        
        # Display success message
        st.success(f"Sample {sample_id} has been shared with {recipient_email}. "
                  f"The link will expire in {expiration_days} days.")
        
        # Display the URL (for testing purposes, can be removed in production)
        with st.expander("Show download URL (for testing)"):
            st.write(signed_url)
            
    except Exception as e:
        logger.error(f"Error sharing sample: {str(e)}")
        st.error(f"Error sharing sample: {str(e)}")
        # Reset the progress bar on error
        progress_bar.progress(0) 