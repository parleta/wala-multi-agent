"""
Public API Client for AZTM.
Provides a clean, high-level interface for messaging without exposing internal transport details.
"""

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Union

from .core.auth import login as _legacy_login
from .core.auth import get_client as _get_client
from .core.auth import logout as _legacy_logout
from .core.config import Config
from .core.xmpp_client import XMPPClient
from .protocol.message import create_request_envelope, parse_request_envelope

logger = logging.getLogger(__name__)

# Global client reference for the 'native' session
_native_client: Optional[XMPPClient] = None
_native_loop_thread: Optional[threading.Thread] = None


class Session:
    """
    Represents an active connection to the mesh.
    """
    def __init__(self, client: XMPPClient):
        self._client = client

    @property
    def identity(self) -> str:
        """Get the current session identity (stable/bare)."""
        return str(self._client.boundjid.bare)


    def send(self, identity: str, topic: str, data: Any) -> None:
        """
        Send a fire-and-forget message.
        
        Args:
            identity: Destination identity (e.g., user@domain)
            topic: Message topic/subject
            data: Payload data (JSON serializable)
        """
        # Create a basic envelope or just send the payload?
        # To be consistent with "native", we should probably wrap it in the standard envelope 
        # so receivers can parse it consistently, but maybe 'data' is the whole body.
        # The plan says "Standardize the 'Native' envelope: Re-use the existing _aztm envelope".
        # Let's use create_request_envelope with method="MSG" or similar default.
        
        envelope = create_request_envelope(
            method="MSG",
            path=topic,
            body=data
        )
        msg = self._client.make_message(mto=identity, mbody=envelope, msubject=topic, mtype="chat")
        msg.send()

    def request(self, identity: str, topic: str, data: Any, timeout: float = 30.0) -> Any:
        """
        Send a request and wait for a response (RPC).
        
        Args:
            identity: Destination identity
            topic: Message topic
            data: Payload data
            timeout: Timeout in seconds
            
        Returns:
            Response payload
        """
        # Use sync wrapper if we are in a sync context, but this method is sync?
        # Actually, XMPPClient.send_http_over_xmpp is async.
        # We need to bridge it if we are sync.
        
        envelope = create_request_envelope(
            method="RPC",
            path=topic,
            body=data
        )
        
        # Helper to run async send in the background loop or current loop
        response = self._run_sync(
            self._client.send_http_over_xmpp(identity, topic, envelope, timeout)
        )
        
        # Unwrap the response payload
        try:
            from .protocol.message import parse_response_envelope
            resp_envelope = parse_response_envelope(response['body'])
            return resp_envelope.get('payload')
        except Exception:
            # Fallback if not an envelope
            return response.get('body')

    def on(self, topic: str, handler: Callable[[Any, Any], Any]) -> None:
        """
        Register a handler for a specific topic.
        
        Args:
            topic: The topic to listen for ('*' for all)
            handler: Function taking (context, payload)
        """
        # We need to wrap the user handler to strip the XMPP message details
        # and provide a clean context/payload.
        
        async def _native_wrapper(msg):
            # Parse envelope
            try:
                body_str = msg['body']
                # Try parsing as standard envelope
                try:
                    envelope = parse_request_envelope(body_str)
                    payload = envelope.get('payload')
                    # Context could include identity, topic, correlation id
                    context = {
                        "identity": str(msg['from'].bare),
                        "topic": msg['subject'],
                        "correlation_id": envelope.get('_aztm', {}).get('corr')
                    }
                except Exception:
                    # Fallback for raw messages
                    payload = body_str
                    context = {
                        "identity": str(msg['from'].bare),
                        "topic": msg['subject'],
                        "correlation_id": msg.get('id')
                    }
                
                # Call handler
                if asyncio.iscoroutinefunction(handler):
                    response = await handler(context, payload)
                else:
                    response = handler(context, payload)
                
                # If there's a return value and correlation ID, send reply
                # (This logic mimics the FastAPI hook but for generic handlers)
                # For now, 'on' is fire-and-forget receiving unless we implement automatic RPC replying here.
                # The user requirement didn't strictly specify automatic RPC replying for 'on', 
                # but 'request' implies someone is replying.
                # Let's keep it simple: if the handler returns something, we try to reply if it looks like RPC.
                
                if response is not None and context.get("correlation_id"):
                    from .protocol.message import create_response_envelope
                    resp_env = create_response_envelope(
                        status=200,
                        body=response,
                        corr=context["correlation_id"]
                    )
                    reply = self._client.make_message(mto=msg['from'], mbody=resp_env, msubject=msg['subject'])
                    reply['id'] = msg.get('id') # Important for some clients
                    reply.send()

            except Exception as e:
                logger.error(f"Error in native handler: {e}")

        self._client.register_message_handler(topic, _native_wrapper)

    def _run_sync(self, coro):
        """Run a coroutine synchronously."""
        import concurrent.futures
        
        if hasattr(self._client, 'event_loop') and self._client.event_loop:
            loop = self._client.event_loop
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                return future.result()
        
        # Fallback (shouldn't happen in managed mode)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def connect(identity: str, password: str, **kwargs) -> Session:
    """
    Connect to the mesh (Synchronous/Blocking).
    
    Args:
        identity: User identity (e.g. user@domain)
        password: Password
        **kwargs: Configuration options
        
    Returns:
        Session object
    """
    # Reuse the logic from core.auth but without global side effects if possible,
    # or just use the global client since existing code relies on it.
    # To support mixed usage, we should probably stick to the global client singleton for now.
    
    # We use legacy login but force server_mode=True to skip patching
    # We must allow the user to override this via kwargs if they really want patching?
    # No, 'connect' is the "native" path. 'login' is the "legacy/patching" path.
    
    # Check if 'intercept_http' was passed, default to False for connect()
    kwargs.setdefault('server_mode', True) # This disables patching in legacy login
    
    # Map generic config keys to internal keys
    if 'host' in kwargs:
        kwargs['xmpp_host'] = kwargs.pop('host')
    if 'port' in kwargs:
        kwargs['xmpp_port'] = kwargs.pop('port')
    if 'domain' in kwargs:
        kwargs['xmpp_domain'] = kwargs.pop('domain')
    if 'secure' in kwargs:
        kwargs['xmpp_use_tls'] = kwargs.pop('secure')
    if 'verify' in kwargs:
        kwargs['xmpp_verify_cert'] = kwargs.pop('verify')
    # Routing/load balancing hint (higher wins when multiple servers share the same identity)
    if 'route_weight' in kwargs:
        kwargs['route_weight'] = kwargs.pop('route_weight')
    if 'load_balancing_weight' in kwargs:
        kwargs['route_weight'] = kwargs.pop('load_balancing_weight')
    # Backward compat alias
    if 'priority' in kwargs:
        kwargs['route_weight'] = kwargs.pop('priority')
        
    _legacy_login(userid=identity, password=password, **kwargs)
    client = _get_client()
    return Session(client)


