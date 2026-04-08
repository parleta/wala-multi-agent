"""
AZTM Health Checks - Service Health Monitoring
Provides health check endpoints and service discovery
"""
import asyncio
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import json


class HealthStatus(Enum):
    """Service health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health status of a service"""
    service_id: str
    status: HealthStatus
    last_check: float
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'service_id': self.service_id,
            'status': self.status.value,
            'last_check': self.last_check,
            'response_time': self.response_time,
            'error_message': self.error_message,
            'metadata': self.metadata
        }


class HealthChecker:
    """Health checker for AZTM services"""
    
    def __init__(self, check_interval: float = 30.0, timeout: float = 5.0):
        self.check_interval = check_interval
        self.timeout = timeout
        self.services: Dict[str, ServiceHealth] = {}
        self.check_callbacks: Dict[str, Callable] = {}
        self.running = False
        self._task: Optional[asyncio.Task] = None
        
    def register_service(self, service_id: str, check_callback: Callable):
        """Register a service for health monitoring"""
        self.check_callbacks[service_id] = check_callback
        self.services[service_id] = ServiceHealth(
            service_id=service_id,
            status=HealthStatus.UNKNOWN,
            last_check=0
        )
    
    def unregister_service(self, service_id: str):
        """Unregister a service from health monitoring"""
        self.check_callbacks.pop(service_id, None)
        self.services.pop(service_id, None)
    
    async def check_service(self, service_id: str) -> ServiceHealth:
        """Check health of a specific service"""
        if service_id not in self.check_callbacks:
            return ServiceHealth(
                service_id=service_id,
                status=HealthStatus.UNKNOWN,
                last_check=time.time(),
                error_message="Service not registered"
            )
        
        start_time = time.time()
        
        try:
            # Call the health check callback with timeout
            callback = self.check_callbacks[service_id]
            result = await asyncio.wait_for(
                callback(),
                timeout=self.timeout
            )
            
            response_time = time.time() - start_time
            
            # Determine status based on response time
            if response_time < self.timeout * 0.5:
                status = HealthStatus.HEALTHY
            elif response_time < self.timeout * 0.8:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            health = ServiceHealth(
                service_id=service_id,
                status=status,
                last_check=time.time(),
                response_time=response_time,
                metadata=result if isinstance(result, dict) else {}
            )
            
        except asyncio.TimeoutError:
            health = ServiceHealth(
                service_id=service_id,
                status=HealthStatus.UNHEALTHY,
                last_check=time.time(),
                error_message="Health check timeout"
            )
            
        except Exception as e:
            health = ServiceHealth(
                service_id=service_id,
                status=HealthStatus.UNHEALTHY,
                last_check=time.time(),
                error_message=str(e)
            )
        
        self.services[service_id] = health
        return health
    
    async def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Check health of all registered services"""
        tasks = [
            self.check_service(service_id)
            for service_id in self.check_callbacks.keys()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for service_id, result in zip(self.check_callbacks.keys(), results):
            if isinstance(result, Exception):
                self.services[service_id] = ServiceHealth(
                    service_id=service_id,
                    status=HealthStatus.UNHEALTHY,
                    last_check=time.time(),
                    error_message=str(result)
                )
        
        return self.services.copy()
    
    async def _health_check_loop(self):
        """Background loop for periodic health checks"""
        while self.running:
            try:
                await self.check_all_services()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"Error in health check loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    def start(self):
        """Start background health checking"""
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._health_check_loop())
    
    def stop(self):
        """Stop background health checking"""
        self.running = False
        if self._task:
            self._task.cancel()
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status"""
        if not self.services:
            return HealthStatus.UNKNOWN
        
        statuses = [s.status for s in self.services.values()]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        return {
            'overall_status': self.get_overall_status().value,
            'timestamp': time.time(),
            'services': {
                service_id: health.to_dict()
                for service_id, health in self.services.items()
            },
            'healthy_count': sum(
                1 for s in self.services.values()
                if s.status == HealthStatus.HEALTHY
            ),
            'unhealthy_count': sum(
                1 for s in self.services.values()
                if s.status == HealthStatus.UNHEALTHY
            )
        }


class ServiceDiscovery:
    """Service discovery for AZTM"""
    
    def __init__(self):
        self.services: Dict[str, Dict[str, Any]] = {}
        self.service_watchers: List[Callable] = []
        
    def register(self, service_id: str, service_jid: str, 
                 metadata: Optional[Dict[str, Any]] = None):
        """Register a service"""
        self.services[service_id] = {
            'jid': service_jid,
            'registered_at': time.time(),
            'metadata': metadata or {}
        }
        
        # Notify watchers
        for watcher in self.service_watchers:
            try:
                watcher('register', service_id, self.services[service_id])
            except:
                pass
    
    def unregister(self, service_id: str):
        """Unregister a service"""
        if service_id in self.services:
            service_info = self.services.pop(service_id)
            
            # Notify watchers
            for watcher in self.service_watchers:
                try:
                    watcher('unregister', service_id, service_info)
                except:
                    pass
    
    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get service information"""
        return self.services.get(service_id)
    
    def list_services(self) -> List[str]:
        """List all registered service IDs"""
        return list(self.services.keys())
    
    def find_services_by_metadata(self, key: str, value: Any) -> List[str]:
        """Find services by metadata key-value"""
        matching = []
        for service_id, info in self.services.items():
            if info['metadata'].get(key) == value:
                matching.append(service_id)
        return matching
    
    def add_watcher(self, callback: Callable):
        """Add a service discovery watcher"""
        self.service_watchers.append(callback)
    
    def remove_watcher(self, callback: Callable):
        """Remove a service discovery watcher"""
        if callback in self.service_watchers:
            self.service_watchers.remove(callback)


# Global instances
_health_checker: Optional[HealthChecker] = None
_service_discovery: Optional[ServiceDiscovery] = None


def get_health_checker() -> HealthChecker:
    """Get or create the global health checker"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def get_service_discovery() -> ServiceDiscovery:
    """Get or create the global service discovery"""
    global _service_discovery
    if _service_discovery is None:
        _service_discovery = ServiceDiscovery()
    return _service_discovery