"""
HTTPX interceptor for AZTM
Patches httpx library to route HTTP requests through AZTM
"""

import logging
import json
import asyncio
from typing import Optional, Dict, Any, Union
from functools import wraps
import httpx
from httpx._models import Request, Response
from httpx._types import URLTypes

logger = logging.getLogger(__name__)

# Store original functions
_original_send = None
_original_async_send = None
_patched = False


def patch_httpx():
    """
    Monkey-patch httpx to intercept HTTP requests and route them through AZTM
    """
    global _original_send, _original_async_send, _patched
    
    if _patched:
        logger.debug("httpx already patched")
        return
    
    logger.info("Patching httpx library for AZTM")
    
    # Import here to avoid circular dependency
    from aztm.core.auth import get_client
    from aztm.core.service_mapping import resolve_service_mapping
    
    # Store original methods
    _original_send = httpx.Client.send
    _original_async_send = httpx.AsyncClient.send
    
    def patched_send(self, request: Request, **kwargs) -> Response:
        """Patched sync send method for httpx.Client"""
        
        # Get AZTM client
        client = get_client()
        if not client:
            # AZTM not initialized, use original
            return _original_send(self, request, **kwargs)
        
        # Check if URL should be routed through AZTM
        url_str = str(request.url)
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        host_port = f"{host}:{port}"
        
        # Check service mapping
        target_jid = resolve_service_mapping(host_port)
        if not target_jid:
            # No mapping found, check if it's localhost
            if host in ["localhost", "127.0.0.1"]:
                # Try with just the port
                target_jid = resolve_service_mapping(f"localhost:{port}")
        
        if not target_jid:
            logger.debug(f"No AZTM mapping for {host_port}, using original httpx")
            return _original_send(self, request, **kwargs)
        
        logger.debug(f"Routing httpx request to {url_str} via secure transport")
        
        try:
            # Convert httpx request to AZTM format
            from aztm.protocol.message import create_request_envelope
            
            # Prepare headers
            headers = dict(request.headers)
            
            # Prepare body
            body = None
            if request.content:
                # Read the content
                content_bytes = request.content
                content_type = headers.get("content-type", "")
                
                if "application/json" in content_type:
                    try:
                        body = json.loads(content_bytes.decode("utf-8"))
                    except:
                        body = content_bytes.decode("utf-8", errors="ignore")
                else:
                    body = content_bytes.decode("utf-8", errors="ignore")
            
            # Create request envelope
            envelope = create_request_envelope(
                method=request.method,
                path=request.url.path,
                query=request.url.query.decode("utf-8") if request.url.query else "",
                headers=headers,
                body=body
            )
            
            # Send via AZTM (synchronously)
            subject = f"httpx:{host_port}{request.url.path}"
            
            # Use the sync XMPP send mechanism
            # Get timeout from the client's timeout settings
            # httpx stores timeout on the client, not in kwargs
            httpx_timeout = 30.0  # default
            
            if hasattr(self, 'timeout') and self.timeout:
                if hasattr(self.timeout, 'read') and self.timeout.read is not None:
                    httpx_timeout = float(self.timeout.read)
                elif hasattr(self.timeout, 'timeout') and self.timeout.timeout is not None:
                    # Sometimes it's just a single timeout value
                    httpx_timeout = float(self.timeout.timeout)
            
            logger.debug(f"Using timeout: {httpx_timeout}s for sync request")
            
            response_data = send_httpx_over_xmpp_sync(
                client, target_jid, subject, envelope, 
                timeout=httpx_timeout
            )
            
            # Convert AZTM response to httpx Response
            return convert_to_httpx_response(response_data, request)
            
        except Exception as e:
            logger.error(f"Error in AZTM httpx interception: {e}")
            # Fall back to original
            return _original_send(self, request, **kwargs)
    
    async def patched_async_send(self, request: Request, **kwargs) -> Response:
        """Patched async send method for httpx.AsyncClient"""
        
        # Get AZTM client
        client = get_client()
        if not client:
            # AZTM not initialized, use original
            return await _original_async_send(self, request, **kwargs)
        
        # Check if URL should be routed through AZTM
        url_str = str(request.url)
        host = request.url.host
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        host_port = f"{host}:{port}"
        
        # Check service mapping
        target_jid = resolve_service_mapping(host_port)
        if not target_jid:
            if host in ["localhost", "127.0.0.1"]:
                target_jid = resolve_service_mapping(f"localhost:{port}")
        
        if not target_jid:
            logger.debug(f"No AZTM mapping for {host_port}, using original httpx")
            return await _original_async_send(self, request, **kwargs)
        
        logger.debug(f"Routing httpx async request to {url_str} via secure transport")
        
        try:
            # Convert httpx request to AZTM format
            from aztm.protocol.message import create_request_envelope
            
            # Prepare headers
            headers = dict(request.headers)
            
            # Prepare body
            body = None
            if request.content:
                content_bytes = request.content
                content_type = headers.get("content-type", "")
                
                if "application/json" in content_type:
                    try:
                        body = json.loads(content_bytes.decode("utf-8"))
                    except:
                        body = content_bytes.decode("utf-8", errors="ignore")
                else:
                    body = content_bytes.decode("utf-8", errors="ignore")
            
            # Create request envelope
            envelope = create_request_envelope(
                method=request.method,
                path=request.url.path,
                query=request.url.query.decode("utf-8") if request.url.query else "",
                headers=headers,
                body=body
            )
            
            # Send via AZTM (asynchronously)
            subject = f"httpx:{host_port}{request.url.path}"
            
            # Get timeout from the client's timeout settings
            httpx_timeout = 30.0  # default
            
            if hasattr(self, 'timeout') and self.timeout:
                if hasattr(self.timeout, 'read') and self.timeout.read is not None:
                    httpx_timeout = float(self.timeout.read)
                elif hasattr(self.timeout, 'timeout') and self.timeout.timeout is not None:
                    httpx_timeout = float(self.timeout.timeout)
            
            logger.debug(f"Using timeout: {httpx_timeout}s for async request")
            
            response_data = await client.send_http_over_xmpp(
                target_jid, subject, envelope,
                timeout=httpx_timeout
            )
            
            # Convert AZTM response to httpx Response
            return convert_to_httpx_response(response_data, request)
            
        except Exception as e:
            logger.error(f"Error in AZTM httpx async interception: {e}")
            # Fall back to original
            return await _original_async_send(self, request, **kwargs)
    
    # Apply patches
    httpx.Client.send = patched_send
    httpx.AsyncClient.send = patched_async_send
    
    # Also patch the low-level transport for better coverage
    patch_httpx_transport()
    
    _patched = True
    logger.info("httpx library patched successfully")


