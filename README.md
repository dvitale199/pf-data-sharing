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

### Environment Variables

The application requires several environment variables for proper configuration. Create a `.env` file in the project root or set these variables in your deployment environment:

**Quick Start**: Copy `env.example` to `.env` and update with your values:
```bash
cp env.example .env
```

#### Required Variables

```bash
# Email Configuration (Required)
EMAIL_USERNAME=your-email@example.com
EMAIL_PASSWORD=your-app-password-or-smtp-password
```

#### Optional Variables with Defaults

```bash
# Source Bucket Configuration
DEFAULT_SOURCE_BUCKET=your-source-bucket-name

# Email Server Settings (defaults shown)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USE_TLS=True
EMAIL_FROM_ADDRESS=your-email@example.com  # defaults to EMAIL_USERNAME

# Expiration Settings (in days)
DEFAULT_SINGLE_EXPIRATION_DAYS=7
DEFAULT_MULTI_EXPIRATION_DAYS=30

# Source Data Prefix (if your data is nested in a subfolder)
DEFAULT_SOURCE_PREFIX=path/to/samples

# Logging
LOGGING_LEVEL=INFO
```

#### GCP Authentication

```bash
# Option 1: Service Account Key File
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Option 2: Use gcloud CLI authentication (for local development)
# Run: gcloud auth application-default login
```

#### Email Setup Notes

For **Gmail** users:
1. Enable 2-factor authentication on your Google account
2. Generate an "App Password" for this application
3. Use your Gmail address as `EMAIL_USERNAME`
4. Use the generated app password as `EMAIL_PASSWORD`

For **other SMTP providers**, adjust the `EMAIL_SMTP_SERVER` and `EMAIL_SMTP_PORT` accordingly.

#### Example .env File

```bash
# Required
EMAIL_USERNAME=myapp@gmail.com
EMAIL_PASSWORD=abcd-efgh-ijkl-mnop

# Optional but recommended
DEFAULT_SOURCE_BUCKET=my-data-bucket
EMAIL_FROM_ADDRESS=Data Sharing Portal <myapp@gmail.com>
DEFAULT_SINGLE_EXPIRATION_DAYS=7
DEFAULT_MULTI_EXPIRATION_DAYS=30
LOGGING_LEVEL=INFO

# If using service account
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
```

### Local Development

1. Clone this repository
2. Create a `.env` file with the required environment variables (see Environment Variables section above)
3. Create a `credentials.json` file with your GCP service account credentials (if using service account authentication)
4. Navigate to the app directory:
   ```
   cd app
   ```
5. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
6. Run the application:
   ```
   python main.py
   ```
7. Access the admin UI at http://localhost:8000/ui/
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