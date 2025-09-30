"""
FastAPI main application for Sentindex.

Provides REST API endpoints for index calculations, historical data,
and system health monitoring.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..core.index_calculator import IndexCalculator, IndexConfig
from ..models.data_models import (
    IndexRequest, IndexResponse, HealthCheck, DataSourceStatus,
    LLMInsightRequest, LLMInsightResponse
)
from ..services.database import DatabaseService
from ..services.grid_llm import SentientLLMService
from ..utils.config import get_config
from ..utils.metrics import MetricsCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global services
db_service: Optional[DatabaseService] = None
sentient_service: Optional[SentientLLMService] = None
metrics: Optional[MetricsCollector] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_service, grid_service, metrics
    
    # Startup
    logger.info("Starting Sentindex API...")
    
    config = get_config()
    
    # Initialize services
    db_service = DatabaseService(config)
    await db_service.connect()
    
    sentient_service = SentientLLMService(config)
    
    metrics = MetricsCollector()
    
    logger.info("Sentindex API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Sentindex API...")
    if db_service:
        await db_service.disconnect()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Sentindex API",
    description="Financial index platform with AI-powered insights",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency injection
async def get_db_service() -> DatabaseService:
    if not db_service:
        raise HTTPException(status_code=503, detail="Database service not available")
    return db_service


async def get_sentient_service() -> SentientLLMService:
    if not sentient_service:
        raise HTTPException(status_code=503, detail="Sentient LLM service not available")
    return sentient_service


async def get_metrics() -> MetricsCollector:
    if not metrics:
        raise HTTPException(status_code=503, detail="Metrics service not available")
    return metrics


# Health check endpoint
@app.get("/health", response_model=HealthCheck)
async def health_check(
    db: DatabaseService = Depends(get_db_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """System health check."""
    try:
        # Check database connection
        db_connected = await db.is_connected()
        
        # Check other services (simplified for now)
        kafka_connected = True  # TODO: Implement actual Kafka health check
        redis_connected = True  # TODO: Implement actual Redis health check
        
        # Get data source statuses
        services = {
            "database": DataSourceStatus(
                source="postgresql",
                last_update=datetime.utcnow(),
                status="healthy" if db_connected else "error",
                confidence=1.0 if db_connected else 0.0
            ),
            "kafka": DataSourceStatus(
                source="kafka",
                last_update=datetime.utcnow(),
                status="healthy" if kafka_connected else "error",
                confidence=1.0 if kafka_connected else 0.0
            ),
            "redis": DataSourceStatus(
                source="redis",
                last_update=datetime.utcnow(),
                status="healthy" if redis_connected else "error",
                confidence=1.0 if redis_connected else 0.0
            )
        }
        
        overall_status = "healthy" if all(
            service.status == "healthy" for service in services.values()
        ) else "degraded"
        
        return HealthCheck(
            status=overall_status,
            timestamp=datetime.utcnow(),
            services=services,
            database_connected=db_connected,
            kafka_connected=kafka_connected,
            redis_connected=redis_connected
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")


# Index endpoints
@app.get("/v1/index/{name}/latest", response_model=IndexResponse)
async def get_latest_index(
    name: str,
    db: DatabaseService = Depends(get_db_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Get latest index value."""
    try:
        with metrics.timer("get_latest_index"):
            # Get latest index value from database
            index_data = await db.get_latest_index(name)
            
            if not index_data:
                raise HTTPException(status_code=404, detail=f"Index {name} not found")
            
            # Get 24h delta
            delta_24h = await db.get_index_delta_24h(name)
            
            return IndexResponse(
                index_name=index_data["index_name"],
                index_value=index_data["index_value"],
                timestamp=index_data["timestamp"],
                method=index_data["method"],
                delta_24h_pct=delta_24h,
                provenance=index_data.get("payload", {})
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest index {name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/v1/index/{name}/history")
async def get_index_history(
    name: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 1000,
    db: DatabaseService = Depends(get_db_service)
):
    """Get historical index data."""
    try:
        # Parse date parameters
        start_date = None
        end_date = None
        
        if start:
            start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
        if end:
            end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        # Get historical data
        history = await db.get_index_history(
            name, start_date, end_date, limit
        )
        
        return {
            "index_name": name,
            "data": history,
            "count": len(history)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"Error getting history for {name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/v1/index/{name}/compute", response_model=IndexResponse)
async def compute_index(
    name: str,
    request: IndexRequest,
    background_tasks: BackgroundTasks,
    db: DatabaseService = Depends(get_db_service),
    sentient_service: SentientLLMService = Depends(get_sentient_service),
    metrics: MetricsCollector = Depends(get_metrics)
):
    """Compute index value (admin endpoint)."""
    try:
        with metrics.timer("compute_index"):
            # Get index configuration
            config = await db.get_index_config(name)
            if not config:
                raise HTTPException(status_code=404, detail=f"Index {name} not found")
            
            # Create calculator
            calculator = IndexConfig.create_calculator(config)
            
            # Validate prices
            is_valid, error = calculator.validate_prices(request.prices)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid price data: {error}")
            
            # Compute index
            if request.method == "level_normalized":
                index_value = calculator.compute_level_normalized(request.prices)
            elif request.method == "return_based":
                if not request.prev_prices or request.prev_index_level is None:
                    raise HTTPException(
                        status_code=400, 
                        detail="Previous prices and index level required for return-based method"
                    )
                index_value = calculator.compute_return_index(
                    request.prev_prices, request.prices, request.prev_index_level
                )
            else:
                raise HTTPException(status_code=400, detail="Invalid calculation method")
            
            # Get 24h delta
            delta_24h = await db.get_index_delta_24h(name)
            
            # Store result
            index_data = {
                "index_name": name,
                "index_value": index_value,
                "timestamp": datetime.utcnow(),
                "method": request.method,
                "payload": {
                    "prices": request.prices,
                    "weights": config["weights"],
                    "base_prices": config["base_prices"]
                }
            }
            
            await db.store_index_value(index_data)
            
            # Generate LLM insights in background
            background_tasks.add_task(
                generate_insights, name, index_value, delta_24h, request.prices, config
            )
            
            return IndexResponse(
                index_name=name,
                index_value=index_value,
                timestamp=index_data["timestamp"],
                method=request.method,
                delta_24h_pct=delta_24h,
                provenance=index_data["payload"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing index {name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/v1/index/{name}/insights")
async def get_insights(
    name: str,
    db: DatabaseService = Depends(get_db_service),
    sentient_service: SentientLLMService = Depends(get_sentient_service)
):
    """Get AI insights for index."""
    try:
        # Get latest index data
        index_data = await db.get_latest_index(name)
        if not index_data:
            raise HTTPException(status_code=404, detail=f"Index {name} not found")
        
        # Get insights from database
        insights = await db.get_latest_insights(name)
        
        return {
            "index_name": name,
            "insights": insights,
            "timestamp": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting insights for {name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Metrics endpoint
@app.get("/metrics")
async def get_metrics_endpoint(metrics: MetricsCollector = Depends(get_metrics)):
    """Prometheus metrics endpoint."""
    return metrics.get_metrics()


# Background task for generating insights
async def generate_insights(
    name: str, 
    index_value: float, 
    delta_24h: float, 
    prices: Dict[str, float], 
    config: Dict
):
    """Generate LLM insights in background."""
    try:
        if not sentient_service:
            logger.warning("Sentient service not available for insights")
            return
        
        # Create insight request
        insight_request = LLMInsightRequest(
            index_name=name,
            index_value=index_value,
            delta_24h_pct=delta_24h,
            prices=prices,
            sources={},  # TODO: Get actual source information
            weights=config["weights"],
            base_prices=config["base_prices"],
            base_level=config["base_level"],
            base_date=config["base_date"]
        )
        
        # Generate insights
        insights = await sentient_service.generate_insights(insight_request)
        
        # Store insights
        if db_service:
            await db_service.store_insights(name, insights)
        
        logger.info(f"Generated insights for {name}")
        
    except Exception as e:
        logger.error(f"Error generating insights for {name}: {e}")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Sentindex API",
        "version": "1.0.0",
        "description": "Financial index platform with AI-powered insights",
        "endpoints": {
            "health": "/health",
            "latest_index": "/v1/index/{name}/latest",
            "index_history": "/v1/index/{name}/history",
            "compute_index": "/v1/index/{name}/compute",
            "insights": "/v1/index/{name}/insights",
            "metrics": "/metrics"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
