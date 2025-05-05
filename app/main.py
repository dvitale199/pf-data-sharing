import os
import sys
import subprocess
import threading
import logging
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import the API routes
from api.routes import api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="GCS Data Sharing Service")

# Mount the API router
app.include_router(api_router, prefix="/api")

# Default route redirects to Streamlit frontend
@app.get("/")
async def redirect_to_streamlit():
    return RedirectResponse(url="/ui/")

def start_streamlit():
    """Start Streamlit server as a subprocess"""
    # Set environment variables for Streamlit
    env = os.environ.copy()
    env["API_URL"] = "http://localhost:8000/api"
    
    # Start Streamlit server
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run", 
        "frontend/streamlit_app.py",
        "--server.port=8501",
        "--server.address=0.0.0.0",
        "--server.baseUrlPath=/ui",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false"
    ]
    
    logger.info(f"Starting Streamlit with command: {' '.join(streamlit_cmd)}")
    
    try:
        process = subprocess.Popen(
            streamlit_cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Log Streamlit output
        for line in process.stdout:
            logger.info(f"Streamlit: {line.strip()}")
            
    except Exception as e:
        logger.error(f"Error starting Streamlit: {str(e)}")

# Function to create a reverse proxy route for Streamlit
@app.get("/ui{path:path}")
async def streamlit_proxy(request: Request, path: str):
    """Proxy requests to Streamlit server"""
    # In a production environment, you would implement proper reverse proxy
    # For this example, we'll redirect to the Streamlit port
    return RedirectResponse(url=f"http://localhost:8501{path}")

if __name__ == "__main__":
    # Start Streamlit in a separate thread
    streamlit_thread = threading.Thread(target=start_streamlit)
    streamlit_thread.daemon = True
    streamlit_thread.start()
    
    # Start FastAPI
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 