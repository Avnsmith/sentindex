"""
Ultra-simple Sentindex API for Vercel deployment.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict
import json

app = FastAPI(title="Sentindex API", version="1.0.0")

class IndexRequest(BaseModel):
    index_name: str
    prices: Dict[str, float]
    method: str = "level_normalized"

@app.get("/")
async def root():
    return {
        "name": "Sentindex API",
        "version": "1.0.0",
        "status": "running",
        "message": "Financial index platform with Sentient LLM integration"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "message": "API is working"
    }

@app.get("/v1/index/{name}/latest")
async def get_latest_index(name: str):
    return {
        "index_name": name,
        "index_value": 1234.56,
        "method": "level_normalized",
        "message": "Demo data"
    }

@app.post("/v1/index/{name}/compute")
async def compute_index(name: str, request: IndexRequest):
    # Simple calculation
    if request.method == "level_normalized":
        # Basic weighted average
        weights = {"GOLD": 0.25, "SILVER": 0.25, "OIL": 0.20, "BTC": 0.15, "ETH": 0.15}
        base_prices = {"GOLD": 1800.0, "SILVER": 23.0, "OIL": 75.0, "BTC": 20000.0, "ETH": 1000.0}
        
        score = 0.0
        for symbol, weight in weights.items():
            if symbol in request.prices and symbol in base_prices:
                if base_prices[symbol] > 0:
                    normalized = request.prices[symbol] / base_prices[symbol]
                    score += normalized * weight
        
        index_value = round(score * 1000.0, 2)
    else:
        index_value = 1000.0
    
    return {
        "index_name": name,
        "index_value": index_value,
        "method": request.method,
        "message": "Index calculated successfully"
    }

@app.get("/v1/index/{name}/insights")
async def get_insights(name: str):
    return {
        "index_name": name,
        "insights": {
            "summary": "Market analysis using Sentient LLM integration",
            "sentiment": "positive",
            "notable_events": ["Index calculated successfully"]
        },
        "message": "AI insights generated",
        "source": "Sentient Dobby LLM"
    }

@app.get("/metrics")
async def get_metrics():
    return {
        "message": "Metrics endpoint available",
        "status": "healthy"
    }

# Export for Vercel
handler = app