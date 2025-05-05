import streamlit as st
import requests
import os
import pandas as pd
from datetime import datetime
import json

# API endpoint
API_URL = os.environ.get("API_URL", "http://localhost:8000/api")

st.set_page_config(
    page_title="GCS Data Sharing Admin",
    page_icon="🗂️",
    layout="wide"
)

st.title("GCS Data Sharing Admin Panel")

# Authentication (simplified - would need proper auth in production)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.header("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
        
        if submit_button:
            # Simple hardcoded auth for demo (replace with proper auth)
            if username == "admin" and password == "admin":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid credentials")
    
    st.stop()

# Main admin interface
tab1, tab2 = st.tabs(["Share Samples", "Manage Shares"])

with tab1:
    st.header("Share Sample Data")
    
    # Get available samples
    try:
        response = requests.get(f"{API_URL}/samples")
        if response.status_code == 200:
            samples = response.json().get("samples", [])
        else:
            st.error(f"Error fetching samples: {response.text}")
            samples = []
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        samples = []
    
    if not samples:
        st.warning("No samples available or couldn't connect to the API.")
        sample_placeholder = st.empty()
        samples = ["889-6625"]  # Fallback for demo
    
    # Share form
    with st.form("share_form"):
        # Sample selection
        selected_sample = st.selectbox(
            "Select Sample ID", 
            options=samples,
            help="Choose the sample folder you want to share"
        )
        
        # User email
        user_email = st.text_input(
            "Recipient Email",
            help="Email address of the user who will receive access to this data"
        )
        
        # Submit button
        submit_button = st.form_submit_button("Create Share")
        
        if submit_button:
            if not selected_sample or not user_email:
                st.warning("Please select a sample and enter a user email")
            else:
                try:
                    with st.spinner("Creating share..."):
                        response = requests.post(
                            f"{API_URL}/share-sample",
                            json={"sample_id": selected_sample, "user_email": user_email}
                        )
                        
                        if response.status_code == 200:
                            share_data = response.json()
                            st.success(f"Sample {selected_sample} has been shared with {user_email}")
                            
                            # Display share details
                            st.json(share_data)
                            
                            # Get base URL for the application
                            base_url = API_URL.replace("/api", "")
                            
                            # Display download link for admin
                            st.markdown(f"**Download URL for user:** {base_url}{share_data['download_url']}")
                            st.info("The sample is being copied to the shared bucket. The download will be available once the copy completes.")
                        else:
                            st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Error creating share: {str(e)}")

with tab2:
    st.header("Manage Existing Shares")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Refresh Shares"):
            st.rerun()
    
    # Get all active shares
    try:
        with st.spinner("Loading shares..."):
            response = requests.get(f"{API_URL}/shares")
            if response.status_code == 200:
                shares = response.json().get("shares", [])
            else:
                st.error(f"Error fetching shares: {response.text}")
                shares = []
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
        shares = []
        
    if not shares:
        st.info("No active shares found")
    else:
        # Convert to DataFrame for better display
        df = pd.DataFrame(shares)
        
        # Format timestamps
        if "created" in df.columns:
            df["created"] = pd.to_datetime(df["created"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Add status colors
        def highlight_status(val):
            if val == "completed":
                return "background-color: #d4f7d4"  # Light green
            elif val == "copying":
                return "background-color: #fff2cc"  # Light yellow
            elif val == "failed":
                return "background-color: #f7d4d4"  # Light red
            return ""
            
        # Apply styling if status column exists
        if "status" in df.columns:
            styled_df = df.style.map(highlight_status, subset=["status"])
            st.dataframe(styled_df)
        else:
            st.dataframe(df)
        
        # Delete functionality
        st.subheader("Delete Share")
        with st.form("delete_form"):
            share_to_delete = st.selectbox("Select Share ID to Delete", options=[s["share_id"] for s in shares])
            
            submit_button = st.form_submit_button("Delete Selected Share")
            if submit_button:
                try:
                    with st.spinner("Deleting share..."):
                        response = requests.delete(f"{API_URL}/shares/{share_to_delete}")
                        
                        if response.status_code == 200:
                            st.success(f"Share {share_to_delete} has been deleted")
                            st.rerun()
                        else:
                            st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Error deleting share: {str(e)}")

# Add a footer
st.markdown("---")
st.markdown("**GCS Data Sharing Admin Panel** | Developed for data sharing and access control") 