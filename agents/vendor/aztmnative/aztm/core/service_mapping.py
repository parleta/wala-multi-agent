"""
Service mapping for AZTM
Allows flexible URL to service ID mapping with localhost support
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Global service mappings
_service_mappings: Dict[str, str] = {}
_default_service: Optional[str] = None
_pattern_mappings: Dict[str, str] = {}


def register_service_mapping(mappings: Dict[str, str]) -> None:
    """
    Register URL host to service ID mappings
    
    Args:
        mappings: Dictionary of host:port to service ID mappings
        
    Example:
        register_service_mapping({
            "localhost:8080": "aztmapi@sure.im",
            "127.0.0.1:8080": "aztmapi@sure.im",
            "api.example.com": "example-api@sure.im"
        })
    """
    global _service_mappings
    _service_mappings.update(mappings)
    logger.info(f"Registered {len(mappings)} service mappings")
    for host, service in mappings.items():
        logger.debug(f"  {host} -> {service}")


def set_default_service(service_id: str) -> None:
    """
    Set a default service for all unmapped URLs
    
    Args:
        service_id: Default service ID (e.g., "aztmapi@sure.im")
    """
    global _default_service
    _default_service = service_id
    logger.info(f"Set default service to {service_id}")


def register_service_pattern(pattern: str, service: str) -> None:
    """
    Register a pattern-based mapping
    
    Args:
        pattern: Pattern like "*:8080" or "*.local"
        service: Service ID to map to
    """
    global _pattern_mappings
    _pattern_mappings[pattern] = service
    logger.info(f"Registered pattern mapping: {pattern} -> {service}")


def load_mappings_from_env() -> None:
    """
    Load service mappings from environment variables
    
    Looks for:
    - SERVICE_MAP: JSON dictionary of mappings (non-AZTM prefix to avoid Config parsing)
    - AZTM_SERVICE_MAP: JSON dictionary of mappings (legacy)
    - AZTM_DEFAULT_SERVICE: Default service ID
    - AZTM_LOCALHOST_SERVICE: Service for localhost URLs
    """
    # Load JSON mapping - check both with and without AZTM_ prefix
    service_map_json = os.getenv("SERVICE_MAP") or os.getenv("AZTM_SERVICE_MAP")
    if service_map_json:
        try:
            mappings = json.loads(service_map_json)
            register_service_mapping(mappings)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid SERVICE_MAP JSON: {e}")
    
    # Load default service
    default_service = os.getenv("AZTM_DEFAULT_SERVICE")
    if default_service:
        set_default_service(default_service)
    
    # Special handling for localhost
    localhost_service = os.getenv("AZTM_LOCALHOST_SERVICE")
    if localhost_service:
        register_service_mapping({
            "localhost": localhost_service,
            "127.0.0.1": localhost_service,
            "localhost:8080": localhost_service,
            "127.0.0.1:8080": localhost_service,
            "localhost:8000": localhost_service,
            "127.0.0.1:8000": localhost_service,
            "[::1]": localhost_service,
        })


def resolve_service_for_url(url: str) -> Optional[str]:
    """
    Resolve which service ID to use for a given URL
    
    Args:
        url: Full URL (e.g., "http://localhost:8080/path")
        
    Returns:
        Service ID if mapped, None otherwise
    """
    parsed = urlparse(url)
    
    # Build various host representations to check
    hostname = parsed.hostname or parsed.netloc
    port = parsed.port
    
    # Check exact mappings first
    if port:
        host_port = f"{hostname}:{port}"
        if host_port in _service_mappings:
            logger.debug(f"Resolved {host_port} -> {_service_mappings[host_port]}")
            return _service_mappings[host_port]
    
    # Check hostname without port
    if hostname in _service_mappings:
        logger.debug(f"Resolved {hostname} -> {_service_mappings[hostname]}")
        return _service_mappings[hostname]
    
    # Check pattern mappings
    for pattern, service in _pattern_mappings.items():
        if _matches_pattern(hostname, port, pattern):
            logger.debug(f"Pattern matched {pattern} -> {service}")
            return service
    
    # Use default service if set
    if _default_service:
        logger.debug(f"Using default service -> {_default_service}")
        return _default_service
    
    return None


def _matches_pattern(hostname: str, port: Optional[int], pattern: str) -> bool:
    """
    Check if hostname:port matches a pattern
    
    Args:
        hostname: Host name
        port: Port number (optional)
        pattern: Pattern like "*:8080" or "*.local"
        
    Returns:
        True if matches
    """
    if pattern.startswith("*:") and port:
        # Port wildcard pattern
        pattern_port = pattern.split(":")[1]
        return str(port) == pattern_port
    
    if pattern.endswith("*") and pattern.startswith("*"):
        # Contains pattern
        middle = pattern[1:-1]
        return middle in hostname
    
    if pattern.startswith("*."):
        # Domain wildcard
        suffix = pattern[1:]  # includes the dot
        return hostname.endswith(suffix)
    
    if pattern.endswith("*"):
        # Prefix pattern
        prefix = pattern[:-1]
        return hostname.startswith(prefix)
    
    return False


def should_use_mapping(url: str) -> bool:
    """
    Check if a URL should use service mapping instead of default URL->JID conversion
    
    Args:
        url: URL to check
        
    Returns:
        True if a mapping exists for this URL
    """
    return resolve_service_for_url(url) is not None


def resolve_service_mapping(host_port: str) -> Optional[str]:
    """
    Resolve service ID for a host:port combination
    
    Args:
        host_port: Host and port like "localhost:8080" or just "localhost"
        
    Returns:
        Service ID if mapped, None otherwise
    """
    # Check exact mapping first
    if host_port in _service_mappings:
        logger.debug(f"Resolved {host_port} -> {_service_mappings[host_port]}")
        return _service_mappings[host_port]
    
    # Try to parse and check hostname separately
    if ":" in host_port:
        hostname = host_port.split(":")[0]
        port = int(host_port.split(":")[1])
        
        # Check hostname without port
        if hostname in _service_mappings:
            logger.debug(f"Resolved {hostname} -> {_service_mappings[hostname]}")
            return _service_mappings[hostname]
        
        # Check pattern mappings
        for pattern, service in _pattern_mappings.items():
            if _matches_pattern(hostname, port, pattern):
                logger.debug(f"Pattern matched {pattern} -> {service}")
                return service
    else:
        # Just hostname, no port
        if host_port in _service_mappings:
            return _service_mappings[host_port]
    
    # Use default service if set
    if _default_service:
        logger.debug(f"Using default service -> {_default_service}")
        return _default_service
    
    return None


# Auto-load from environment on import
load_mappings_from_env()