def patch_httpx_transport():
    """
    Patch httpx transport classes for deeper integration
    """
    try:
        from httpx._transports.default import HTTPTransport, AsyncHTTPTransport
        
        # Store original handle_request methods
        HTTPTransport._original_handle_request = HTTPTransport.handle_request
        AsyncHTTPTransport._original_handle_async_request = AsyncHTTPTransport.handle_async_request
        
        def patched_handle_request(self, request: Request) -> Response:
            """Patched handle_request for HTTPTransport"""
            # Check if this should go through AZTM
            from aztm.core.auth import get_client
            from aztm.core.service_mapping import resolve_service_mapping
            
            client = get_client()
            if not client:
                return self._original_handle_request(request)
            
            host = request.url.host
            port = request.url.port or (443 if request.url.scheme == "https" else 80)
            host_port = f"{host}:{port}"
            
            target_jid = resolve_service_mapping(host_port)
            if not target_jid and host in ["localhost", "127.0.0.1"]:
                target_jid = resolve_service_mapping(f"localhost:{port}")
            
            if not target_jid:
                return self._original_handle_request(request)
            
            # Route through AZTM
            logger.debug(f"HTTPTransport routing {request.url} through AZTM")
            
            # This will be caught by the patched send method
            return self._original_handle_request(request)
        
        HTTPTransport.handle_request = patched_handle_request
        
    except ImportError:
        logger.debug("Could not patch httpx transport classes")


def unpatch_httpx():
    """
    Restore original httpx behavior
    """
    global _original_send, _original_async_send, _patched
    
    if not _patched:
        logger.debug("httpx not patched, nothing to restore")
        return
    
    logger.info("Restoring original httpx behavior")
    
    if _original_send:
        httpx.Client.send = _original_send
    
    if _original_async_send:
        httpx.AsyncClient.send = _original_async_send
    
    # Restore transport methods
    try:
        from httpx._transports.default import HTTPTransport, AsyncHTTPTransport
        if hasattr(HTTPTransport, '_original_handle_request'):
            HTTPTransport.handle_request = HTTPTransport._original_handle_request
            delattr(HTTPTransport, '_original_handle_request')
    except:
        pass
    
    _original_send = None
    _original_async_send = None
    _patched = False
    
    logger.info("httpx library restored to original behavior")


def send_httpx_over_xmpp_sync(client, target_jid: str, subject: str, envelope: str, timeout: float = 30):
    """
    Send HTTP request over XMPP synchronously (for sync httpx client)
    
    Args:
        client: XMPP client
        target_jid: Target JID to send to
        subject: Message subject
        envelope: Request envelope
        timeout: Timeout in seconds
        
    Returns:
        Response data dictionary
    """
    import concurrent.futures
    import threading
    
    # Create a new event loop in a separate thread for async operations
    def run_in_new_loop():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(
                client.send_http_over_xmpp(target_jid, subject, envelope, timeout)
            )
        finally:
            new_loop.close()
    
    # Run in executor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_new_loop)
        try:
            response_data = future.result(timeout=timeout)
            return response_data
        except concurrent.futures.TimeoutError:
            from aztm.protocol.errors import TransportTimeout
            raise TransportTimeout(f"Request timed out after {timeout}s")


def convert_to_httpx_response(xmpp_response: Dict[str, Any], request: Request) -> Response:
    """
    Convert XMPP response to httpx Response object
    
    Args:
        xmpp_response: Response data from XMPP
        request: Original httpx request
        
    Returns:
        httpx Response object
    """
    from aztm.protocol.message import parse_response_envelope
    
    try:
        # Parse the response envelope
        envelope = parse_response_envelope(xmpp_response["body"])
        aztm_meta = envelope["_aztm"]
        payload = envelope.get("payload")
        
        # Extract response components
        status_code = aztm_meta["status"]
        headers = aztm_meta.get("headers", {})
        
        # Prepare response content
        if payload is not None:
            if isinstance(payload, dict) or isinstance(payload, list):
                content = json.dumps(payload).encode("utf-8")
                if "content-type" not in headers:
                    headers["content-type"] = "application/json"
            elif isinstance(payload, str):
                content = payload.encode("utf-8")
            elif isinstance(payload, bytes):
                content = payload
            else:
                content = str(payload).encode("utf-8")
        else:
            content = b""
        
        # Create httpx Response
        response = Response(
            status_code=status_code,
            headers=headers,
            content=content,
            request=request,
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error converting transport response to httpx: {e}")
        # Return error response
        return Response(
            status_code=500,
            headers={"content-type": "text/plain"},
            content=f"AZTM conversion error: {str(e)}".encode("utf-8"),
            request=request,
        )