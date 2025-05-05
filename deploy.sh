#!/bin/bash
set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SOURCE_BUCKET="your-source-bucket-name"  # Change this to your source bucket name

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Deploying GCS Data Sharing Service to Cloud Run${NC}"
echo -e "Project ID: ${GREEN}${PROJECT_ID}${NC}"
echo -e "Region: ${GREEN}${REGION}${NC}"
echo -e "Source Bucket: ${GREEN}${SOURCE_BUCKET}${NC}"
echo

# Build and deploy the combined service
echo -e "${YELLOW}Building and deploying combined service...${NC}"
gcloud builds submit --tag gcr.io/${PROJECT_ID}/gcs-data-sharing-service ./app

echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy gcs-data-sharing-service \
  --image gcr.io/${PROJECT_ID}/gcs-data-sharing-service \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --set-env-vars "SOURCE_BUCKET=${SOURCE_BUCKET}"

# Get the service URL
SERVICE_URL=$(gcloud run services describe gcs-data-sharing-service \
  --platform managed \
  --region ${REGION} \
  --format 'value(status.url)')

echo -e "${GREEN}Service deployed at: ${SERVICE_URL}${NC}"
echo
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "Admin Panel URL: ${GREEN}${SERVICE_URL}/ui${NC}"
echo -e "API URL: ${GREEN}${SERVICE_URL}/api${NC}"
echo
echo -e "${YELLOW}Default login:${NC}"
echo -e "Username: ${GREEN}admin${NC}"
echo -e "Password: ${GREEN}admin${NC}"
echo
echo -e "${RED}WARNING: For production use, please set up proper authentication!${NC}" 