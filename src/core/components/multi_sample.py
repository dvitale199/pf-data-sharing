import streamlit as st
import time
import logging
import uuid
import re
from typing import List, Dict, Optional

from src.core.services.gcs_service import GCSService
from src.core.services.email_service import EmailService
from src.core.services.tracking_service import TrackingService
from src.core.utils.file_operations import FileOperations

def validate_email(email: str) -> bool:
    """Validate email format"""
    email_pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    return bool(email_pattern.match(email))

def validate_bucket_name(name: str) -> bool:
    """Validate GCS bucket name format"""
    # GCS bucket naming rules: 3-63 chars, lowercase, numbers, dashes, start/end with letter/number
    bucket_pattern = re.compile(r'^[a-z0-9][-a-z0-9]{1,61}[a-z0-9]$')
    return bool(bucket_pattern.match(name))

def render_multi_sample_component(
    gcs_service: GCSService,
    email_service: EmailService,
    tracking_service: TrackingService,
    file_ops: FileOperations,
    source_bucket: str,
):
    """
    Render the multi-sample sharing component
    
    Args:
        gcs_service: GCS service instance
        email_service: Email service instance
        tracking_service: Tracking service instance
        file_ops: File operations utility instance
        source_bucket: Source bucket name for samples
    """
    st.header("Share Multiple Samples")
    
    # Two tabs: Upload List or Enter Manually
    tab1, tab2 = st.tabs(["Upload Sample List", "Enter Sample IDs Manually"])
    
    with tab1:
        uploaded_file = st.file_uploader(
            "Upload a file with sample IDs (CSV or TXT)", 
            type=["csv", "txt"],
            help="File should contain one sample ID per line or as the first column in CSV"
        )
        
        has_header = st.checkbox("File has header row", value=True)
        
        if uploaded_file is not None:
            # Process the file to extract sample IDs
            sample_ids = file_ops.process_batch_file(uploaded_file, has_header)
            if sample_ids:
                st.success(f"Found {len(sample_ids)} sample IDs in the uploaded file")
                # Store in session state to use later
                st.session_state["multi_sample_ids"] = sample_ids
                # Show preview
                with st.expander("Preview Sample IDs"):
                    st.write(sample_ids[:10])
                    if len(sample_ids) > 10:
                        st.write("... and more")
            else:
                st.error("No sample IDs found in the uploaded file")
    
    with tab2:
        manual_sample_ids = st.text_area(
            "Enter Sample IDs (one per line)",
            help="Enter one sample ID per line"
        )
        
        if st.button("Parse Sample IDs"):
            if manual_sample_ids:
                # Split by newline and filter empty lines
                sample_ids = [line.strip() for line in manual_sample_ids.split("\n") if line.strip()]
                if sample_ids:
                    st.success(f"Found {len(sample_ids)} sample IDs")
                    # Store in session state to use later
                    st.session_state["multi_sample_ids"] = sample_ids
                else:
                    st.error("No valid sample IDs entered")
            else:
                st.error("Please enter at least one sample ID")
    
    # Only show the sharing form if sample IDs are available
    if "multi_sample_ids" in st.session_state and st.session_state["multi_sample_ids"]:
        st.subheader("Sharing Configuration")
        
        recipient_email = st.text_input("Recipient Email", help="Enter the email address of the recipient")
        
        # Bucket creation options
        bucket_option = st.radio(
            "Destination Bucket",
            ["Create new bucket", "Use existing bucket"]
        )
        
        destination_bucket = ""
        if bucket_option == "Create new bucket":
            # Allow custom bucket name or generate one
            use_custom_name = st.checkbox("Use custom bucket name", value=False)
            
            if use_custom_name:
                custom_bucket_name = st.text_input(
                    "Bucket Name", 
                    help="Enter a globally unique bucket name (3-63 characters, lowercase, no spaces)"
                )
                if custom_bucket_name:
                    if validate_bucket_name(custom_bucket_name):
                        destination_bucket = custom_bucket_name
                    else:
                        st.error("Invalid bucket name format")
            else:
                # Generate a bucket name automatically
                sample_count = len(st.session_state["multi_sample_ids"])
                auto_bucket_name = f"shared-samples-{sample_count}-{uuid.uuid4().hex[:8]}".lower()
                st.info(f"Generated bucket name: {auto_bucket_name}")
                destination_bucket = auto_bucket_name
                
        else:  # Use existing bucket
            existing_bucket = st.text_input(
                "Existing Bucket Name",
                help="Enter the name of an existing bucket you have access to"
            )
            destination_bucket = existing_bucket
        
        expiration_days = st.slider(
            "Expiration (days)", 
            min_value=1,
            max_value=90,
            value=30,
            help="Number of days until the shared data expires"
        )
        
        if st.button("Share Samples"):
            if not destination_bucket:
                st.error("Please specify a destination bucket")
                return
                
            if not validate_email(recipient_email):
                st.error("Please enter a valid email address")
                return
                
            if destination_bucket == source_bucket:
                st.error("""⚠️ Security Error: Cannot use source bucket as destination. 
                         This would grant recipient access to ALL data in the source bucket. 
                         Please choose a different destination bucket.""")
                return
                
            # Share the samples
            share_multi_samples(
                gcs_service=gcs_service,
                email_service=email_service,
                tracking_service=tracking_service,
                file_ops=file_ops,
                source_bucket=source_bucket,
                destination_bucket=destination_bucket,
                sample_ids=st.session_state["multi_sample_ids"],
                recipient_email=recipient_email,
                expiration_days=expiration_days,
                create_new_bucket=(bucket_option == "Create new bucket")
            )

