#!/bin/bash

# Usage: ./zip_and_share.sh <SAMPLE_ID> <USER_EMAIL>
# Example: ./zip_and_share.sh 889-6625 user@example.com

set -e

BUCKET="gcp-pf-bucket"
SRC_PREFIX="FulgentTF"
DEST_PREFIX="pf_data_returns"
SAMPLE_ID="$1"
USER_EMAIL="$2"

if [[ -z "$SAMPLE_ID" || -z "$USER_EMAIL" ]]; then
  echo "Usage: $0 <SAMPLE_ID> <USER_EMAIL>"
  exit 1
fi

LOCAL_TMP="${SAMPLE_ID}_tmp"
ZIP_FILE="${SAMPLE_ID}.zip"
DEST_GCS_PATH="gs://${BUCKET}/${DEST_PREFIX}/${SAMPLE_ID}.zip"

# Clean up any previous local files
rm -rf "$LOCAL_TMP" "$ZIP_FILE"

# Create the local destination directory before downloading
mkdir -p "$LOCAL_TMP"

# Download the directory from GCS to local tmp
echo "Downloading gs://${BUCKET}/${SRC_PREFIX}/${SAMPLE_ID}/ to $LOCAL_TMP ..."
gcloud storage cp --recursive "gs://${BUCKET}/${SRC_PREFIX}/${SAMPLE_ID}" "$LOCAL_TMP"

# Zip the local directory
echo "Zipping $LOCAL_TMP to $ZIP_FILE ..."
cd "$(dirname "$LOCAL_TMP")"
zip -r "$ZIP_FILE" "$(basename "$LOCAL_TMP")"

# Upload the zip file to the destination in GCS
echo "Uploading $ZIP_FILE to $DEST_GCS_PATH ..."
gcloud storage cp "$ZIP_FILE" "$DEST_GCS_PATH"

# Grant IAM access to the user for the zip file
CONDITION_FILE=$(mktemp)
cat > "$CONDITION_FILE" <<EOF
{
  "title": "Allow read access to ${SAMPLE_ID}.zip",
  "description": "Grants read access to the zip file for $SAMPLE_ID",
  "expression": "resource.name == 'projects/_/buckets/${BUCKET}/objects/${DEST_PREFIX}/${SAMPLE_ID}.zip'"
}
EOF

echo "Granting read access to $USER_EMAIL for $DEST_GCS_PATH ..."
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="user:${USER_EMAIL}" \
  --role="roles/storage.objectViewer" \
  --condition-from-file="$CONDITION_FILE"

# Clean up local files
rm "$CONDITION_FILE"
rm -rf "$LOCAL_TMP" "$ZIP_FILE"

echo "Done. The user can access the file at:"
echo "https://storage.cloud.google.com/${BUCKET}/${DEST_PREFIX}/${SAMPLE_ID}.zip"