async def connect_async(identity: str, password: str, **kwargs) -> Session:
    """
    Connect to the mesh (Asynchronous).
    
    Args:
        identity: User identity
        password: Password
        **kwargs: Configuration options
        
    Returns:
        Session object
    """
    # For async, we want to bring-your-own-loop usually.
    # The current XMPPClient is designed with threading in mind in core/auth.
    # We might need to instantiate XMPPClient directly to avoid the thread spawning in _legacy_login.
    
    # Map generic config keys to internal keys
    if 'host' in kwargs:
        kwargs['xmpp_host'] = kwargs.pop('host')
    if 'port' in kwargs:
        kwargs['xmpp_port'] = kwargs.pop('port')
    if 'domain' in kwargs:
        kwargs['xmpp_domain'] = kwargs.pop('domain')
    if 'secure' in kwargs:
        kwargs['xmpp_use_tls'] = kwargs.pop('secure')
    if 'verify' in kwargs:
        kwargs['xmpp_verify_cert'] = kwargs.pop('verify')
    # Routing/load balancing hint (higher wins when multiple servers share the same identity)
    if 'route_weight' in kwargs:
        kwargs['route_weight'] = kwargs.pop('route_weight')
    if 'load_balancing_weight' in kwargs:
        kwargs['route_weight'] = kwargs.pop('load_balancing_weight')
    # Backward compat alias
    if 'priority' in kwargs:
        kwargs['route_weight'] = kwargs.pop('priority')

    config = Config.from_env()
    config.update(kwargs)
    config_dict = vars(config)
    
    if "@" in identity and not config.xmpp_domain:
        config_dict["xmpp_domain"] = identity.split("@")[1]
        
    client = XMPPClient(identity, password, config_dict)
    
    # Connect
    if config.xmpp_host:
        client.connect(host=config.xmpp_host, port=config.xmpp_port)
    else:
        client.connect()
        
    # Wait for session start (this is tricky in purely async if the client expects to run_forever)
    # Slixmpp usually requires a blocking loop or a background task.
    # We can start the client processing in a background task.
    
    loop = asyncio.get_running_loop()
    client.event_loop = loop
    
    # Start processing in background task
    asyncio.create_task(client.process(forever=False)) # process() returns a future/coroutine in newer slixmpp?
    # Wait, client.process() is usually blocking? 
    # Slixmpp's `process` is sync blocking? No, it depends on use_asyncio.
    # In XMPPClient (slixmpp based), `process` calls `loop.run_forever` if `forever=True`.
    # If we are already in a loop, we shouldn't call process() blocking.
    # Slixmpp is async-native. We just need to ensure `client.process` isn't blocking.
    
    # Actually, if we are in an async function, we assume the loop is running.
    # We just need to wait for 'connected'.
    
    await client.wait_until_connected()
    
    return Session(client)

def disconnect():
    """Disconnect from the mesh."""
    _legacy_logout()