def share_multi_samples(
    gcs_service: GCSService,
    email_service: EmailService,
    tracking_service: TrackingService,
    file_ops: FileOperations,
    source_bucket: str,
    destination_bucket: str,
    sample_ids: List[str],
    recipient_email: str,
    expiration_days: int,
    create_new_bucket: bool
):
    """
    Share multiple samples with a recipient
    
    Args:
        gcs_service: GCS service instance
        email_service: Email service instance
        tracking_service: Tracking service instance
        file_ops: File operations utility instance
        source_bucket: Source bucket name
        destination_bucket: Destination bucket name
        sample_ids: List of sample IDs to share
        recipient_email: Recipient's email address
        expiration_days: Days until the share expires
        create_new_bucket: Whether to create a new bucket or use existing
    """
    logger = logging.getLogger(__name__)
    
    # Show progress
    progress_bar = st.progress(0)
    status_text = st.empty()
    sample_status = st.empty()
    
    try:
        # Step 1: Check or create destination bucket
        status_text.text("Step 1/4: Preparing destination bucket...")
        
        if create_new_bucket:
            # Check if the bucket already exists
            if gcs_service.bucket_exists(destination_bucket):
                st.error(f"Bucket {destination_bucket} already exists. Please choose a different name.")
                return
                
            # Create the bucket
            gcs_service.create_bucket(destination_bucket)
            
            # Set lifecycle policy
            gcs_service.set_lifecycle_policy(destination_bucket, expiration_days)
            
        else:
            # Check if the bucket exists
            if not gcs_service.bucket_exists(destination_bucket):
                st.error(f"Bucket {destination_bucket} does not exist or you don't have access.")
                return
        
        progress_bar.progress(25)
        
        # Step 2: Copy samples to destination
        status_text.text("Step 2/4: Copying sample data...")
        
        # Copy samples and track progress
        total_samples = len(sample_ids)
        results = {}
        
        for idx, sample_id in enumerate(sample_ids):
            # Update status
            sample_status.text(f"Copying sample {idx+1}/{total_samples}: {sample_id}")
            
            # Calculate progress percentage for this step (25-75% of total)
            sub_progress = 25 + int(50 * (idx / total_samples))
            progress_bar.progress(sub_progress)
            
            # Copy this sample's objects
            try:
                objects = gcs_service.list_objects(source_bucket, f"FulgentTF/{sample_id}")
                
                # Skip if no objects found for this sample
                if not objects:
                    results[sample_id] = 0
                    continue
                    
                # Copy each object
                count = 0
                for obj in objects:
                    gcs_service.copy_object(
                        source_bucket, obj.name,
                        destination_bucket, obj.name
                    )
                    count += 1
                
                results[sample_id] = count
            except Exception as e:
                logger.error(f"Error copying sample {sample_id}: {str(e)}")
                results[sample_id] = -1  # Error flag
        
        progress_bar.progress(75)
        
        # Step 3: Grant access to recipient
        status_text.text("Step 3/4: Granting access to recipient...")
        
        # Grant bucket access to recipient
        gcs_service.grant_access(destination_bucket, recipient_email)
        
        progress_bar.progress(90)
        
        # Step 4: Send notification email
        status_text.text("Step 4/4: Sending email notification...")
        
        # Only include successfully copied samples
        successful_samples = [
            sample_id for sample_id, count in results.items() if count > 0
        ]
        
        # Send email notification
        if successful_samples:
            email_sent = email_service.send_multi_sample_notification(
                recipient_email=recipient_email,
                sample_ids=successful_samples,
                bucket_name=destination_bucket,
                expires_days=expiration_days
            )
            
            if not email_sent:
                st.warning("Failed to send email notification, but samples were shared.")
                
            # Add record to tracking service
            try:
                record = tracking_service.add_multi_sample_record(
                    sample_ids=successful_samples,
                    recipient_email=recipient_email,
                    source_bucket=source_bucket,
                    destination_bucket=destination_bucket,
                    expiration_days=expiration_days
                )
                logger.info(f"Successfully added tracking record for {len(successful_samples)} samples")
            except Exception as e:
                logger.error(f"Failed to add tracking record: {str(e)}")
                st.warning(f"Samples shared successfully, but tracking record could not be saved: {str(e)}")
        else:
            st.error("No samples were successfully copied. Nothing was shared.")
            return
        
        progress_bar.progress(100)
        sample_status.empty()  # Clear the sample status
        
        # Final status update
        status_text.text("Samples shared successfully!")
        
        # Summary of results
        successful_count = len(successful_samples)
        failed_count = sum(1 for count in results.values() if count <= 0)
        
        st.success(f"{successful_count} samples have been shared with {recipient_email}. "
                  f"The data will expire in {expiration_days} days.")
        
        # Add prominent navigation guidance
        st.info("📊 **To view this share record:** Use the sidebar navigation to go to **'Track & Manage'** page")
        
        if failed_count > 0:
            st.warning(f"{failed_count} samples could not be shared (not found or error occurred).")
            
        # Show details
        with st.expander("Show details"):
            st.write("Shared to bucket:", destination_bucket)
            st.write("Results by sample:")
            for sample_id, count in results.items():
                if count > 0:
                    st.write(f"✅ {sample_id}: {count} files copied")
                else:
                    st.write(f"❌ {sample_id}: Failed to copy")
    
    except Exception as e:
        logger.error(f"Error sharing samples: {str(e)}")
        st.error(f"Error sharing samples: {str(e)}")
        # Reset progress
        progress_bar.progress(0) 