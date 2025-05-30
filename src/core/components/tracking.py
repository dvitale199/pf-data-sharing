import streamlit as st
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..services.tracking_service import TrackingService
from ..services.gcs_service import GCSService

def render_tracking_component(
    tracking_service: TrackingService,
    gcs_service: Optional[GCSService] = None
):
    """
    Render the tracking and management component
    
    Args:
        tracking_service: Tracking service instance
        gcs_service: Optional GCS service for cleanup operations
    """
    st.header("Track & Manage Shared Samples")
    
    # Load all records
    df = tracking_service.get_all_records()
    
    if df.empty:
        st.info("No shared samples found.")
        return
    
    # Add filter options
    st.subheader("Filter Records")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        show_active_only = st.checkbox("Active only", value=True)
    
    with col2:
        if 'recipient_email' in df.columns and not df['recipient_email'].empty:
            recipients = ["All"] + sorted(df['recipient_email'].unique().tolist())
            selected_recipient = st.selectbox("Recipient", recipients)
        else:
            selected_recipient = "All"
    
    with col3:
        if 'type' in df.columns and not df['type'].empty:
            types = ["All"] + sorted(df['type'].unique().tolist())
            selected_type = st.selectbox("Share Type", types)
        else:
            selected_type = "All"
    
    with col4:
        if 'expires_at' in df.columns and not df['expires_at'].empty:
            sort_by = st.selectbox(
                "Sort by",
                ["Expiration (soonest first)", "Expiration (latest first)", "Creation (newest first)", "Creation (oldest first)"]
            )
        else:
            sort_by = "Creation (newest first)"
    
    # Apply filters
    filtered_df = df.copy()
    
    if show_active_only:
        filtered_df = filtered_df[filtered_df['active'] == True]
    
    if selected_recipient != "All":
        filtered_df = filtered_df[filtered_df['recipient_email'] == selected_recipient]
    
    if selected_type != "All":
        filtered_df = filtered_df[filtered_df['type'] == selected_type]
    
    # Apply sorting
    if sort_by == "Expiration (soonest first)":
        filtered_df = filtered_df.sort_values('expires_at')
    elif sort_by == "Expiration (latest first)":
        filtered_df = filtered_df.sort_values('expires_at', ascending=False)
    elif sort_by == "Creation (newest first)":
        filtered_df = filtered_df.sort_values('created_at', ascending=False)
    elif sort_by == "Creation (oldest first)":
        filtered_df = filtered_df.sort_values('created_at')
    
    # Format the DataFrame for display
    if not filtered_df.empty:
        display_df = format_dataframe_for_display(filtered_df)
        
        # Display the data as a table
        st.dataframe(
            display_df,
            column_config={
                "Days Left": st.column_config.ProgressColumn(
                    "Days Left",
                    help="Days until expiration",
                    format="%d days",
                    min_value=0,
                    max_value=30,
                ),
                "Actions": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select for deletion"
                )
            },
            hide_index=True
        )
        
        # Display selected actions
        if 'selected_rows' in st.session_state and st.session_state['selected_rows']:
            selected_ids = [row['id'] for row in st.session_state['selected_rows'] if row['Actions']]
            
            if selected_ids:
                st.write(f"Selected {len(selected_ids)} records for action:")
                
                # Action buttons
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Delete Selected Records"):
                        delete_selected_records(tracking_service, gcs_service, selected_ids)
                
                with col2:
                    if st.button("Deactivate Selected Records"):
                        deactivate_selected_records(tracking_service, selected_ids)
    else:
        st.info("No records match the selected filters.")

