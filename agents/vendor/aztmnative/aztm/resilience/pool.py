"""
AZTM Resilience - Connection Pooling and Circuit Breaker
Provides connection multiplexing, caching, and resilience patterns
"""
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import deque
import hashlib
import json
from enum import Enum

from ..core.xmpp_client import XMPPClient
from ..observability.metrics import get_metrics_collector


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CacheEntry:
    """Cache entry for response caching"""
    response: Any
    timestamp: float
    ttl: float
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return time.time() - self.timestamp > self.ttl


@dataclass
class CircuitBreaker:
    """Circuit breaker for failing services"""
    service_jid: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_requests: int = 3
    
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    last_failure_time: float = field(default=0.0)
    half_open_count: int = field(default=0)
    
    def record_success(self):
        """Record a successful request"""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_count += 1
            if self.half_open_count >= self.half_open_requests:
                # Enough successful requests, close the circuit
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.half_open_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def record_failure(self):
        """Record a failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
        elif self.state == CircuitState.HALF_OPEN:
            # Failed during recovery, reopen circuit
            self.state = CircuitState.OPEN
            self.half_open_count = 0
    
    def should_attempt(self) -> bool:
        """Check if request should be attempted"""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_count = 0
                return True
            return False
        else:  # HALF_OPEN
            return True


class ConnectionPool:
    """Connection pool for managing multiple AZTM connections"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections: Dict[str, XMPPClient] = {}
        self.connection_usage: Dict[str, float] = {}
        self.lock = asyncio.Lock()
        self.metrics = get_metrics_collector()
        
    async def get_connection(self, jid: str, password: str) -> XMPPClient:
        """Get or create a connection from the pool"""
        async with self.lock:
            if jid in self.connections:
                # Update last used time
                self.connection_usage[jid] = time.time()
                return self.connections[jid]
            
            # Check if we need to evict old connections
            if len(self.connections) >= self.max_connections:
                await self._evict_oldest()
            
            # Create new connection
            client = XMPPClient(jid, password)
            client.connect()
            
            # Wait for connection to establish
            await client.connected.wait()
            
            self.connections[jid] = client
            self.connection_usage[jid] = time.time()
            self.metrics.increment_active_connections()
            
            return client
    
    async def _evict_oldest(self):
        """Evict the least recently used connection"""
        if not self.connections:
            return
            
        # Find LRU connection
        oldest_jid = min(self.connection_usage, key=self.connection_usage.get)
        
        # Disconnect and remove
        client = self.connections[oldest_jid]
        client.disconnect()
        
        del self.connections[oldest_jid]
        del self.connection_usage[oldest_jid]
        self.metrics.decrement_active_connections()
    
    async def close_all(self):
        """Close all connections in the pool"""
        async with self.lock:
            for client in self.connections.values():
                client.disconnect()
                self.metrics.decrement_active_connections()
            
            self.connections.clear()
            self.connection_usage.clear()


class ResponseCache:
    """Response cache with TTL and LRU eviction"""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: deque = deque(maxlen=max_size)
        self.lock = asyncio.Lock()
        
    def _make_key(self, method: str, url: str, params: Optional[Dict] = None) -> str:
        """Create cache key from request parameters"""
        key_data = f"{method}:{url}"
        if params:
            key_data += f":{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def get(self, method: str, url: str, params: Optional[Dict] = None) -> Optional[Any]:
        """Get cached response if available"""
        if method not in ['GET', 'HEAD']:
            # Only cache safe methods
            return None
            
        key = self._make_key(method, url, params)
        
        async with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                
                if entry.is_expired():
                    # Remove expired entry
                    del self.cache[key]
                    return None
                
                # Update hit count and access order
                entry.hit_count += 1
                self.access_order.remove(key)
                self.access_order.append(key)
                
                return entry.response
        
        return None
    
    async def set(self, method: str, url: str, response: Any, 
                  params: Optional[Dict] = None, ttl: Optional[float] = None):
        """Cache a response"""
        if method not in ['GET', 'HEAD']:
            return
            
        key = self._make_key(method, url, params)
        ttl = ttl or self.default_ttl
        
        async with self.lock:
            # Check if we need to evict
            if len(self.cache) >= self.max_size and key not in self.cache:
                # Evict least recently used
                if self.access_order:
                    lru_key = self.access_order.popleft()
                    del self.cache[lru_key]
            
            # Add to cache
            self.cache[key] = CacheEntry(
                response=response,
                timestamp=time.time(),
                ttl=ttl
            )
            
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
    
    async def clear(self):
        """Clear the cache"""
        async with self.lock:
            self.cache.clear()
            self.access_order.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_hits = sum(entry.hit_count for entry in self.cache.values())
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'total_hits': total_hits,
            'hit_rate': total_hits / max(1, total_hits + len(self.cache))
        }


class RetryPolicy:
    """Retry policy with exponential backoff"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 30.0, exponential_base: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.metrics = get_metrics_collector()
    
    async def execute_with_retry(self, func, operation_name: str = "request"):
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await func()
                if attempt > 0:
                    self.metrics.record_retry(operation_name, success=True)
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    
                    self.metrics.record_retry(operation_name, success=False)
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    self.metrics.record_retry(operation_name, success=False)
                    break
        
        raise last_exception


class ResilienceManager:
    """Manager for all resilience features"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        
        # Connection pooling
        self.connection_pool = ConnectionPool(
            max_connections=config.get('max_connections', 10)
        )
        
        # Response caching
        self.cache = ResponseCache(
            max_size=config.get('cache_size', 1000),
            default_ttl=config.get('cache_ttl', 300.0)
        )
        
        # Circuit breakers for each service
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Retry policy
        self.retry_policy = RetryPolicy(
            max_retries=config.get('max_retries', 3),
            base_delay=config.get('retry_base_delay', 1.0)
        )
        
        self.metrics = get_metrics_collector()
    
    def get_circuit_breaker(self, service_jid: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_jid not in self.circuit_breakers:
            self.circuit_breakers[service_jid] = CircuitBreaker(service_jid)
        return self.circuit_breakers[service_jid]
    
    async def execute_request(self, service_jid: str, request_func):
        """Execute request with full resilience features"""
        # Check circuit breaker
        circuit_breaker = self.get_circuit_breaker(service_jid)
        
        if not circuit_breaker.should_attempt():
            self.metrics.record_connection_failure('circuit_open')
            raise Exception(f"Circuit breaker open for {service_jid}")
        
        try:
            # Execute with retry policy
            result = await self.retry_policy.execute_with_retry(
                request_func,
                operation_name=f"request_to_{service_jid}"
            )
            
            # Record success
            circuit_breaker.record_success()
            return result
            
        except Exception as e:
            # Record failure
            circuit_breaker.record_failure()
            self.metrics.record_connection_failure(str(type(e).__name__))
            raise
    
    async def shutdown(self):
        """Shutdown resilience manager"""
        await self.connection_pool.close_all()
        await self.cache.clear()


# Global resilience manager
_manager: Optional[ResilienceManager] = None

def get_resilience_manager() -> ResilienceManager:
    """Get or create the global resilience manager"""
    global _manager
    if _manager is None:
        _manager = ResilienceManager()
    return _manager