"""
Metrics collection for Sentindex.

Provides Prometheus metrics for monitoring system performance,
data quality, and operational health.
"""

import time
from typing import Dict, Any, Optional
from contextlib import contextmanager
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Prometheus metrics collector for Sentindex."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.
        
        Args:
            registry: Prometheus registry (uses default if None)
        """
        self.registry = registry or CollectorRegistry()
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize all metrics."""
        
        # Index calculation metrics
        self.index_calculations_total = Counter(
            'sentindex_index_calculations_total',
            'Total number of index calculations',
            ['index_name', 'method'],
            registry=self.registry
        )
        
        self.index_calculation_duration = Histogram(
            'sentindex_index_calculation_duration_seconds',
            'Time spent calculating indices',
            ['index_name', 'method'],
            registry=self.registry
        )
        
        # Data ingestion metrics
        self.data_points_processed = Counter(
            'sentindex_data_points_processed_total',
            'Total number of data points processed',
            ['source', 'symbol'],
            registry=self.registry
        )
        
        self.ingestion_latency = Histogram(
            'sentindex_ingestion_latency_seconds',
            'Data ingestion latency',
            ['source'],
            registry=self.registry
        )
        
        self.source_error_rate = Counter(
            'sentindex_source_errors_total',
            'Total number of source errors',
            ['source', 'error_type'],
            registry=self.registry
        )
        
        # LLM metrics
        self.llm_requests_total = Counter(
            'sentindex_llm_requests_total',
            'Total number of LLM requests',
            ['model', 'status'],
            registry=self.registry
        )
        
        self.llm_latency = Histogram(
            'sentindex_llm_latency_seconds',
            'LLM request latency',
            ['model'],
            registry=self.registry
        )
        
        self.llm_tokens_used = Counter(
            'sentindex_llm_tokens_total',
            'Total LLM tokens used',
            ['model', 'type'],
            registry=self.registry
        )
        
        # System health metrics
        self.active_connections = Gauge(
            'sentindex_active_connections',
            'Number of active database connections',
            registry=self.registry
        )
        
        self.queue_size = Gauge(
            'sentindex_queue_size',
            'Message queue size',
            ['queue_name'],
            registry=self.registry
        )
        
        self.cache_hit_rate = Gauge(
            'sentindex_cache_hit_rate',
            'Cache hit rate',
            ['cache_name'],
            registry=self.registry
        )
        
        # Data quality metrics
        self.data_quality_score = Gauge(
            'sentindex_data_quality_score',
            'Data quality score (0-1)',
            ['source', 'symbol'],
            registry=self.registry
        )
        
        self.stale_data_points = Gauge(
            'sentindex_stale_data_points',
            'Number of stale data points',
            ['source'],
            registry=self.registry
        )
        
        # Business metrics
        self.index_value = Gauge(
            'sentindex_index_value',
            'Current index value',
            ['index_name'],
            registry=self.registry
        )
        
        self.index_delta_24h = Gauge(
            'sentindex_index_delta_24h_percent',
            '24-hour index change percentage',
            ['index_name'],
            registry=self.registry
        )
    
    @contextmanager
    def timer(self, operation: str, labels: Optional[Dict[str, str]] = None):
        """
        Context manager for timing operations.
        
        Args:
            operation: Operation name
            labels: Additional labels for the metric
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            
            # Update appropriate histogram based on operation
            if operation.startswith("index_calculation"):
                index_name = labels.get("index_name", "unknown") if labels else "unknown"
                method = labels.get("method", "unknown") if labels else "unknown"
                self.index_calculation_duration.labels(
                    index_name=index_name, method=method
                ).observe(duration)
            elif operation.startswith("ingestion"):
                source = labels.get("source", "unknown") if labels else "unknown"
                self.ingestion_latency.labels(source=source).observe(duration)
            elif operation.startswith("llm"):
                model = labels.get("model", "unknown") if labels else "unknown"
                self.llm_latency.labels(model=model).observe(duration)
    
    def increment_index_calculations(self, index_name: str, method: str):
        """Increment index calculation counter."""
        self.index_calculations_total.labels(
            index_name=index_name, method=method
        ).inc()
    
    def increment_data_points(self, source: str, symbol: str):
        """Increment data points processed counter."""
        self.data_points_processed.labels(source=source, symbol=symbol).inc()
    
    def increment_source_errors(self, source: str, error_type: str):
        """Increment source error counter."""
        self.source_error_rate.labels(source=source, error_type=error_type).inc()
    
    def increment_llm_requests(self, model: str, status: str):
        """Increment LLM request counter."""
        self.llm_requests_total.labels(model=model, status=status).inc()
    
    def add_llm_tokens(self, model: str, token_type: str, count: int):
        """Add LLM tokens used."""
        self.llm_tokens_used.labels(model=model, type=token_type).inc(count)
    
    def set_active_connections(self, count: int):
        """Set active database connections count."""
        self.active_connections.set(count)
    
    def set_queue_size(self, queue_name: str, size: int):
        """Set message queue size."""
        self.queue_size.labels(queue_name=queue_name).set(size)
    
    def set_cache_hit_rate(self, cache_name: str, rate: float):
        """Set cache hit rate."""
        self.cache_hit_rate.labels(cache_name=cache_name).set(rate)
    
    def set_data_quality_score(self, source: str, symbol: str, score: float):
        """Set data quality score."""
        self.data_quality_score.labels(source=source, symbol=symbol).set(score)
    
    def set_stale_data_points(self, source: str, count: int):
        """Set stale data points count."""
        self.stale_data_points.labels(source=source).set(count)
    
    def set_index_value(self, index_name: str, value: float):
        """Set current index value."""
        self.index_value.labels(index_name=index_name).set(value)
    
    def set_index_delta_24h(self, index_name: str, delta: float):
        """Set 24-hour index delta."""
        self.index_delta_24h.labels(index_name=index_name).set(delta)
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get metrics as dictionary for JSON responses."""
        # This is a simplified version - in production you might want
        # to parse the Prometheus text format or use a different approach
        return {
            "index_calculations_total": "See /metrics endpoint for detailed metrics",
            "data_points_processed": "See /metrics endpoint for detailed metrics",
            "llm_requests_total": "See /metrics endpoint for detailed metrics",
            "note": "Use /metrics endpoint for full Prometheus metrics"
        }


# Global metrics instance
_metrics_instance: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector()
    return _metrics_instance


# Example usage
if __name__ == "__main__":
    metrics = MetricsCollector()
    
    # Example of using metrics
    with metrics.timer("index_calculation", {"index_name": "test", "method": "level_normalized"}):
        time.sleep(0.1)  # Simulate work
    
    metrics.increment_index_calculations("test", "level_normalized")
    metrics.set_index_value("test", 1234.56)
    metrics.set_index_delta_24h("test", 1.5)
    
    print("Metrics:")
    print(metrics.get_metrics())
