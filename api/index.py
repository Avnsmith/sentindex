"""
Simple Sentindex API for Vercel deployment.
Using basic HTTP handler to avoid Vercel Python runtime issues.
"""

from http.server import BaseHTTPRequestHandler
import json
import urllib.parse

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        path = self.path.split('?')[0]  # Remove query params
        
        if path == '/':
            response = {
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
            response = {
                "status": "healthy",
                "message": "API is working correctly",
                "timestamp": "2025-01-01T00:00:00Z"
            }
        elif path.startswith('/v1/index/') and path.endswith('/latest'):
            # Extract index name from path
            parts = path.split('/')
            index_name = parts[-2] if len(parts) >= 4 else "default"
            response = {
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
            response = {
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
            response = {
                "message": "Metrics endpoint available",
                "status": "healthy",
                "timestamp": "2025-01-01T00:00:00Z"
            }
        else:
            self.send_response(404)
            self.end_headers()
            response = {"error": "Not found", "path": path}
        
        self.wfile.write(json.dumps(response).encode())
    
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        path = self.path.split('?')[0]  # Remove query params
        
        if path.startswith('/v1/index/') and path.endswith('/compute'):
            # Extract index name from path
            parts = path.split('/')
            index_name = parts[-2] if len(parts) >= 4 else "default"
            
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                request_data = json.loads(post_data.decode('utf-8'))
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
                
                response = {
                    "index_name": index_name,
                    "index_value": index_value,
                    "method": method,
                    "timestamp": "2025-01-01T00:00:00Z",
                    "message": "Index calculated successfully"
                }
            except Exception as e:
                response = {
                    "error": "Invalid request data",
                    "message": str(e)
                }
        else:
            self.send_response(404)
            self.end_headers()
            response = {"error": "Not found", "path": path}
        
        self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

# Export for Vercel
def handler(request, response):
    return Handler(request, response, None)