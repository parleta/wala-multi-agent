"""
HTTP interceptors for AZTM
Patches requests and httpx libraries to route through XMPP
"""

import logging
from .requests_hook import patch_requests, unpatch_requests
try:
    from .httpx_hook import patch_httpx, unpatch_httpx
except ImportError:
    patch_httpx = None
    unpatch_httpx = None

logger = logging.getLogger(__name__)


def patch_all(client, config):
    """
    Patch all supported HTTP libraries

    Args:
        client: XMPP client instance
        config: Configuration object
    """
    logger.info("Patching HTTP libraries...")

    # Patch requests library
    try:
        patch_requests()
        logger.info("Successfully patched requests library")
    except Exception as e:
        logger.error(f"Failed to patch requests: {e}")

    # Patch httpx library
    if patch_httpx:
        try:
            patch_httpx()
            logger.info("Successfully patched httpx library")
        except Exception as e:
            logger.error(f"Failed to patch httpx: {e}")
    else:
        logger.debug("httpx patching not available")


def unpatch_all():
    """
    Restore original HTTP library behavior
    """
    logger.info("Unpatching HTTP libraries...")

    # Unpatch requests library
    try:
        unpatch_requests()
        logger.info("Successfully unpatched requests library")
    except Exception as e:
        logger.error(f"Failed to unpatch requests: {e}")
    
    # Unpatch httpx library
    if unpatch_httpx:
        try:
            unpatch_httpx()
            logger.info("Successfully unpatched httpx library")
        except Exception as e:
            logger.error(f"Failed to unpatch httpx: {e}")
