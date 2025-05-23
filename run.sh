#!/bin/bash
# Environment variable setup for GCP Data Sharing Portal

# Add near the top of run.sh
if [ -f .env.sh ]; then
  source .env.sh
fi

# Default values (can be overridden by Cloud Run environment variables)
export DEFAULT_SINGLE_EXPIRATION_DAYS=${DEFAULT_SINGLE_EXPIRATION_DAYS:-7}
export DEFAULT_MULTI_EXPIRATION_DAYS=${DEFAULT_MULTI_EXPIRATION_DAYS:-30}
export LOGGING_LEVEL=${LOGGING_LEVEL:-INFO}

# Email configuration
export EMAIL_SMTP_SERVER=${EMAIL_SMTP_SERVER:-smtp.gmail.com}
export EMAIL_SMTP_PORT=${EMAIL_SMTP_PORT:-587}
export EMAIL_USE_TLS=${EMAIL_USE_TLS:-True}

# Required variables - fail if not set
if [ -z "$EMAIL_USERNAME" ]; then
  echo "ERROR: EMAIL_USERNAME environment variable is required"
  exit 1
fi

if [ -z "$EMAIL_PASSWORD" ]; then
  echo "ERROR: EMAIL_PASSWORD environment variable is required"
  exit 1
fi

if [ -z "$DEFAULT_SOURCE_BUCKET" ]; then
  echo "WARNING: DEFAULT_SOURCE_BUCKET environment variable is not set"
fi

# Set FROM address to username if not specified
export EMAIL_FROM_ADDRESS=${EMAIL_FROM_ADDRESS:-$EMAIL_USERNAME}

# Print configuration (excluding secrets)
echo "Starting application with configuration:"
echo "  DEFAULT_SOURCE_BUCKET=$DEFAULT_SOURCE_BUCKET"
echo "  EMAIL_SMTP_SERVER=$EMAIL_SMTP_SERVER"
echo "  EMAIL_SMTP_PORT=$EMAIL_SMTP_PORT" 
echo "  EMAIL_USE_TLS=$EMAIL_USE_TLS"
echo "  EMAIL_USERNAME=$EMAIL_USERNAME"
echo "  EMAIL_FROM_ADDRESS=$EMAIL_FROM_ADDRESS"
echo "  DEFAULT_SINGLE_EXPIRATION_DAYS=$DEFAULT_SINGLE_EXPIRATION_DAYS"
echo "  DEFAULT_MULTI_EXPIRATION_DAYS=$DEFAULT_MULTI_EXPIRATION_DAYS"
echo "  LOGGING_LEVEL=$LOGGING_LEVEL"

# Execute the application
cd /app
exec streamlit run app.py