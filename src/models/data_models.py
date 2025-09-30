"""
Data models for Sentindex.

Defines Pydantic models for normalized data schema, index values,
and API request/response structures.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, validator
import json


class PriceData(BaseModel):
    """Normalized price data from any source."""
    
    symbol: str = Field(..., description="Asset symbol (e.g., GOLD, BTC)")
    price: float = Field(..., gt=0, description="Price value")
    unit: str = Field(..., description="Price unit (e.g., USD/oz, USD)")
    timestamp: datetime = Field(..., description="Data timestamp")
    source: str = Field(..., description="Data source (e.g., AlphaVantage)")
    source_id: Optional[str] = Field(None, description="Source-specific ID")
    confidence: float = Field(..., ge=0, le=1, description="Data confidence score")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class IndexValue(BaseModel):
    """Index calculation result."""
    
    index_name: str = Field(..., description="Index identifier")
    index_value: float = Field(..., description="Calculated index value")
    timestamp: datetime = Field(..., description="Calculation timestamp")
    method: str = Field(..., description="Calculation method (level_normalized, return_based)")
    delta_24h_pct: Optional[float] = Field(None, description="24-hour percentage change")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class IndexConfig(BaseModel):
    """Index configuration."""
    
    name: str = Field(..., description="Index display name")
    base_level: float = Field(..., description="Base index level")
    base_date: str = Field(..., description="Base date for calculations")
    weights: Dict[str, float] = Field(..., description="Asset weights")
    base_prices: Dict[str, float] = Field(..., description="Base prices at index origin")
    
    @validator('weights')
    def weights_must_sum_to_one(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f'Weights must sum to 1.0, got {total}')
        return v


class IndexRequest(BaseModel):
    """Request to compute index."""
    
    index_name: str = Field(..., description="Index to compute")
    prices: Dict[str, float] = Field(..., description="Current asset prices")
    method: str = Field("level_normalized", description="Calculation method")
    prev_prices: Optional[Dict[str, float]] = Field(None, description="Previous prices for return-based method")
    prev_index_level: Optional[float] = Field(None, description="Previous index level for return-based method")


class IndexResponse(BaseModel):
    """Index calculation response."""
    
    index_name: str
    index_value: float
    timestamp: datetime
    method: str
    delta_24h_pct: Optional[float] = None
    summary: Optional[str] = None
    notable_events: List[str] = Field(default_factory=list)
    sentiment: Dict[str, str] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LLMInsightRequest(BaseModel):
    """Request for LLM insights."""
    
    index_name: str
    index_value: float
    delta_24h_pct: float
    prices: Dict[str, float]
    sources: Dict[str, str]
    weights: Dict[str, float]
    base_prices: Dict[str, float]
    base_level: float
    base_date: str


class LLMInsightResponse(BaseModel):
    """LLM insight response with structured JSON."""
    
    index: float = Field(..., description="Index value")
    index_delta_24h_pct: float = Field(..., description="24-hour percentage change")
    summary: str = Field(..., max_length=200, description="Brief summary (max 2 sentences)")
    notable_events: List[str] = Field(default_factory=list, description="Notable market events")
    sentiment: Dict[str, str] = Field(..., description="Sentiment for each asset")
    
    @validator('sentiment')
    def sentiment_must_be_valid(cls, v):
        valid_sentiments = {'positive', 'negative', 'neutral'}
        for asset, sentiment in v.items():
            if sentiment not in valid_sentiments:
                raise ValueError(f'Invalid sentiment for {asset}: {sentiment}')
        return v


class DataSourceStatus(BaseModel):
    """Data source health status."""
    
    source: str
    last_update: Optional[datetime]
    status: str = Field(..., description="Status: healthy, degraded, error")
    error_message: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)


class HealthCheck(BaseModel):
    """System health check response."""
    
    status: str = Field(..., description="Overall system status")
    timestamp: datetime
    services: Dict[str, DataSourceStatus]
    database_connected: bool
    kafka_connected: bool
    redis_connected: bool


class MetricsData(BaseModel):
    """Prometheus metrics data."""
    
    ingestion_latency_ms: float
    computation_time_ms: float
    llm_latency_ms: float
    source_error_rate: float
    index_calculations_total: int
    data_points_processed: int


# Example normalized schema as mentioned in the roadmap
EXAMPLE_NORMALIZED_SCHEMA = {
    "symbol": "GOLD",
    "price": 1900.12,
    "unit": "USD/oz",
    "timestamp": "2025-09-30T07:40:00Z",
    "source": "AlphaVantage",
    "source_id": "quote_12345",
    "confidence": 0.98
}

# Example LLM response schema
EXAMPLE_LLM_RESPONSE = {
    "index": 1234.56,
    "index_delta_24h_pct": 0.98,
    "summary": "Gold and silver were steady while oil dipped 2% on supply concerns. Bitcoin rose 3% amid positive on-chain flows.",
    "notable_events": ["Oil inventory report 2025-09-29: +1.2M barrels"],
    "sentiment": {"BTC": "positive", "ETH": "neutral"}
}