def format_dataframe_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """
    Format the DataFrame for better display in the UI
    
    Args:
        df: Original DataFrame from the tracking service
        
    Returns:
        Formatted DataFrame for display
    """
    # Create a copy for display
    display_df = pd.DataFrame()
    
    # Add type-specific columns
    if 'type' in df.columns:
        display_df['Type'] = df['type'].apply(lambda x: 'Single Sample' if x == 'single' else 'Multiple Samples')
    
    # Add shared items info
    if 'sample_id' in df.columns:
        display_df['Shared Data'] = df['sample_id']
    elif 'sample_count' in df.columns:
        display_df['Shared Data'] = df['sample_count'].apply(lambda x: f"{x} samples")
    
    # Add recipient
    if 'recipient_email' in df.columns:
        display_df['Recipient'] = df['recipient_email']
    
    # Add dates and expiration
    if all(col in df.columns for col in ['created_at', 'expires_at']):
        display_df['Shared On'] = df['created_at'].dt.strftime('%Y-%m-%d')
        display_df['Expires On'] = df['expires_at'].dt.strftime('%Y-%m-%d')
        
        if 'days_remaining' in df.columns:
            display_df['Days Left'] = df['days_remaining']
    
    # Add location info
    if 'destination' in df.columns:
        display_df['Location'] = df['destination']
    
    # Hidden ID for actions
    display_df['id'] = df['id']
    
    # Add checkbox column for actions
    display_df['Actions'] = False
    
    return display_df

def delete_selected_records(
    tracking_service: TrackingService,
    gcs_service: Optional[GCSService],
    record_ids: List[str]
):
    """
    Delete selected records from the tracking service
    
    Args:
        tracking_service: Tracking service instance
        gcs_service: Optional GCS service for cleanup
        record_ids: List of record IDs to delete
    """
    logger = logging.getLogger(__name__)
    
    success_count = 0
    fail_count = 0
    
    # Create a progress bar
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    for idx, record_id in enumerate(record_ids):
        progress_text.text(f"Deleting record {idx+1}/{len(record_ids)}...")
        progress_value = (idx + 1) / len(record_ids)
        progress_bar.progress(progress_value)
        
        try:
            # Delete with cleanup if GCS service is available
            cleanup_gcs = gcs_service is not None
            result = tracking_service.delete_record(record_id, cleanup_gcs)
            
            if result:
                success_count += 1
            else:
                fail_count += 1
                logger.error(f"Failed to delete record {record_id}")
        except Exception as e:
            fail_count += 1
            logger.error(f"Error deleting record {record_id}: {str(e)}")
    
    # Clear the progress
    progress_text.empty()
    progress_bar.empty()
    
    # Show results
    if success_count > 0:
        st.success(f"Successfully deleted {success_count} records")
    
    if fail_count > 0:
        st.error(f"Failed to delete {fail_count} records")
    
    # Refresh the page to update the table
    st.rerun()

def deactivate_selected_records(
    tracking_service: TrackingService,
    record_ids: List[str]
):
    """
    Deactivate selected records in the tracking service
    
    Args:
        tracking_service: Tracking service instance
        record_ids: List of record IDs to deactivate
    """
    logger = logging.getLogger(__name__)
    
    success_count = 0
    fail_count = 0
    
    # Create a progress bar
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    for idx, record_id in enumerate(record_ids):
        progress_text.text(f"Deactivating record {idx+1}/{len(record_ids)}...")
        progress_value = (idx + 1) / len(record_ids)
        progress_bar.progress(progress_value)
        
        try:
            result = tracking_service.update_record_status(record_id, False)
            
            if result:
                success_count += 1
            else:
                fail_count += 1
                logger.error(f"Failed to deactivate record {record_id}")
        except Exception as e:
            fail_count += 1
            logger.error(f"Error deactivating record {record_id}: {str(e)}")
    
    # Clear the progress
    progress_text.empty()
    progress_bar.empty()
    
    # Show results
    if success_count > 0:
        st.success(f"Successfully deactivated {success_count} records")
    
    if fail_count > 0:
        st.error(f"Failed to deactivate {fail_count} records")
    
    # Refresh the page to update the table
    st.rerun() 