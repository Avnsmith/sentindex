"""
Index calculation consumer for Sentindex.

Consumes price data from Kafka, calculates indices, and stores results
in TimescaleDB. Runs as a background service.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from aiokafka import AIOKafkaConsumer
import redis.asyncio as redis

from ..core.index_calculator import IndexCalculator, IndexConfig
from ..models.data_models import PriceData, IndexValue
from ..services.database import DatabaseService
from ..services.grid_llm import SentientLLMService
from ..utils.config import get_config
from ..utils.metrics import get_metrics
from ..utils.logging import get_logger

logger = get_logger(__name__)


class IndexConsumer:
    """Consumer for processing price data and calculating indices."""
    
    def __init__(self):
        self.config = get_config()
        self.metrics = get_metrics()
        self.logger = get_logger(__name__)
        
        # Services
        self.db_service: Optional[DatabaseService] = None
        self.sentient_service: Optional[SentientLLMService] = None
        self.redis_client: Optional[redis.Redis] = None
        self.kafka_consumer: Optional[AIOKafkaConsumer] = None
        
        # Price data cache
        self.price_cache: Dict[str, PriceData] = {}
        
        # Index configurations
        self.index_configs: Dict[str, Dict[str, Any]] = {}
    
    async def start(self):
        """Start the index consumer."""
        try:
            # Initialize services
            await self._init_services()
            
            # Load index configurations
            await self._load_index_configs()
            
            # Start Kafka consumer
            await self._start_kafka_consumer()
            
            self.logger.info("Index consumer started successfully")
            
        except Exception as e:
            self.logger.error("Failed to start index consumer", error=str(e))
            raise
    
    async def stop(self):
        """Stop the index consumer."""
        try:
            if self.kafka_consumer:
                await self.kafka_consumer.stop()
            
            if self.redis_client:
                await self.redis_client.close()
            
            if self.db_service:
                await self.db_service.disconnect()
            
            self.logger.info("Index consumer stopped")
            
        except Exception as e:
            self.logger.error("Error stopping index consumer", error=str(e))
    
    async def _init_services(self):
        """Initialize all required services."""
        # Database service
        self.db_service = DatabaseService(self.config)
        await self.db_service.connect()
        
        # Sentient LLM service
        self.sentient_service = SentientLLMService(self.config)
        
        # Redis client
        redis_config = self.config.get_redis_config()
        self.redis_client = redis.Redis(
            host=redis_config["host"],
            port=redis_config["port"],
            db=redis_config["db"],
            password=redis_config.get("password")
        )
    
    async def _load_index_configs(self):
        """Load index configurations from database."""
        try:
            # Load default configuration
            default_config = IndexConfig.get_gold_silver_oil_crypto_config()
            self.index_configs["gold_silver_oil_crypto"] = default_config
            
            # Store in database if not exists
            await self.db_service.store_index_config("gold_silver_oil_crypto", default_config)
            
            self.logger.info("Loaded index configurations", count=len(self.index_configs))
            
        except Exception as e:
            self.logger.error("Error loading index configurations", error=str(e))
            raise
    
    async def _start_kafka_consumer(self):
        """Start Kafka consumer for price data."""
        kafka_config = self.config.get_kafka_config()
        
        self.kafka_consumer = AIOKafkaConsumer(
            f"{kafka_config['topic_prefix']}.prices",
            bootstrap_servers=kafka_config["bootstrap_servers"],
            group_id=kafka_config["consumer_group"],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            enable_auto_commit=True
        )
        
        await self.kafka_consumer.start()
        
        # Start consuming messages
        asyncio.create_task(self._consume_messages())
    
    async def _consume_messages(self):
        """Consume messages from Kafka."""
        try:
            async for message in self.kafka_consumer:
                try:
                    # Parse price data
                    price_data = PriceData(**message.value)
                    
                    # Update price cache
                    await self._update_price_cache(price_data)
                    
                    # Calculate indices
                    await self._calculate_indices()
                    
                except Exception as e:
                    self.logger.error("Error processing message", error=str(e))
                    self.metrics.increment_source_errors("kafka", "message_processing_error")
        
        except Exception as e:
            self.logger.error("Error in message consumption", error=str(e))
            raise
    
    async def _update_price_cache(self, price_data: PriceData):
        """Update price cache with new data."""
        cache_key = f"{price_data.symbol}:{price_data.source}"
        self.price_cache[cache_key] = price_data
        
        # Update Redis cache
        if self.redis_client:
            await self.redis_client.setex(
                f"price:{cache_key}",
                300,  # 5 minutes TTL
                json.dumps(price_data.dict(), default=str)
            )
        
        self.logger.debug("Updated price cache", symbol=price_data.symbol, source=price_data.source)
    
    async def _calculate_indices(self):
        """Calculate all configured indices."""
        for index_name, config in self.index_configs.items():
            try:
                # Get latest prices for this index
                prices = await self._get_latest_prices_for_index(config)
                
                if not prices:
                    self.logger.warning("No prices available for index", index_name=index_name)
                    continue
                
                # Create calculator
                calculator = IndexConfig.create_calculator(config)
                
                # Validate prices
                is_valid, error = calculator.validate_prices(prices)
                if not is_valid:
                    self.logger.warning("Invalid prices for index", index_name=index_name, error=error)
                    continue
                
                # Calculate index
                with self.metrics.timer("index_calculation", {"index_name": index_name, "method": "level_normalized"}):
                    index_value = calculator.compute_level_normalized(prices)
                
                # Get 24h delta
                delta_24h = await self.db_service.get_index_delta_24h(index_name)
                
                # Store index value
                index_data = {
                    "timestamp": datetime.utcnow(),
                    "index_name": index_name,
                    "index_value": index_value,
                    "method": "level_normalized",
                    "delta_24h_pct": delta_24h,
                    "payload": {
                        "prices": prices,
                        "weights": config["weights"],
                        "base_prices": config["base_prices"]
                    }
                }
                
                await self.db_service.store_index_value(index_data)
                
                # Update metrics
                self.metrics.increment_index_calculations(index_name, "level_normalized")
                self.metrics.set_index_value(index_name, index_value)
                if delta_24h is not None:
                    self.metrics.set_index_delta_24h(index_name, delta_24h)
                
                self.logger.info(
                    "Index calculated",
                    index_name=index_name,
                    index_value=index_value,
                    delta_24h_pct=delta_24h
                )
                
                # Generate insights in background
                asyncio.create_task(self._generate_insights(index_name, index_value, delta_24h, prices, config))
                
            except Exception as e:
                self.logger.error("Error calculating index", index_name=index_name, error=str(e))
                self.metrics.increment_source_errors("index_calculation", "calculation_error")
    
    async def _get_latest_prices_for_index(self, config: Dict[str, Any]) -> Dict[str, float]:
        """Get latest prices for an index configuration."""
        prices = {}
        weights = config["weights"]
        
        for symbol in weights.keys():
            # Find latest price for this symbol
            latest_price = None
            latest_timestamp = None
            
            for cache_key, price_data in self.price_cache.items():
                if price_data.symbol == symbol:
                    if latest_timestamp is None or price_data.timestamp > latest_timestamp:
                        latest_price = price_data
                        latest_timestamp = price_data.timestamp
            
            if latest_price:
                prices[symbol] = latest_price.price
            else:
                self.logger.warning("No price data found", symbol=symbol)
        
        return prices
    
    async def _generate_insights(self, index_name: str, index_value: float, 
                               delta_24h: Optional[float], prices: Dict[str, float], 
                               config: Dict[str, Any]):
        """Generate LLM insights for an index."""
        try:
            if not self.sentient_service:
                return
            
            # Create insight request
            from ..models.data_models import LLMInsightRequest
            
            # Get source information from cache
            sources = {}
            for symbol in prices.keys():
                for cache_key, price_data in self.price_cache.items():
                    if price_data.symbol == symbol:
                        sources[symbol] = price_data.source
                        break
            
            insight_request = LLMInsightRequest(
                index_name=index_name,
                index_value=index_value,
                delta_24h_pct=delta_24h or 0.0,
                prices=prices,
                sources=sources,
                weights=config["weights"],
                base_prices=config["base_prices"],
                base_level=config["base_level"],
                base_date=config["base_date"]
            )
            
            # Generate insights
            insights = await self.sentient_service.generate_insights(insight_request)
            
            # Store insights
            await self.db_service.store_insights(index_name, insights)
            
            self.logger.info("Generated insights", index_name=index_name)
            
        except Exception as e:
            self.logger.error("Error generating insights", index_name=index_name, error=str(e))
    
    async def run_forever(self):
        """Run the consumer forever."""
        try:
            await self.start()
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        except Exception as e:
            self.logger.error("Fatal error in consumer", error=str(e))
            raise
        finally:
            await self.stop()


# Example usage
if __name__ == "__main__":
    async def main():
        consumer = IndexConsumer()
        await consumer.run_forever()
    
    asyncio.run(main())
