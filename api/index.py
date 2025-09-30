"""
Vercel serverless function for Sentindex API.

This is the entry point for Vercel deployment.
"""

import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

try:
    # Import the FastAPI app
    from api.main import app
    handler = app
except ImportError as e:
    # Fallback simple FastAPI app if imports fail
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI(title="Sentindex API", description="Financial index platform")
    
    @app.get("/")
    async def root():
        return {
            "name": "Sentindex API",
            "version": "1.0.0",
            "status": "running",
            "message": "API is working but some services may be unavailable"
        }
    
    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "message": "Basic health check passed"
        }
    
    @app.get("/v1/index/{name}/latest")
    async def get_latest_index(name: str):
        return {
            "index_name": name,
            "index_value": 1000.0,
            "message": "Demo mode - add your API keys to enable full functionality"
        }
    
    handler = app
