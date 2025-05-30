FROM python:3.9-slim

WORKDIR /app

# Install gcsfuse and required dependencies
RUN apt-get update && apt-get install -y \
    gnupg \
    lsb-release \
    wget \
    fuse \
    && echo "deb https://packages.cloud.google.com/apt gcsfuse-$(lsb_release -c -s) main" | tee /etc/apt/sources.list.d/gcsfuse.list \
    && wget -qO- https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - \
    && apt-get update \
    && apt-get install -y gcsfuse \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create mount point for gcsfuse
RUN mkdir -p /mnt/gcs

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]