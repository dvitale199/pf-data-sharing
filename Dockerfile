FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY src/core/ .

# Make run.sh executable
COPY run.sh .
RUN chmod +x run.sh

# Container will run using this script as entrypoint
ENTRYPOINT ["/app/run.sh"]