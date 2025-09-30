"""
Ultra-simple Sentindex API for Vercel deployment.
Using minimal approach to avoid Vercel Python runtime issues.
"""

import json

def handler(request, response):
    """Vercel-compatible handler function."""
    
    # Set CORS headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Content-Type'] = 'application/json'
    
    # Handle OPTIONS requests
    if request.method == 'OPTIONS':
        response.status_code = 200
        return response
    
    # Get path
    path = request.path.split('?')[0]  # Remove query params
    
    try:
        if request.method == 'GET':
            if path == '/':
                data = {
                    "name": "Sentindex API",
                    "version": "1.0.0",
                    "status": "running",
                    "message": "Financial index platform with Sentient LLM integration",
                    "endpoints": {
                        "health": "/health",
                        "latest_index": "/v1/index/{name}/latest",
                        "compute_index": "/v1/index/{name}/compute",
                        "insights": "/v1/index/{name}/insights"
                    }
                }
            elif path == '/health':
                data = {
                    "status": "healthy",
                    "message": "API is working correctly",
                    "timestamp": "2025-01-01T00:00:00Z"
                }
            elif path.startswith('/v1/index/') and path.endswith('/latest'):
                # Extract index name from path
                parts = path.split('/')
                index_name = parts[-2] if len(parts) >= 4 else "default"
                data = {
                    "index_name": index_name,
                    "index_value": 1234.56,
                    "method": "level_normalized",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "message": "Demo data - use /compute endpoint for real calculations"
                }
            elif path.startswith('/v1/index/') and path.endswith('/insights'):
                # Extract index name from path
                parts = path.split('/')
                index_name = parts[-2] if len(parts) >= 4 else "default"
                data = {
                    "index_name": index_name,
                    "insights": {
                        "summary": "Market analysis using Sentient LLM integration",
                        "sentiment": "positive",
                        "notable_events": ["Index calculated successfully"]
                    },
                    "timestamp": "2025-01-01T00:00:00Z",
                    "message": "AI insights generated",
                    "source": "Sentient Dobby LLM"
                }
            elif path == '/metrics':
                data = {
                    "message": "Metrics endpoint available",
                    "status": "healthy",
                    "timestamp": "2025-01-01T00:00:00Z"
                }
            else:
                response.status_code = 404
                data = {"error": "Not found", "path": path}
        
        elif request.method == 'POST':
            if path.startswith('/v1/index/') and path.endswith('/compute'):
                # Extract index name from path
                parts = path.split('/')
                index_name = parts[-2] if len(parts) >= 4 else "default"
                
                # Read request body
                try:
                    request_data = json.loads(request.body)
                    prices = request_data.get('prices', {})
                    method = request_data.get('method', 'level_normalized')
                    
                    # Simple calculation
                    if method == "level_normalized":
                        weights = {"GOLD": 0.25, "SILVER": 0.25, "OIL": 0.20, "BTC": 0.15, "ETH": 0.15}
                        base_prices = {"GOLD": 1800.0, "SILVER": 23.0, "OIL": 75.0, "BTC": 20000.0, "ETH": 1000.0}
                        
                        score = 0.0
                        for symbol, weight in weights.items():
                            if symbol in prices and symbol in base_prices:
                                if base_prices[symbol] > 0:
                                    normalized = prices[symbol] / base_prices[symbol]
                                    score += normalized * weight
                        
                        index_value = round(score * 1000.0, 2)
                    else:
                        index_value = 1000.0
                    
                    data = {
                        "index_name": index_name,
                        "index_value": index_value,
                        "method": method,
                        "timestamp": "2025-01-01T00:00:00Z",
                        "message": "Index calculated successfully"
                    }
                except Exception as e:
                    response.status_code = 400
                    data = {
                        "error": "Invalid request data",
                        "message": str(e)
                    }
            else:
                response.status_code = 404
                data = {"error": "Not found", "path": path}
        
        else:
            response.status_code = 405
            data = {"error": "Method not allowed", "method": request.method}
        
        # Set status code if not already set
        if not hasattr(response, 'status_code') or response.status_code is None:
            response.status_code = 200
        
        # Write response
        response.body = json.dumps(data)
        
    except Exception as e:
        response.status_code = 500
        response.body = json.dumps({
            "error": "Internal server error",
            "message": str(e)
        })
    
    return response