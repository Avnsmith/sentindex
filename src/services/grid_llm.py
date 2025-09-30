"""
Sentient LLM integration for Sentindex.

Provides AI-powered insights for financial indices with structured JSON output
and schema validation using Sentient Dobby LLM.
"""

import json
import logging
from typing import Dict, Any, Optional
import httpx
from pydantic import ValidationError

from ..models.data_models import LLMInsightRequest, LLMInsightResponse
from ..utils.config import get_config
from ..utils.metrics import get_metrics

logger = logging.getLogger(__name__)


class SentientLLMService:
    """Sentient LLM service for generating financial insights."""
    
    def __init__(self, config):
        self.config = config
        self.sentient_config = config.get_sentient_config()
        self.metrics = get_metrics()
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # LLM prompt template
        self.prompt_template = self._create_prompt_template()
        
        # JSON schema for response validation
        self.response_schema = self._create_response_schema()
    
    def _create_prompt_template(self) -> str:
        """Create the LLM prompt template."""
        return """You are a financial analyst. Input contains latest prices and sources. Return EXACTLY a JSON object with keys: index, index_delta_24h_pct, summary (max 2 sentences), notable_events[], sentiment:{BTC,ETH}. Do not add extra text.

Input:
- GOLD: {gold_price} (source {gold_source}, {gold_timestamp})
- SILVER: {silver_price} (source {silver_source}, {silver_timestamp})
- OIL: {oil_price} (source {oil_source}, {oil_timestamp})
- BTC: {btc_price} (source {btc_source}, {btc_timestamp})
- ETH: {eth_price} (source {eth_source}, {eth_timestamp})
Index weights: GOLD {gold_weight}%, SILVER {silver_weight}%, OIL {oil_weight}%, BTC {btc_weight}%, ETH {eth_weight}%.
Base index level: {base_level} (base date: {base_date})
Current index value: {index_value}
24h change: {delta_24h_pct}%

Return JSON only."""
    
    def _create_response_schema(self) -> Dict[str, Any]:
        """Create JSON schema for response validation."""
        return {
            "type": "object",
            "properties": {
                "index": {
                    "type": "number",
                    "description": "Index value"
                },
                "index_delta_24h_pct": {
                    "type": "number",
                    "description": "24-hour percentage change"
                },
                "summary": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Brief summary (max 2 sentences)"
                },
                "notable_events": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Notable market events"
                },
                "sentiment": {
                    "type": "object",
                    "properties": {
                        "BTC": {
                            "type": "string",
                            "enum": ["positive", "negative", "neutral"]
                        },
                        "ETH": {
                            "type": "string",
                            "enum": ["positive", "negative", "neutral"]
                        }
                    },
                    "required": ["BTC", "ETH"],
                    "additionalProperties": false
                }
            },
            "required": ["index", "index_delta_24h_pct", "summary", "notable_events", "sentiment"],
            "additionalProperties": false
        }
    
    async def generate_insights(self, request: LLMInsightRequest) -> LLMInsightResponse:
        """
        Generate AI insights for an index.
        
        Args:
            request: Insight request with index data
            
        Returns:
            Structured LLM insights
            
        Raises:
            ValueError: If LLM response is invalid
            httpx.HTTPError: If API request fails
        """
        try:
            with self.metrics.timer("llm", {"model": self.grid_config.get("model", "gpt-4")}):
                # Prepare prompt
                prompt = self._prepare_prompt(request)
                
                # Call Sentient API
                response = await self._call_sentient_api(prompt)
                
                # Parse and validate response
                insights = self._parse_response(response)
                
                # Update metrics
                self.metrics.increment_llm_requests(
                    self.sentient_config.get("model", "dobby"), "success"
                )
                
                return insights
                
        except ValidationError as e:
            logger.error(f"LLM response validation error: {e}")
            self.metrics.increment_llm_requests(
                self.sentient_config.get("model", "dobby"), "validation_error"
            )
            raise ValueError(f"Invalid LLM response: {e}")
        
        except httpx.HTTPError as e:
            logger.error(f"Sentient API error: {e}")
            self.metrics.increment_llm_requests(
                self.sentient_config.get("model", "dobby"), "api_error"
            )
            raise
        
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            self.metrics.increment_llm_requests(
                self.sentient_config.get("model", "dobby"), "error"
            )
            raise
    
    def _prepare_prompt(self, request: LLMInsightRequest) -> str:
        """Prepare the LLM prompt with request data."""
        # Extract prices and sources
        prices = request.prices
        sources = request.sources
        
        # Format weights as percentages
        weights = request.weights
        weight_pct = {k: int(v * 100) for k, v in weights.items()}
        
        # Prepare prompt data
        prompt_data = {
            "gold_price": prices.get("GOLD", 0),
            "gold_source": sources.get("GOLD", "Unknown"),
            "gold_timestamp": "2025-09-30T07:40:00Z",  # TODO: Get actual timestamp
            "silver_price": prices.get("SILVER", 0),
            "silver_source": sources.get("SILVER", "Unknown"),
            "silver_timestamp": "2025-09-30T07:40:00Z",
            "oil_price": prices.get("OIL", 0),
            "oil_source": sources.get("OIL", "Unknown"),
            "oil_timestamp": "2025-09-30T07:40:00Z",
            "btc_price": prices.get("BTC", 0),
            "btc_source": sources.get("BTC", "Unknown"),
            "btc_timestamp": "2025-09-30T07:40:00Z",
            "eth_price": prices.get("ETH", 0),
            "eth_source": sources.get("ETH", "Unknown"),
            "eth_timestamp": "2025-09-30T07:40:00Z",
            "gold_weight": weight_pct.get("GOLD", 25),
            "silver_weight": weight_pct.get("SILVER", 25),
            "oil_weight": weight_pct.get("OIL", 20),
            "btc_weight": weight_pct.get("BTC", 15),
            "eth_weight": weight_pct.get("ETH", 15),
            "base_level": request.base_level,
            "base_date": request.base_date,
            "index_value": request.index_value,
            "delta_24h_pct": request.delta_24h_pct
        }
        
        return self.prompt_template.format(**prompt_data)
    
    async def _call_sentient_api(self, prompt: str) -> str:
        """Call Sentient API with the prompt."""
        api_key = self.sentient_config.get("api_key")
        if not api_key:
            raise ValueError("Sentient API key not configured")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.sentient_config.get("model", "dobby"),
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": self.sentient_config.get("max_tokens", 1000),
            "temperature": self.sentient_config.get("temperature", 0.1),
            "response_format": {
                "type": "json_object"
            }
        }
        
        base_url = self.sentient_config.get("base_url", "https://api.sentient.ai")
        url = f"{base_url}/v1/chat/completions"
        
        response = await self.client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        # Extract content from response
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            
            # Update token usage metrics
            if "usage" in result:
                usage = result["usage"]
                self.metrics.add_llm_tokens(
                    self.sentient_config.get("model", "dobby"),
                    "prompt",
                    usage.get("prompt_tokens", 0)
                )
                self.metrics.add_llm_tokens(
                    self.sentient_config.get("model", "dobby"),
                    "completion",
                    usage.get("completion_tokens", 0)
                )
            
            return content
        else:
            raise ValueError("Invalid response from Sentient API")
    
    def _parse_response(self, response_text: str) -> LLMInsightResponse:
        """Parse and validate LLM response."""
        try:
            # Try to extract JSON from response
            json_text = self._extract_json(response_text)
            
            # Parse JSON
            data = json.loads(json_text)
            
            # Validate against schema
            self._validate_schema(data)
            
            # Create response object
            return LLMInsightResponse(
                index=float(data["index"]),
                index_delta_24h_pct=float(data["index_delta_24h_pct"]),
                summary=data["summary"],
                notable_events=data["notable_events"],
                sentiment=data["sentiment"]
            )
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {e}")
        except KeyError as e:
            raise ValueError(f"Missing required field in LLM response: {e}")
        except Exception as e:
            raise ValueError(f"Error parsing LLM response: {e}")
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response text."""
        # Look for JSON object in the response
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
            raise ValueError("No JSON object found in response")
        
        return text[start_idx:end_idx + 1]
    
    def _validate_schema(self, data: Dict[str, Any]):
        """Validate response against JSON schema."""
        # Check required fields
        required_fields = ["index", "index_delta_24h_pct", "summary", "notable_events", "sentiment"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate sentiment values
        valid_sentiments = {"positive", "negative", "neutral"}
        sentiment = data["sentiment"]
        
        if not isinstance(sentiment, dict):
            raise ValueError("Sentiment must be an object")
        
        for asset, sentiment_value in sentiment.items():
            if sentiment_value not in valid_sentiments:
                raise ValueError(f"Invalid sentiment for {asset}: {sentiment_value}")
        
        # Validate summary length
        summary = data["summary"]
        if len(summary) > 200:
            raise ValueError("Summary too long (max 200 characters)")
        
        # Validate notable_events is a list
        if not isinstance(data["notable_events"], list):
            raise ValueError("Notable events must be a list")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
async def test_sentient_service():
    config = get_config()
    service = SentientLLMService(config)
        
        # Create test request
        request = LLMInsightRequest(
            index_name="test_index",
            index_value=1234.56,
            delta_24h_pct=1.5,
            prices={
                "GOLD": 1900.12,
                "SILVER": 24.31,
                "OIL": 78.45,
                "BTC": 27450.0,
                "ETH": 1850.0
            },
            sources={
                "GOLD": "AlphaVantage",
                "SILVER": "Yahoo",
                "OIL": "EIA",
                "BTC": "CoinGecko",
                "ETH": "CoinGecko"
            },
            weights={
                "GOLD": 0.25,
                "SILVER": 0.25,
                "OIL": 0.20,
                "BTC": 0.15,
                "ETH": 0.15
            },
            base_prices={
                "GOLD": 1800.0,
                "SILVER": 23.0,
                "OIL": 75.0,
                "BTC": 20000.0,
                "ETH": 1000.0
            },
            base_level=1000.0,
            base_date="2025-01-01"
        )
        
        try:
            insights = await service.generate_insights(request)
            print("Generated insights:")
            print(json.dumps(insights.dict(), indent=2))
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await service.close()
    
    asyncio.run(test_sentient_service())
