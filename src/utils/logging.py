"""
Structured logging configuration for Sentindex.

Provides consistent logging across all services with proper formatting,
correlation IDs, and integration with monitoring systems.
"""

import logging
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional
import structlog
from pythonjsonlogger import jsonlogger


class SentindexFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for Sentindex logs."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        """Add custom fields to log records."""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add service name
        log_record['service'] = 'sentindex'
        
        # Add correlation ID if available
        if hasattr(record, 'correlation_id'):
            log_record['correlation_id'] = record.correlation_id
        
        # Add request ID if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        
        # Add user ID if available
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id


def setup_logging(log_level: str = "INFO", service_name: str = "sentindex"):
    """
    Setup structured logging for Sentindex.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service_name: Name of the service for log identification
    """
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = SentindexFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler for errors
    error_handler = logging.FileHandler('logs/error.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Create file handler for all logs
    all_handler = logging.FileHandler('logs/sentindex.log')
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(formatter)
    root_logger.addHandler(all_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("aiokafka").setLevel(logging.WARNING)
    
    return structlog.get_logger(service_name)


class LogContext:
    """Context manager for adding structured logging context."""
    
    def __init__(self, logger, **context):
        self.logger = logger
        self.context = context
        self.bound_logger = None
    
    def __enter__(self):
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.bound_logger.error(
                "Exception in context",
                exc_type=exc_type.__name__,
                exc_value=str(exc_val)
            )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Logging decorators
def log_function_call(logger: structlog.BoundLogger):
    """Decorator to log function calls with parameters and results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.info(
                "Function called",
                function=func.__name__,
                args=args,
                kwargs=kwargs
            )
            
            try:
                result = func(*args, **kwargs)
                logger.info(
                    "Function completed",
                    function=func.__name__,
                    result=result
                )
                return result
            except Exception as e:
                logger.error(
                    "Function failed",
                    function=func.__name__,
                    error=str(e),
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


def log_async_function_call(logger: structlog.BoundLogger):
    """Decorator to log async function calls with parameters and results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            logger.info(
                "Async function called",
                function=func.__name__,
                args=args,
                kwargs=kwargs
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.info(
                    "Async function completed",
                    function=func.__name__,
                    result=result
                )
                return result
            except Exception as e:
                logger.error(
                    "Async function failed",
                    function=func.__name__,
                    error=str(e),
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


# Performance logging
class PerformanceLogger:
    """Logger for performance metrics."""
    
    def __init__(self, logger: structlog.BoundLogger):
        self.logger = logger
    
    def log_database_query(self, query: str, duration: float, rows: int = None):
        """Log database query performance."""
        self.logger.info(
            "Database query executed",
            query=query,
            duration_ms=duration * 1000,
            rows=rows
        )
    
    def log_api_request(self, method: str, path: str, status_code: int, duration: float):
        """Log API request performance."""
        self.logger.info(
            "API request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration * 1000
        )
    
    def log_llm_request(self, model: str, tokens: int, duration: float):
        """Log LLM request performance."""
        self.logger.info(
            "LLM request",
            model=model,
            tokens=tokens,
            duration_ms=duration * 1000
        )
    
    def log_data_ingestion(self, source: str, records: int, duration: float):
        """Log data ingestion performance."""
        self.logger.info(
            "Data ingestion",
            source=source,
            records=records,
            duration_ms=duration * 1000
        )


# Example usage
if __name__ == "__main__":
    # Setup logging
    logger = setup_logging("DEBUG")
    
    # Basic logging
    logger.info("Application started", version="1.0.0")
    
    # Context logging
    with LogContext(logger, user_id="123", request_id="req-456") as ctx_logger:
        ctx_logger.info("Processing request")
        ctx_logger.warning("Rate limit approaching")
    
    # Performance logging
    perf_logger = PerformanceLogger(logger)
    perf_logger.log_api_request("GET", "/v1/index/test/latest", 200, 0.05)
    perf_logger.log_database_query("SELECT * FROM index_values", 0.02, 100)
    
    # Function logging
    @log_function_call(logger)
    def example_function(x: int, y: int) -> int:
        return x + y
    
    result = example_function(1, 2)
    print(f"Result: {result}")
