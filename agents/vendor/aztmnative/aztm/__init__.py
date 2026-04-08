"""
AZTM - Agentic Zero Trust Mesh
HTTP over secure transport with zero code changes
"""

__version__ = "0.1.0"
__author__ = "Elad Rave"

# Configure privacy redaction as early as possible
try:
    from aztm.observability.privacy import configure_privacy_from_env
    configure_privacy_from_env()
except Exception:
    # Do not fail import if privacy configuration cannot be applied
    pass

# Main API
from aztm.core.auth import login, get_client
from aztm.core.service_mapping import (
    register_service_mapping,
    set_default_service,
    register_service_pattern
)

# New Native API
from aztm.client import connect, connect_async, Session, disconnect

# Server API (optional imports)
try:
    from aztm.server.langgraph_hook import serve_langgraph
except ImportError:
    serve_langgraph = None

# Auto-patch httpx on import (if available)
try:
    import os
    if os.environ.get("AZTM_DISABLE_AUTO_PATCH") != "1":
        from aztm.interceptors.httpx_hook import patch_httpx
        patch_httpx()
except Exception:
    # If httpx is not installed or patching fails, continue without interception
    pass

__all__ = [
    "login",
    "get_client",
    "connect",
    "connect_async",
    "Session",
    "disconnect",
    "register_service_mapping",
    "set_default_service",
    "register_service_pattern",
    "serve_langgraph",
    "__version__",
]
