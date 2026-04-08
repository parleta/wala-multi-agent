"""
AZTM Observability - Metrics Collection
Provides Prometheus metrics for monitoring AZTM performance
"""
from prometheus_client import Counter, Histogram, Gauge, Summary
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager

# Define metrics
request_counter = Counter(
    'aztm_requests_total',
    'Total AZTM requests',
    ['method', 'status', 'transport']
)

request_duration = Histogram(
    'aztm_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'transport'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

active_connections = Gauge(
    'aztm_active_connections',
    'Number of active messaging connections'
)

payload_size = Histogram(
    'aztm_payload_bytes',
    'Payload size in bytes',
    ['direction', 'transfer_mode'],
    buckets=[1024, 10240, 102400, 1048576, 5242880, 10485760, 52428800]
)

message_queue_size = Gauge(
    'aztm_message_queue_size',
    'Number of messages waiting to be processed',
    ['queue_type']
)

connection_failures = Counter(
    'aztm_connection_failures_total',
    'Total connection failures',
    ['reason']
)

retry_counter = Counter(
    'aztm_retries_total',
    'Total number of retry attempts',
    ['operation', 'result']
)

latency_summary = Summary(
    'aztm_latency_summary',
    'Summary of request latencies',
    ['endpoint']
)


class MetricsCollector:
    """Collector for AZTM metrics"""
    
    def __init__(self):
        self._start_times: Dict[str, float] = {}
        
    @contextmanager
    def measure_request(self, method: str, path: str):
        """Context manager to measure request duration"""
        request_id = f"{method}:{path}:{time.time()}"
        start_time = time.time()
        self._start_times[request_id] = start_time
        
        try:
            yield request_id
        finally:
            duration = time.time() - start_time
            request_duration.labels(method=method, transport='aztm').observe(duration)
            latency_summary.labels(endpoint=path).observe(duration)
            if request_id in self._start_times:
                del self._start_times[request_id]
    
    def record_request(self, method: str, status: int, duration: float, transport: str = 'aztm'):
        """Record a completed request"""
        request_counter.labels(method=method, status=status, transport=transport).inc()
        request_duration.labels(method=method, transport=transport).observe(duration)
    
    def record_payload(self, direction: str, mode: str, size: int):
        """Record payload size metrics"""
        payload_size.labels(direction=direction, transfer_mode=mode).observe(size)
    
    def increment_active_connections(self):
        """Increment active connection count"""
        active_connections.inc()
    
    def decrement_active_connections(self):
        """Decrement active connection count"""
        active_connections.dec()
    
    def set_queue_size(self, queue_type: str, size: int):
        """Set current queue size"""
        message_queue_size.labels(queue_type=queue_type).set(size)
    
    def record_connection_failure(self, reason: str):
        """Record a connection failure"""
        connection_failures.labels(reason=reason).inc()
    
    def record_retry(self, operation: str, success: bool):
        """Record a retry attempt"""
        result = 'success' if success else 'failure'
        retry_counter.labels(operation=operation, result=result).inc()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics"""
        # This is useful for debugging without Prometheus
        return {
            'active_connections': active_connections._value.get(),
            'total_requests': sum(
                request_counter._metrics.values()
            ) if hasattr(request_counter, '_metrics') else 0,
            'pending_requests': len(self._start_times)
        }


# Global metrics collector instance
_collector = None

def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector"""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector