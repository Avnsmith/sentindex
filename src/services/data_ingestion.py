"""
Data ingestion microservices for Sentindex.

Each microservice handles data from a specific source, normalizes it,
and emits to the message bus for processing.
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import redis.asyncio as redis
from aiokafka import AIOKafkaProducer

from ..models.data_models import PriceData
from ..utils.config import get_config
from ..utils.metrics import get_metrics

logger = logging.getLogger(__name__)


@dataclass
class DataSourceConfig:
    """Configuration for a data source."""
    name: str
    base_url: str
    api_key: Optional[str] = None
    rate_limit: int = 60  # requests per minute
    symbols: List[str] = None
    cache_ttl: int = 300  # seconds


class DataIngestionService:
    """Base class for data ingestion services."""
    
    def __init__(self, config: DataSourceConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.redis_client: Optional[redis.Redis] = None
        self.kafka_producer: Optional[AIOKafkaProducer] = None
        self.metrics = get_metrics()
        self._rate_limiter = asyncio.Semaphore(config.rate_limit)
    
    async def start(self):
        """Start the ingestion service."""
        # Initialize HTTP session
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        # Initialize Redis for caching
        redis_config = get_config().get_redis_config()
        self.redis_client = redis.Redis(
            host=redis_config["host"],
            port=redis_config["port"],
            db=redis_config["db"],
            password=redis_config.get("password")
        )
        
        # Initialize Kafka producer
        kafka_config = get_config().get_kafka_config()
        self.kafka_producer = AIOKafkaProducer(
            bootstrap_servers=kafka_config["bootstrap_servers"],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.kafka_producer.start()
        
        logger.info(f"Started {self.config.name} ingestion service")
    
    async def stop(self):
        """Stop the ingestion service."""
        if self.session:
            await self.session.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.kafka_producer:
            await self.kafka_producer.stop()
        
        logger.info(f"Stopped {self.config.name} ingestion service")
    
    async def fetch_data(self) -> List[PriceData]:
        """Fetch data from the source. Must be implemented by subclasses."""
        raise NotImplementedError
    
    async def normalize_data(self, raw_data: Any) -> List[PriceData]:
        """Normalize raw data to PriceData format. Must be implemented by subclasses."""
        raise NotImplementedError
    
    async def emit_data(self, price_data: List[PriceData]):
        """Emit normalized data to message bus."""
        try:
            topic = f"{get_config().get_kafka_config()['topic_prefix']}.prices"
            
            for data in price_data:
                message = data.dict()
                await self.kafka_producer.send_and_wait(topic, message)
                
                # Update metrics
                self.metrics.increment_data_points(self.config.name, data.symbol)
                
            logger.debug(f"Emitted {len(price_data)} data points from {self.config.name}")
            
        except Exception as e:
            logger.error(f"Error emitting data from {self.config.name}: {e}")
            self.metrics.increment_source_errors(self.config.name, "emit_error")
    
    async def get_cached_data(self, key: str) -> Optional[Any]:
        """Get cached data from Redis."""
        try:
            if self.redis_client:
                cached = await self.redis_client.get(key)
                if cached:
                    return json.loads(cached)
        except Exception as e:
            logger.warning(f"Error getting cached data: {e}")
        return None
    
    async def set_cached_data(self, key: str, data: Any, ttl: int = None):
        """Set cached data in Redis."""
        try:
            if self.redis_client:
                ttl = ttl or self.config.cache_ttl
                await self.redis_client.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logger.warning(f"Error setting cached data: {e}")
    
    async def run_ingestion_loop(self):
        """Run the main ingestion loop."""
        logger.info(f"Starting ingestion loop for {self.config.name}")
        
        while True:
            try:
                async with self._rate_limiter:
                    with self.metrics.timer("ingestion", {"source": self.config.name}):
                        # Fetch and process data
                        raw_data = await self.fetch_data()
                        normalized_data = await self.normalize_data(raw_data)
                        
                        # Emit to message bus
                        if normalized_data:
                            await self.emit_data(normalized_data)
                
                # Wait before next iteration
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error(f"Error in ingestion loop for {self.config.name}: {e}")
                self.metrics.increment_source_errors(self.config.name, "ingestion_error")
                await asyncio.sleep(30)  # Wait before retry


class AlphaVantageService(DataIngestionService):
    """AlphaVantage data ingestion service."""
    
    def __init__(self):
        config = DataSourceConfig(
            name="alphavantage",
            base_url="https://www.alphavantage.co/query",
            api_key=get_config().get("data_sources.alphavantage.api_key"),
            rate_limit=5,  # AlphaVantage free tier limit
            symbols=["GOLD", "SILVER"],
            cache_ttl=300
        )
        super().__init__(config)
    
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch data from AlphaVantage."""
        if not self.config.api_key:
            logger.warning("AlphaVantage API key not configured")
            return []
        
        data = []
        
        for symbol in self.config.symbols:
            try:
                # Check cache first
                cache_key = f"alphavantage:{symbol}"
                cached = await self.get_cached_data(cache_key)
                if cached:
                    data.append(cached)
                    continue
                
                # Fetch from API
                params = {
                    "function": "CURRENCY_EXCHANGE_RATE",
                    "from_currency": symbol,
                    "to_currency": "USD",
                    "apikey": self.config.api_key
                }
                
                async with self.session.get(self.config.base_url, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # Cache the result
                        await self.set_cached_data(cache_key, result)
                        data.append(result)
                    else:
                        logger.error(f"AlphaVantage API error for {symbol}: {response.status}")
                        self.metrics.increment_source_errors(self.config.name, "api_error")
                
            except Exception as e:
                logger.error(f"Error fetching {symbol} from AlphaVantage: {e}")
                self.metrics.increment_source_errors(self.config.name, "fetch_error")
        
        return data
    
    async def normalize_data(self, raw_data: List[Dict[str, Any]]) -> List[PriceData]:
        """Normalize AlphaVantage data."""
        normalized = []
        
        for data in raw_data:
            try:
                if "Realtime Currency Exchange Rate" in data:
                    rate_data = data["Realtime Currency Exchange Rate"]
                    
                    symbol = rate_data.get("1. From_Currency Code", "").upper()
                    price = float(rate_data.get("5. Exchange Rate", 0))
                    timestamp_str = rate_data.get("6. Last Refreshed", "")
                    
                    if symbol and price > 0:
                        # Parse timestamp
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        
                        price_data = PriceData(
                            symbol=symbol,
                            price=price,
                            unit="USD/oz" if symbol in ["GOLD", "SILVER"] else "USD",
                            timestamp=timestamp,
                            source=self.config.name,
                            confidence=0.95
                        )
                        normalized.append(price_data)
                
            except Exception as e:
                logger.error(f"Error normalizing AlphaVantage data: {e}")
        
        return normalized


class CoinGeckoService(DataIngestionService):
    """CoinGecko data ingestion service."""
    
    def __init__(self):
        config = DataSourceConfig(
            name="coingecko",
            base_url="https://api.coingecko.com/api/v3",
            rate_limit=30,
            symbols=["bitcoin", "ethereum"],
            cache_ttl=60
        )
        super().__init__(config)
    
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch data from CoinGecko."""
        try:
            # Check cache first
            cache_key = "coingecko:btc_eth"
            cached = await self.get_cached_data(cache_key)
            if cached:
                return [cached]
            
            # Fetch from API
            params = {
                "ids": ",".join(self.config.symbols),
                "vs_currencies": "usd",
                "include_last_updated_at": "true"
            }
            
            url = f"{self.config.base_url}/simple/price"
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Cache the result
                    await self.set_cached_data(cache_key, result)
                    return [result]
                else:
                    logger.error(f"CoinGecko API error: {response.status}")
                    self.metrics.increment_source_errors(self.config.name, "api_error")
                    return []
        
        except Exception as e:
            logger.error(f"Error fetching from CoinGecko: {e}")
            self.metrics.increment_source_errors(self.config.name, "fetch_error")
            return []
    
    async def normalize_data(self, raw_data: List[Dict[str, Any]]) -> List[PriceData]:
        """Normalize CoinGecko data."""
        normalized = []
        
        for data in raw_data:
            try:
                for coin_id, coin_data in data.items():
                    if "usd" in coin_data:
                        symbol = coin_id.upper()
                        if symbol == "BITCOIN":
                            symbol = "BTC"
                        elif symbol == "ETHEREUM":
                            symbol = "ETH"
                        
                        price = float(coin_data["usd"])
                        timestamp = datetime.fromtimestamp(coin_data.get("last_updated_at", 0))
                        
                        price_data = PriceData(
                            symbol=symbol,
                            price=price,
                            unit="USD",
                            timestamp=timestamp,
                            source=self.config.name,
                            confidence=0.98
                        )
                        normalized.append(price_data)
                
            except Exception as e:
                logger.error(f"Error normalizing CoinGecko data: {e}")
        
        return normalized


class EIAService(DataIngestionService):
    """EIA (Energy Information Administration) data ingestion service."""
    
    def __init__(self):
        config = DataSourceConfig(
            name="eia",
            base_url="https://api.eia.gov/v2",
            api_key=get_config().get("data_sources.eia.api_key"),
            rate_limit=10,
            symbols=["PET.RWTC.D"],  # WTI Crude Oil
            cache_ttl=3600  # 1 hour cache for oil data
        )
        super().__init__(config)
    
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch data from EIA."""
        if not self.config.api_key:
            logger.warning("EIA API key not configured")
            return []
        
        try:
            # Check cache first
            cache_key = "eia:oil"
            cached = await self.get_cached_data(cache_key)
            if cached:
                return [cached]
            
            # Fetch from API
            params = {
                "api_key": self.config.api_key,
                "frequency": "daily",
                "data[0]": "value",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "offset": 0,
                "length": 1
            }
            
            url = f"{self.config.base_url}/petroleum/pri/spt/data"
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Cache the result
                    await self.set_cached_data(cache_key, result)
                    return [result]
                else:
                    logger.error(f"EIA API error: {response.status}")
                    self.metrics.increment_source_errors(self.config.name, "api_error")
                    return []
        
        except Exception as e:
            logger.error(f"Error fetching from EIA: {e}")
            self.metrics.increment_source_errors(self.config.name, "fetch_error")
            return []
    
    async def normalize_data(self, raw_data: List[Dict[str, Any]]) -> List[PriceData]:
        """Normalize EIA data."""
        normalized = []
        
        for data in raw_data:
            try:
                if "response" in data and "data" in data["response"]:
                    oil_data = data["response"]["data"]
                    if oil_data:
                        latest = oil_data[0]
                        
                        price = float(latest["value"])
                        period = latest["period"]
                        
                        # Parse period (format: YYYY-MM-DD)
                        timestamp = datetime.fromisoformat(period)
                        
                        price_data = PriceData(
                            symbol="OIL",
                            price=price,
                            unit="USD/bbl",
                            timestamp=timestamp,
                            source=self.config.name,
                            confidence=0.99
                        )
                        normalized.append(price_data)
                
            except Exception as e:
                logger.error(f"Error normalizing EIA data: {e}")
        
        return normalized


# Service factory
def create_ingestion_service(source_name: str) -> DataIngestionService:
    """Create ingestion service by name."""
    services = {
        "alphavantage": AlphaVantageService,
        "coingecko": CoinGeckoService,
        "eia": EIAService
    }
    
    service_class = services.get(source_name)
    if not service_class:
        raise ValueError(f"Unknown data source: {source_name}")
    
    return service_class()


# Example usage
if __name__ == "__main__":
    async def main():
        # Create and run services
        services = [
            create_ingestion_service("alphavantage"),
            create_ingestion_service("coingecko"),
            create_ingestion_service("eia")
        ]
        
        # Start all services
        for service in services:
            await service.start()
        
        try:
            # Run ingestion loops concurrently
            tasks = [service.run_ingestion_loop() for service in services]
            await asyncio.gather(*tasks)
        finally:
            # Stop all services
            for service in services:
                await service.stop()
    
    asyncio.run(main())
