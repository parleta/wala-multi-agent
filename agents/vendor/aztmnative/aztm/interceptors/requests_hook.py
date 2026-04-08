"""
Requests library interceptor for AZTM
Patches the requests library to route HTTP through XMPP
"""

import asyncio
import io
import json
import logging
import threading
from typing import Optional, Dict, Any
from unittest.mock import MagicMock

import requests
from requests.models import Response
from requests.structures import CaseInsensitiveDict

from aztm.core.auth import get_client, get_jid
from aztm.core.mapping import parse_url_components
from aztm.core.service_mapping import resolve_service_for_url, should_use_mapping
from aztm.protocol.message import create_request_envelope, parse_response_envelope

logger = logging.getLogger(__name__)

# Store original implementation
_original_request = None
_original_send = None


def patch_requests():
    """Patch the requests library to intercept HTTP requests"""
    global _original_request, _original_send

    if _original_request is not None:
        logger.warning("Requests library already patched")
        return

    # Store original implementations
    _original_request = requests.Session.request
    _original_send = requests.adapters.HTTPAdapter.send

    # Replace with our implementation
    requests.Session.request = patched_request
    requests.adapters.HTTPAdapter.send = patched_send

    logger.info("Requests library patched for AZTM")


def unpatch_requests():
    """Restore original requests library behavior"""
    global _original_request, _original_send

    if _original_request is None:
        logger.warning("Requests library not patched")
        return

    requests.Session.request = _original_request
    requests.adapters.HTTPAdapter.send = _original_send

    _original_request = None
    _original_send = None

    logger.info("Requests library unpatched")


def patched_request(self, method, url, **kwargs):
    """
    Intercept requests.Session.request calls

    This is the main entry point for HTTP interception
    """
    logger.debug(f"Intercepted request: {method} {url}")

    # Check if this should go through XMPP
    if not should_intercept(url):
        logger.debug(f"Not intercepting {url}, using original implementation")
        return _original_request(self, method, url, **kwargs)

    try:
        # Get XMPP client
        client = get_client()
        client_jid = get_jid()

        # Check for service mapping first
        mapped_service = resolve_service_for_url(url)
        logger.debug(f"Service mapping lookup for {url}: {mapped_service}")
        if mapped_service:
            # Use mapped service
            from urllib.parse import urlparse
            parsed = urlparse(url)
            from aztm.core.mapping import path_to_subject
            target_jid = mapped_service
            subject = path_to_subject(parsed.path, parsed.query or "")
            path = parsed.path
            query = parsed.query or ""
            logger.debug(f"Using mapped service: {target_jid}")
        else:
            # Use default URL to JID mapping
            target_jid, subject, path, query = parse_url_components(url, client_jid)
            logger.debug(f"Using default mapping: {target_jid}")

        # Extract request data
        headers = kwargs.get("headers", {})
        if hasattr(headers, "items"):
            headers = dict(headers.items())

        # Handle different body formats
        body = None
        if "json" in kwargs:
            body = kwargs["json"]
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
        elif "data" in kwargs:
            body = kwargs["data"]
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="ignore")

        # Add timeout if specified
        timeout = kwargs.get("timeout", 30)

        # Create request envelope
        envelope = create_request_envelope(
            method=method, path=path, query=query, headers=headers, body=body
        )

        # Send via transport and wait for response
        logger.info(f"Routing via secure transport: subject={subject}")
        response_data = send_http_over_xmpp_sync(client, target_jid, subject, envelope, timeout)

        # Convert to requests.Response
        return convert_to_requests_response(response_data, url)

    except Exception as e:
        logger.error(f"Error in AZTM request interception: {e}")
        # Fall back to original implementation on error
        return _original_request(self, method, url, **kwargs)


def patched_send(self, request, **kwargs):
    """
    Intercept HTTPAdapter.send calls (lower level)
    """
    url = request.url

    if not should_intercept(url):
        return _original_send(self, request, **kwargs)

    # Create a mock session and use patched_request
    session = requests.Session()
    return session.request(
        method=request.method, url=request.url, headers=request.headers, data=request.body, **kwargs
    )


