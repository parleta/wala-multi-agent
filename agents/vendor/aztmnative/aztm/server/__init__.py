"""
Server integration for AZTM
Auto-hooks FastAPI and LangGraph apps to receive HTTP requests via XMPP
"""

import logging
from .fastapi_hook import find_fastapi_app, hook_fastapi
try:
    from .langgraph_hook import serve_langgraph, hook_langgraph_imports
except ImportError:
    serve_langgraph = None
    hook_langgraph_imports = None

logger = logging.getLogger(__name__)


def auto_hook_fastapi(client, config):
    """
    Auto-detect and hook FastAPI application

    Args:
        client: XMPP client instance
        config: Configuration object

    Returns:
        bool: True if FastAPI was hooked, False otherwise
    """
    logger.debug("Attempting to detect FastAPI application...")

    app = find_fastapi_app()
    if app:
        return hook_fastapi(app, client, config)

    return False
