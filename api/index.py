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

# Import the FastAPI app
from api.main import app

# Export the app for Vercel
handler = app
