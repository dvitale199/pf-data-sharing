# GCP Data Sharing Portal

A Streamlit application for sharing data from GCP buckets with specific recipients. The application provides both single sample sharing (with automatic zipping) and multi-sample sharing functionality, while tracking all shared data.

## Features

- Share a single sample with automatic zipping and secure download link
- Share multiple samples to a new or existing bucket with access control
- Track all shared samples with expiration management
- Automated email notifications to recipients
- Automatic lifecycle management for deletion after expiration

## Project Structure

```
src/
└── core/
    ├── app.py                 # Main application entry point
    ├── requirements.txt       # Project dependencies
    ├── components/
    │   ├── single_sample.py   # Single sample sharing component
    │   ├── multi_sample.py    # Multi-sample sharing component
    │   └── tracking.py        # Tracking and management component
    ├── services/
    │   ├── gcs_service.py     # Google Cloud Storage operations
    │   ├── email_service.py   # Email sending functionality
    │   └── tracking_service.py  # Tracking state management
    └── utils/
        ├── auth.py            # Authentication utilities
        └── file_operations.py # File handling utilities
```

## Setup Instructions

### Prerequisites

1. Python 3.7 or higher
2. Google Cloud Platform account with storage access
3. SendGrid account for email notifications

### Environment Setup

1. Set up GCP authentication:
   ```bash
   gcloud auth application-default login
   ```

2. Configure environment variables:
   ```bash
   export SENDGRID_API_KEY="your_sendgrid_api_key"
   export SENDGRID_FROM_EMAIL="your_verified_sender_email"
   export DEFAULT_SOURCE_BUCKET="your_default_source_bucket"
   ```

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

```bash
cd src/core
streamlit run app.py
```

The application will be available at http://localhost:8501

## Usage Guide

### Sharing a Single Sample

1. Navigate to "Share Single Sample" in the sidebar
2. Enter a sample ID and recipient email
3. Adjust expiration time if needed
4. Click "Share Sample"

The application will:
- Create a zip file with all sample data
- Store it in a temporary bucket
- Generate a signed URL
- Send an email to the recipient with the download link
- Track the shared sample

### Sharing Multiple Samples

1. Navigate to "Share Multiple Samples" in the sidebar
2. Upload a CSV/TXT file with sample IDs or enter them manually
3. Enter recipient email
4. Choose to create a new bucket or use an existing one
5. Click "Share Samples"

The application will:
- Copy all sample files to the destination bucket
- Grant access to the recipient
- Send an email notification with access information
- Track the shared samples

### Tracking Shared Samples

1. Navigate to "Track & Manage" in the sidebar
2. View all shared samples with their status
3. Filter by recipient, type, or expiration
4. Select samples to delete or deactivate

## Troubleshooting

- **Authentication issues**: Ensure you've run `gcloud auth application-default login`
- **Email sending fails**: Verify your SendGrid API key and sender email
- **Missing samples**: Check that the source bucket contains the requested sample IDs
- **Permission errors**: Ensure your GCP account has storage admin permissions 