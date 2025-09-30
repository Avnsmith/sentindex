"""
Simple Sentindex API for Vercel deployment.

This is a minimal version that works without external dependencies.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import json
import httpx
import asyncio

app = FastAPI(
    title="Sentindex API",
    description="Financial index platform with AI-powered insights using Sentient LLM",
    version="1.0.0"
)

# Simple data models
class IndexRequest(BaseModel):
    index_name: str
    prices: Dict[str, float]
    method: str = "level_normalized"

class IndexResponse(BaseModel):
    index_name: str
    index_value: float
    method: str
    message: str

# Index configuration
INDEX_CONFIG = {
    "gold_silver_oil_crypto": {
        "name": "Gold-Silver-Oil-Crypto Index",
        "base_level": 1000.0,
        "base_date": "2025-01-01",
        "weights": {
            "GOLD": 0.25,
            "SILVER": 0.25,
            "OIL": 0.20,
            "BTC": 0.15,
            "ETH": 0.15
        },
        "base_prices": {
            "GOLD": 1800.0,
            "SILVER": 23.0,
            "OIL": 75.0,
            "BTC": 20000.0,
            "ETH": 1000.0
        }
    }
}

def compute_level_normalized(prices: Dict[str, float], config: Dict) -> float:
    """Compute level-based normalized index."""
    weights = config["weights"]
    base_prices = config["base_prices"]
    base_level = config["base_level"]
    
    score = 0.0
    for symbol, weight in weights.items():
        if symbol in prices and symbol in base_prices:
            if base_prices[symbol] > 0:
                normalized_price = prices[symbol] / base_prices[symbol]
                score += normalized_price * weight
    
    return round(score * base_level, 2)

async def call_sentient_api(prompt: str) -> str:
    """Call Sentient API for insights."""
    api_key = "key_4pVTEkqgJWn3ZMVz"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "dobby",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.1
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.sentient.ai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                return "No response from Sentient API"
                
    except Exception as e:
        return f"Error calling Sentient API: {str(e)}"

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Sentindex API",
        "version": "1.0.0",
        "description": "Financial index platform with AI-powered insights using Sentient LLM",
        "endpoints": {
            "health": "/health",
            "latest_index": "/v1/index/{name}/latest",
            "compute_index": "/v1/index/{name}/compute",
            "insights": "/v1/index/{name}/insights"
        },
        "status": "running"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": "2025-01-01T00:00:00Z",
        "services": {
            "api": "healthy",
            "sentient_llm": "configured"
        }
    }

@app.get("/v1/index/{name}/latest")
async def get_latest_index(name: str):
    """Get latest index value."""
    if name not in INDEX_CONFIG:
        raise HTTPException(status_code=404, detail=f"Index {name} not found")
    
    # Return demo data
    return {
        "index_name": name,
        "index_value": 1234.56,
        "method": "level_normalized",
        "timestamp": "2025-01-01T00:00:00Z",
        "message": "Demo data - use /compute endpoint for real calculations"
    }

@app.post("/v1/index/{name}/compute", response_model=IndexResponse)
async def compute_index(name: str, request: IndexRequest):
    """Compute index value."""
    if name not in INDEX_CONFIG:
        raise HTTPException(status_code=404, detail=f"Index {name} not found")
    
    config = INDEX_CONFIG[name]
    
    # Validate prices
    weights = config["weights"]
    for symbol in weights.keys():
        if symbol not in request.prices:
            raise HTTPException(status_code=400, detail=f"Missing price for {symbol}")
        if request.prices[symbol] <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid price for {symbol}")
    
    # Compute index
    if request.method == "level_normalized":
        index_value = compute_level_normalized(request.prices, config)
    else:
        raise HTTPException(status_code=400, detail="Only level_normalized method supported")
    
    return IndexResponse(
        index_name=name,
        index_value=index_value,
        method=request.method,
        message="Index calculated successfully"
    )

@app.get("/v1/index/{name}/insights")
async def get_insights(name: str):
    """Get AI insights for index."""
    if name not in INDEX_CONFIG:
        raise HTTPException(status_code=404, detail=f"Index {name} not found")
    
    config = INDEX_CONFIG[name]
    
    # Create prompt for Sentient
    prompt = f"""You are a financial analyst. Analyze the {config['name']} and provide insights.

Index Configuration:
- Weights: {config['weights']}
- Base Level: {config['base_level']}
- Base Date: {config['base_date']}

Return a JSON object with:
- summary: Brief market analysis (max 2 sentences)
- sentiment: Market sentiment (positive/negative/neutral)
- notable_events: List of notable market events

Return JSON only."""

    try:
        insights = await call_sentient_api(prompt)
        return {
            "index_name": name,
            "insights": insights,
            "timestamp": "2025-01-01T00:00:00Z",
            "source": "Sentient Dobby LLM"
        }
    except Exception as e:
        return {
            "index_name": name,
            "insights": f"Error generating insights: {str(e)}",
            "timestamp": "2025-01-01T00:00:00Z",
            "source": "Error"
        }

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    return {
        "message": "Metrics endpoint available",
        "note": "Use /health for basic status"
    }

# Export for Vercel
handler = app
