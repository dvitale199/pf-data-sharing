# GCP Data Sharing Portal

A Streamlit-based application for sharing data samples from Google Cloud Storage with automatic expiration and tracking. **Now optimized with gcsfuse for improved performance!**

## 🚀 Performance Optimizations

This application has been optimized to use gcsfuse, which provides:
- **Efficient zip creation** - Zip files are created on disk using gcsfuse mounted files (no more in-memory operations)
- **Faster operations** - Direct bucket-to-bucket copying without downloading
- **Lower memory usage** - No need to buffer large files in memory
- **Scalable** - Can handle much larger samples without memory constraints

## Features

- **Single Sample Sharing**: Create a zip file of a sample on disk and share via email with a signed URL
- **Multi-Sample Sharing**: Copy multiple samples to a new bucket with automatic cleanup
- **Automatic Expiration**: Shared data automatically expires after a configurable period
- **Email Notifications**: Recipients receive email with download links or bucket access instructions
- **Tracking System**: Monitor all shared samples and their expiration status

## Prerequisites

- Python 3.9+
- Google Cloud Project with Storage API enabled
- Service account with appropriate permissions
- SMTP email credentials (Gmail or other provider)
- gcsfuse (for local development)

## Installation

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd gcp-data-sharing-portal
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install gcsfuse:
```bash
# On Ubuntu/Debian
export GCSFUSE_REPO=gcsfuse-`lsb_release -c -s`
echo "deb https://packages.cloud.google.com/apt $GCSFUSE_REPO main" | sudo tee /etc/apt/sources.list.d/gcsfuse.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update
sudo apt-get install gcsfuse
```

4. Set up environment variables:
```bash
cp env.example .env
# Edit .env with your configuration
```

5. Configure Google Cloud authentication:
```bash
# Option 1: Service account key (REQUIRED for signed URLs)
# Place your service account key file at ~/data-tecnica-8d915e1082d7.json
# Or set the path via environment variable:
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json

# Option 2: Application default credentials (limited functionality)
gcloud auth application-default login
```

6. Load environment variables and run with gcsfuse:
```bash
# Load all environment variables from .env file
set -a; source .env; set +a

# Run the startup script
./start_with_gcsfuse.sh
```

### Running on a GCP VM

When running on a Compute Engine VM:

1. Ensure the VM has the required scopes:
```bash
# Check current scopes
curl -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/scopes

# Should include: https://www.googleapis.com/auth/devstorage.read_write
```

2. Use a service account key for full functionality:
```bash
# The default Compute Engine service account cannot generate signed URLs
# Upload a service account key with Storage Admin permissions
```

3. Load environment variables before running:
```bash
# This exports all variables in .env file to child processes
set -a; source .env; set +a

# Then run the application
./start_with_gcsfuse.sh
```

### Docker Deployment

1. Build the Docker image:
```bash
docker build -t gcp-data-sharing .
```

2. Run with docker-compose:
```bash
# Copy and edit the example file
cp docker-compose.example.yml docker-compose.yml
# Edit docker-compose.yml with your configuration

# Run the container
docker-compose up
```

## Configuration

### Required Environment Variables

- `EMAIL_USERNAME`: SMTP username for sending emails
- `EMAIL_PASSWORD`: SMTP password or app-specific password
- `DEFAULT_SOURCE_BUCKET`: Default source bucket name

### Loading Environment Variables

The application requires environment variables to be **exported** (not just set in the current shell). Use this command to load and export all variables from your `.env` file:

```bash
set -a; source .env; set +a
```

**What this does:**
- `set -a`: Automatically export all variables that are set
- `source .env`: Load variables from the .env file
- `set +a`: Turn off automatic export

This ensures that child processes (like the Python application) can access the environment variables.

### Optional Environment Variables

- `EMAIL_SMTP_SERVER`: SMTP server address (default: smtp.gmail.com)
- `EMAIL_SMTP_PORT`: SMTP server port (default: 587)
- `EMAIL_USE_TLS`: Use TLS for SMTP (default: True)
- `EMAIL_FROM_ADDRESS`: From address for emails (default: EMAIL_USERNAME)
- `DEFAULT_SINGLE_EXPIRATION_DAYS`: Default expiration for single samples (default: 7)
- `DEFAULT_MULTI_EXPIRATION_DAYS`: Default expiration for multiple samples (default: 30)

### Google Cloud Permissions

The service account needs the following roles:
- `roles/storage.admin` on source and destination buckets
- `roles/iam.serviceAccountTokenCreator` for generating signed URLs

## Usage

1. **Configure Source Bucket**: Enter the source bucket name in the sidebar

2. **Share Single Sample**:
   - Enter the sample ID
   - Enter recipient email
   - Set expiration period
   - Click "Share Sample"
   - The app creates a zip file on disk using gcsfuse
   - Recipients receive a download link for the zip file

3. **Share Multiple Samples**:
   - Upload a CSV/TXT file with sample IDs or enter manually
   - Enter recipient email
   - Choose to create new bucket or use existing
   - Set expiration period
   - Click "Share Samples"
   - Recipients will receive bucket access

4. **Track & Manage**:
   - View all shared samples
   - Monitor expiration status
   - See sharing history

## Architecture

The application uses:
- **Streamlit** for the web interface
- **Google Cloud Storage** for data storage
- **gcsfuse** for efficient file access (mounted at `/mnt/gcs`)
- **SMTP** for email notifications
- **Signed URLs** for secure, temporary access

## Docker Deployment Notes

When running in Docker, the container requires special privileges for gcsfuse:
- `SYS_ADMIN` capability
- Access to `/dev/fuse` device
- AppArmor unconfined (or appropriate profile)

See `docker-compose.example.yml` for the complete configuration.

## Troubleshooting

### GCSFuse Issues
- Ensure the container has required capabilities (SYS_ADMIN)
- Verify credentials have bucket access
- Check bucket name is correct
- Make sure the source bucket is mounted at `/mnt/gcs/{bucket-name}`

### Email Issues
- For Gmail: Use app-specific password with 2FA enabled
- Check firewall rules for SMTP ports
- Verify SMTP server settings

### Performance
- With gcsfuse, zip files are created on disk rather than in memory
- Large samples can be zipped without memory constraints
- Bucket-to-bucket copies remain fast for multi-sample sharing

## License

[Your License Here] 