def should_intercept(url: str) -> bool:
    """
    Determine if a URL should be intercepted

    Args:
        url: The URL to check

    Returns:
        bool: True if should be intercepted, False otherwise
    """
    # Don't intercept file URLs
    if url.startswith("file://"):
        return False
    
    # Check if URL has a service mapping (including localhost)
    if should_use_mapping(url):
        return True
    
    # Don't intercept unmapped localhost URLs
    if url.startswith(("http://localhost", "http://127.0.0.1", "http://[::1]")):
        # Unless there's a mapping for it
        return False

    # All other HTTP/HTTPS URLs should be intercepted
    return url.startswith(("http://", "https://"))


def send_http_over_xmpp_sync(
    client, target_jid: str, subject: str, envelope: str, timeout: float
) -> Dict[str, Any]:
    """
    Synchronously send HTTP over XMPP (wrapper for async function)

    Args:
        client: XMPP client
        target_jid: Target JID
        subject: Message subject
        envelope: Request envelope
        timeout: Request timeout

    Returns:
        Response data dictionary
    """
    import concurrent.futures
    
    # The XMPP client stores its event loop
    if hasattr(client, 'event_loop') and client.event_loop:
        loop = client.event_loop
        logger.info(f"🔄 Using client's event loop: {loop}")
        logger.info(f"   Loop is running: {loop.is_running()}")
        logger.info(f"   Current thread: {threading.current_thread().name}")
        
        # The loop should be running in another thread
        # Use run_coroutine_threadsafe to schedule the coroutine
        logger.info(f"   Scheduling send_http_over_xmpp in loop...")
        future = asyncio.run_coroutine_threadsafe(
            client.send_http_over_xmpp(target_jid, subject, envelope, timeout),
            loop
        )
        
        try:
            response_data = future.result(timeout=timeout)
            logger.debug(f"Got response: {response_data}")
            return response_data
        except concurrent.futures.TimeoutError:
            from aztm.protocol.errors import TransportTimeout
            raise TransportTimeout(f"Request timed out after {timeout}s")
        except Exception as e:
            logger.error(f"Transport send error: {e}")
            raise
    else:
        # Fallback: try to get current event loop
        logger.warning("Client doesn't have event_loop attribute, trying fallback")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        
        if loop and loop.is_running():
            # We're in a loop, use run_coroutine_threadsafe
            future = asyncio.run_coroutine_threadsafe(
                client.send_http_over_xmpp(target_jid, subject, envelope, timeout),
                loop
            )
            return future.result(timeout=timeout)
        else:
            # No running loop, run until complete
            return loop.run_until_complete(
                client.send_http_over_xmpp(target_jid, subject, envelope, timeout)
            )


def convert_to_requests_response(xmpp_response: Dict[str, Any], url: str) -> Response:
    """
    Convert XMPP response to requests.Response object

    Args:
        xmpp_response: Response from XMPP
        url: Original request URL

    Returns:
        requests.Response object
    """
    # Parse response envelope
    envelope = parse_response_envelope(xmpp_response["body"])
    aztm = envelope["_aztm"]

    # Create Response object
    response = Response()
    response.status_code = aztm["status"]
    response.url = url

    # Set headers
    response.headers = CaseInsensitiveDict(aztm.get("headers", {}))

    # Set body
    payload = envelope.get("payload")
    if payload:
        if isinstance(payload, dict) or isinstance(payload, list):
            # JSON response
            response._content = json.dumps(payload).encode("utf-8")
            if "Content-Type" not in response.headers:
                response.headers["Content-Type"] = "application/json"
        elif isinstance(payload, str):
            # String response
            response._content = payload.encode("utf-8")
        elif isinstance(payload, bytes):
            # Binary response
            response._content = payload
        else:
            # Convert to string
            response._content = str(payload).encode("utf-8")
    else:
        response._content = b""

    # Set encoding
    response.encoding = "utf-8"

    # Set other attributes
    response.reason = get_reason_phrase(response.status_code)
    response.elapsed = MagicMock()  # Mock elapsed time

    return response


def get_reason_phrase(status_code: int) -> str:
    """Get HTTP reason phrase for status code"""
    reason_phrases = {
        100: "Continue",
        101: "Switching Protocols",
        200: "OK",
        201: "Created",
        202: "Accepted",
        204: "No Content",
        301: "Moved Permanently",
        302: "Found",
        304: "Not Modified",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }
    return reason_phrases.get(status_code, "Unknown")
