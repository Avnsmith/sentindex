"""
Database service for Sentindex.

Handles TimescaleDB operations for storing and retrieving
index values, configurations, and insights.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select, insert, update, delete
import json

from ..utils.config import get_config
from ..models.data_models import IndexValue, IndexConfig, LLMInsightResponse

logger = logging.getLogger(__name__)


class DatabaseService:
    """Database service for TimescaleDB operations."""
    
    def __init__(self, config):
        self.config = config
        self.engine = None
        self.session_factory = None
        self.pool = None
    
    async def connect(self):
        """Connect to the database."""
        try:
            db_config = self.config.get_database_config()
            
            # Create async engine
            database_url = (
                f"postgresql+asyncpg://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/{db_config['name']}"
            )
            
            self.engine = create_async_engine(
                database_url,
                pool_size=db_config.get("pool_size", 10),
                max_overflow=db_config.get("max_overflow", 20),
                echo=False
            )
            
            # Create session factory
            self.session_factory = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
            
            # Create connection pool for raw queries
            self.pool = await asyncpg.create_pool(
                host=db_config["host"],
                port=db_config["port"],
                user=db_config["user"],
                password=db_config["password"],
                database=db_config["name"],
                min_size=5,
                max_size=20
            )
            
            # Initialize database schema
            await self._init_schema()
            
            logger.info("Connected to database successfully")
            
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the database."""
        try:
            if self.pool:
                await self.pool.close()
            if self.engine:
                await self.engine.dispose()
            logger.info("Disconnected from database")
        except Exception as e:
            logger.error(f"Error disconnecting from database: {e}")
    
    async def is_connected(self) -> bool:
        """Check if database is connected."""
        try:
            if self.pool:
                async with self.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return True
        except Exception:
            pass
        return False
    
    async def _init_schema(self):
        """Initialize database schema."""
        try:
            async with self.pool.acquire() as conn:
                # Enable TimescaleDB extension
                await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
                
                # Create index_values table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS index_values (
                        time TIMESTAMPTZ NOT NULL,
                        index_name TEXT NOT NULL,
                        index_value NUMERIC NOT NULL,
                        method TEXT NOT NULL,
                        delta_24h_pct NUMERIC,
                        payload JSONB,
                        PRIMARY KEY (time, index_name)
                    )
                """)
                
                # Create hypertable
                await conn.execute("""
                    SELECT create_hypertable('index_values', 'time', 
                                           if_not_exists => TRUE)
                """)
                
                # Create index configurations table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS index_configs (
                        name TEXT PRIMARY KEY,
                        config JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                
                # Create insights table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS insights (
                        id SERIAL PRIMARY KEY,
                        index_name TEXT NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        insights JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                
                # Create data sources table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS data_sources (
                        source TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        last_update TIMESTAMPTZ,
                        status TEXT DEFAULT 'unknown',
                        confidence NUMERIC DEFAULT 0.0,
                        PRIMARY KEY (source, symbol)
                    )
                """)
                
                # Create indexes for better performance
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_index_values_name_time 
                    ON index_values (index_name, time DESC)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_insights_name_time 
                    ON insights (index_name, timestamp DESC)
                """)
                
                logger.info("Database schema initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database schema: {e}")
            raise
    
    async def store_index_value(self, index_data: Dict[str, Any]):
        """Store index value in the database."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO index_values (time, index_name, index_value, method, delta_24h_pct, payload)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (time, index_name) DO UPDATE SET
                        index_value = EXCLUDED.index_value,
                        method = EXCLUDED.method,
                        delta_24h_pct = EXCLUDED.delta_24h_pct,
                        payload = EXCLUDED.payload
                """, 
                index_data["timestamp"],
                index_data["index_name"],
                index_data["index_value"],
                index_data["method"],
                index_data.get("delta_24h_pct"),
                json.dumps(index_data.get("payload", {}))
                )
                
        except Exception as e:
            logger.error(f"Error storing index value: {e}")
            raise
    
    async def get_latest_index(self, index_name: str) -> Optional[Dict[str, Any]]:
        """Get latest index value."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT time, index_name, index_value, method, payload
                    FROM index_values
                    WHERE index_name = $1
                    ORDER BY time DESC
                    LIMIT 1
                """, index_name)
                
                if row:
                    return {
                        "timestamp": row["time"],
                        "index_name": row["index_name"],
                        "index_value": float(row["index_value"]),
                        "method": row["method"],
                        "payload": json.loads(row["payload"]) if row["payload"] else {}
                    }
                
        except Exception as e:
            logger.error(f"Error getting latest index: {e}")
            raise
        
        return None
    
    async def get_index_history(self, index_name: str, start_date: Optional[datetime] = None,
                              end_date: Optional[datetime] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get historical index data."""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT time, index_name, index_value, method, delta_24h_pct, payload
                    FROM index_values
                    WHERE index_name = $1
                """
                params = [index_name]
                param_count = 1
                
                if start_date:
                    param_count += 1
                    query += f" AND time >= ${param_count}"
                    params.append(start_date)
                
                if end_date:
                    param_count += 1
                    query += f" AND time <= ${param_count}"
                    params.append(end_date)
                
                query += f" ORDER BY time DESC LIMIT ${param_count + 1}"
                params.append(limit)
                
                rows = await conn.fetch(query, *params)
                
                return [
                    {
                        "timestamp": row["time"].isoformat(),
                        "index_name": row["index_name"],
                        "index_value": float(row["index_value"]),
                        "method": row["method"],
                        "delta_24h_pct": float(row["delta_24h_pct"]) if row["delta_24h_pct"] else None,
                        "payload": json.loads(row["payload"]) if row["payload"] else {}
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Error getting index history: {e}")
            raise
    
    async def get_index_delta_24h(self, index_name: str) -> Optional[float]:
        """Get 24-hour index delta percentage."""
        try:
            async with self.pool.acquire() as conn:
                # Get current and 24h ago values
                current = await conn.fetchrow("""
                    SELECT index_value FROM index_values
                    WHERE index_name = $1
                    ORDER BY time DESC LIMIT 1
                """, index_name)
                
                if not current:
                    return None
                
                past_24h = await conn.fetchrow("""
                    SELECT index_value FROM index_values
                    WHERE index_name = $1 AND time <= NOW() - INTERVAL '24 hours'
                    ORDER BY time DESC LIMIT 1
                """, index_name)
                
                if not past_24h:
                    return None
                
                current_value = float(current["index_value"])
                past_value = float(past_24h["index_value"])
                
                if past_value <= 0:
                    return None
                
                delta_pct = ((current_value - past_value) / past_value) * 100
                return round(delta_pct, 2)
                
        except Exception as e:
            logger.error(f"Error getting 24h delta: {e}")
            return None
    
    async def store_index_config(self, name: str, config: Dict[str, Any]):
        """Store index configuration."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO index_configs (name, config, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (name) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = NOW()
                """, name, json.dumps(config))
                
        except Exception as e:
            logger.error(f"Error storing index config: {e}")
            raise
    
    async def get_index_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get index configuration."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT config FROM index_configs WHERE name = $1
                """, name)
                
                if row:
                    return json.loads(row["config"])
                
        except Exception as e:
            logger.error(f"Error getting index config: {e}")
            raise
        
        return None
    
    async def store_insights(self, index_name: str, insights: LLMInsightResponse):
        """Store LLM insights."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO insights (index_name, timestamp, insights)
                    VALUES ($1, NOW(), $2)
                """, index_name, json.dumps(insights.dict()))
                
        except Exception as e:
            logger.error(f"Error storing insights: {e}")
            raise
    
    async def get_latest_insights(self, index_name: str) -> Optional[Dict[str, Any]]:
        """Get latest insights for an index."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT insights, timestamp FROM insights
                    WHERE index_name = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, index_name)
                
                if row:
                    return {
                        "insights": json.loads(row["insights"]),
                        "timestamp": row["timestamp"].isoformat()
                    }
                
        except Exception as e:
            logger.error(f"Error getting latest insights: {e}")
            raise
        
        return None
    
    async def update_data_source_status(self, source: str, symbol: str, 
                                      status: str, confidence: float, 
                                      last_update: Optional[datetime] = None):
        """Update data source status."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO data_sources (source, symbol, last_update, status, confidence)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (source, symbol) DO UPDATE SET
                        last_update = EXCLUDED.last_update,
                        status = EXCLUDED.status,
                        confidence = EXCLUDED.confidence
                """, source, symbol, last_update or datetime.utcnow(), status, confidence)
                
        except Exception as e:
            logger.error(f"Error updating data source status: {e}")
            raise
    
    async def get_data_source_status(self, source: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get data source status."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT last_update, status, confidence
                    FROM data_sources
                    WHERE source = $1 AND symbol = $2
                """, source, symbol)
                
                if row:
                    return {
                        "last_update": row["last_update"],
                        "status": row["status"],
                        "confidence": float(row["confidence"])
                    }
                
        except Exception as e:
            logger.error(f"Error getting data source status: {e}")
            raise
        
        return None
    
    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data to manage storage."""
        try:
            async with self.pool.acquire() as conn:
                # Delete old index values
                deleted = await conn.execute("""
                    DELETE FROM index_values
                    WHERE time < NOW() - INTERVAL '%s days'
                """ % days_to_keep)
                
                # Delete old insights
                await conn.execute("""
                    DELETE FROM insights
                    WHERE timestamp < NOW() - INTERVAL '%s days'
                """ % days_to_keep)
                
                logger.info(f"Cleaned up data older than {days_to_keep} days")
                
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            raise


# Example usage
if __name__ == "__main__":
    async def main():
        config = get_config()
        db = DatabaseService(config)
        
        try:
            await db.connect()
            
            # Test storing and retrieving data
            test_data = {
                "timestamp": datetime.utcnow(),
                "index_name": "test_index",
                "index_value": 1234.56,
                "method": "level_normalized",
                "payload": {"test": "data"}
            }
            
            await db.store_index_value(test_data)
            
            latest = await db.get_latest_index("test_index")
            print("Latest index:", latest)
            
        finally:
            await db.disconnect()
    
    asyncio.run(main())
