# GCS Data Sharing Service

A Cloud Run service for securely sharing specific GCS folders with individual users.

## Overview

This application allows administrators to:
1. Select specific sample folders from a source GCS bucket
2. Copy them to individual user-specific buckets
3. Grant temporary access to specific users by email
4. Provide users with a download link for the data as a ZIP file

## Architecture

The service combines both the backend API and frontend admin interface in a single service:

- **Backend API**: FastAPI REST API for handling bucket operations
- **Frontend**: Streamlit admin interface
- **Storage**: Google Cloud Storage buckets
- **Deployment**: Single Google Cloud Run service

## Features

- Admin interface for selecting specific samples to share
- Secure sharing with specific users via email
- Automatic zip file creation for easy downloads
- Background processing for large files (5GB+)
- Time-limited access with bucket lifecycle policies (7 days)
- Status tracking for copy operations

## Setup and Deployment

### Prerequisites

- Google Cloud Platform account
- GCP Project with billing enabled
- Google Cloud Storage bucket containing sample data
- Service account with appropriate permissions:
  - Storage Admin (roles/storage.admin)
  - Storage Object Admin (roles/storage.objectAdmin)

### Local Development

1. Clone this repository
2. Create a `credentials.json` file with your GCP service account credentials
3. Navigate to the app directory:
   ```
   cd app
   ```
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Run the application:
   ```
   python main.py
   ```
6. Access the admin UI at http://localhost:8000/ui/
   - Default login: username: `admin` / password: `admin`

### Cloud Run Deployment

1. Make the deployment script executable:
   ```bash
   chmod +x deploy-combined.sh
   ```

2. Update the SOURCE_BUCKET variable in the script to point to your source bucket

3. Run the deployment script:
   ```bash
   ./deploy-combined.sh
   ```

4. After deployment, you'll receive URLs for:
   - Admin Panel: https://[service-url]/ui/
   - API: https://[service-url]/api/

## Usage

1. Log in to the admin panel
2. Select the sample you want to share (e.g., `889-6625`)
3. Enter the recipient's email address
4. Click "Create Share"
5. Share the download link with the user
6. The user can download all files as a ZIP by visiting the link

## Security Considerations

- The admin UI should be protected with appropriate authentication
- For production use, consider:
  - Using Identity-Aware Proxy (IAP) to protect the admin interface
  - Implementing a more robust authentication system
  - Setting up HTTPS for secure communication

## Bucket Structure

The samples should be stored in the source bucket using a consistent path structure, such as:
```
gs://your-source-bucket-name/path/to/889-6625/
                                     /file1.txt
                                     /file2.jpg
                                     /subfolder/file3.csv
```

## License

MIT 