import streamlit as st
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.core.services.tracking_service import TrackingService
from src.core.services.gcs_service import GCSService

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
    
    # Add refresh button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh", help="Reload tracking data from file"):
            st.rerun()
    
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
        
        # Display the data as a read-only table
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
                "GCS Path": st.column_config.TextColumn(
                    "GCS Path",
                    help="Full path to zip file in Google Cloud Storage (copy this to search in GCS console)",
                    width="large"
                ),
                "id": None,  # Hide the ID column
            },
            hide_index=True,
            use_container_width=True
        )
        
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
    
    # Add location/file info with better specificity
    location_data = []
    for _, row in df.iterrows():
        if row.get('type') == 'single' and 'zip_file_path' in row and pd.notna(row['zip_file_path']):
            # For single samples, show the zip file path
            zip_path = row['zip_file_path']
            # Extract just the filename for easier identification
            if '/' in zip_path:
                filename = zip_path.split('/')[-1]
                location_data.append(f"📁 {filename}")
            else:
                location_data.append(f"📁 {zip_path}")
        elif row.get('type') == 'multi' and 'destination' in row and pd.notna(row['destination']):
            # For multi samples, show the destination bucket
            location_data.append(f"🗂️ {row['destination']}")
        else:
            location_data.append("❓ Unknown")
    
    if location_data:
        display_df['File/Location'] = location_data
    
    # Add full path column for zip files (useful for GCS console)
    if 'zip_file_path' in df.columns:
        zip_paths = []
        for _, row in df.iterrows():
            if row.get('type') == 'single' and pd.notna(row.get('zip_file_path')):
                zip_paths.append(row['zip_file_path'])
            else:
                zip_paths.append("")
        
        # Only add the column if there are actual zip paths
        if any(zip_paths):
            display_df['GCS Path'] = zip_paths
    
    # Hidden ID for actions (kept hidden)
    display_df['id'] = df['id']
    
    return display_df 