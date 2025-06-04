import streamlit as st
import time
import logging
import uuid
import re
import os
from typing import Tuple, Optional, List

from src.core.services.gcs_service import GCSService
from src.core.services.email_service import EmailService
from src.core.services.tracking_service import TrackingService
from src.core.utils.file_operations import FileOperations

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
            max_value=60, 
            value=30,
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
    expiration_days: int,
):
    """
    Share a single sample with a recipient by creating a zip file using gcsfuse
    
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
        # Step 1: Check if sample exists
        status_text.text("Step 1/5: Checking sample data...")
        
        # List all objects for this sample to verify it exists
        objects = gcs_service.list_objects(source_bucket, f"FulgentTF/{sample_id}")
        
        if not objects:
            st.error(f"No files found for sample ID: {sample_id}")
            return
            
        progress_bar.progress(20)
        
        # Step 2: Create zip file on disk using gcsfuse
        status_text.text("Step 2/5: Creating zip file from sample data...")
        
        # Mount the source bucket with gcsfuse and create zip
        try:
            zip_path, file_count = file_ops.create_zip_from_gcsfuse(source_bucket, sample_id)
            
            if file_count == 0:
                st.error(f"No files could be added to zip for sample ID: {sample_id}")
                return
                
        except Exception as e:
            st.error(f"Error creating zip file: {str(e)}")
            st.info("Make sure gcsfuse is properly mounted and the source bucket is accessible at /mnt/gcs/")
            return
            
        progress_bar.progress(40)
        
        # Step 3: Upload zip file to pf_data_returns via gsutil
        status_text.text("Step 3/4: Uploading zipped sample data...")
        
        # Upload via gsutil instead of gcsfuse (better for large files)
        zip_object_name = file_ops.upload_zip_to_gcs_via_gsutil(source_bucket, sample_id, zip_path)
        
        # Clean up the temporary zip file
        try:
            logger.info(f"Attempting to remove temporary zip file: {zip_path}")
            os.remove(zip_path)
            logger.info(f"Successfully removed temporary zip file: {zip_path}")
        except Exception as e:
            logger.error(f"Could not remove temporary zip file {zip_path}: {str(e)} (Error type: {type(e).__name__})")
        
        progress_bar.progress(60)
        
        # Step 4: Generate download URL
        status_text.text("Step 4/4: Generating download link...")
        
        # Try to generate a signed URL first
        try:
            download_url = gcs_service.generate_signed_url(
                bucket_name=source_bucket,
                object_name=zip_object_name,
                expiration=expiration_days
            )
            logger.info("Successfully generated signed URL")
        except Exception as e:
            logger.warning(f"Could not generate signed URL: {str(e)}")
            
            # Fall back to granting access and providing direct URL
            try:
                gcs_service.grant_object_access(
                    bucket_name=source_bucket,
                    object_name=zip_object_name,
                    email=recipient_email
                )
                logger.info(f"Granted object access to {recipient_email}")
            except Exception as e2:
                logger.warning(f"Could not grant object-level access: {str(e2)}")
            
            # Provide direct GCS URL (user will need to authenticate with Google)
            download_url = f"https://storage.googleapis.com/{source_bucket}/{zip_object_name}"
        
        progress_bar.progress(80)
        
        # Step 5: Send notification email
        status_text.text("Step 5/5: Sending email notification...")
        
        # Send email with the signed URL
        email_sent = email_service.send_single_sample_notification(
            recipient_email=recipient_email,
            sample_id=sample_id,
            download_url=download_url,
            expires_days=expiration_days
        )
        
        if not email_sent:
            st.warning("Failed to send email notification, but the sample is shared")
        
        # Add record to tracking service
        try:
            # Create the full zip file path for tracking
            zip_file_path = f"{source_bucket}/{zip_object_name}"
            
            record = tracking_service.add_single_sample_record(
                sample_id=sample_id,
                recipient_email=recipient_email,
                source_bucket=source_bucket,
                zip_file_path=zip_file_path,
                expiration_days=expiration_days
            )
            logger.info(f"Successfully added tracking record for sample {sample_id}")
        except Exception as e:
            logger.error(f"Failed to add tracking record: {str(e)}")
            st.warning(f"Sample shared successfully, but tracking record could not be saved: {str(e)}")
        
        progress_bar.progress(100)
        status_text.text("Sample shared successfully!")
        
        # Display success message
        st.success(f"Sample {sample_id} has been shared with {recipient_email}. "
                  f"The link will expire in {expiration_days} days.")
        
        # Add prominent navigation guidance
        st.info("📊 **To view this share record:** Use the sidebar navigation to go to **'Track & Manage'** page")
        
        # Display the URL (for testing purposes, can be removed in production)
        with st.expander("Show download URL (for testing)"):
            st.write(download_url)
            
    except Exception as e:
        logger.error(f"Error sharing sample: {str(e)}")
        st.error(f"Error sharing sample: {str(e)}")
        # Reset the progress bar on error
        progress_bar.progress(0)