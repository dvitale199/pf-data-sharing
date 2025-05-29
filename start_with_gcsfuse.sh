#!/bin/bash

# Startup script for running the app with gcsfuse

# Check if source bucket is provided
if [ -z "$DEFAULT_SOURCE_BUCKET" ]; then
    echo "Error: DEFAULT_SOURCE_BUCKET environment variable not set"
    echo "Usage: DEFAULT_SOURCE_BUCKET=your-bucket ./start_with_gcsfuse.sh"
    exit 1
fi

# Create mount directory if it doesn't exist
MOUNT_DIR="/mnt/gcs"
if [ ! -d "$MOUNT_DIR" ]; then
    echo "Creating mount directory: $MOUNT_DIR"
    sudo mkdir -p "$MOUNT_DIR"
    sudo chmod 755 "$MOUNT_DIR"
fi

# Check if already mounted
if mountpoint -q "$MOUNT_DIR/$DEFAULT_SOURCE_BUCKET"; then
    echo "GCSFuse already mounted at $MOUNT_DIR/$DEFAULT_SOURCE_BUCKET"
else
    # Mount the bucket using gcsfuse
    echo "Mounting $DEFAULT_SOURCE_BUCKET to $MOUNT_DIR/$DEFAULT_SOURCE_BUCKET"
    sudo mkdir -p "$MOUNT_DIR/$DEFAULT_SOURCE_BUCKET"
    sudo chown $USER:$USER "$MOUNT_DIR/$DEFAULT_SOURCE_BUCKET"
    gcsfuse --implicit-dirs --file-mode=644 --dir-mode=755 "$DEFAULT_SOURCE_BUCKET" "$MOUNT_DIR/$DEFAULT_SOURCE_BUCKET"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to mount bucket with gcsfuse"
        exit 1
    fi
fi

echo "GCSFuse mounted successfully"
echo "Starting Streamlit application..."

# Run the Streamlit app
streamlit run app.py 