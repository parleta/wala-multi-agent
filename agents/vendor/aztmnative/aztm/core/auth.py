"""
Working authentication module for AZTM based on slixmpp documentation
"""

import asyncio
import logging
import threading
import time
from typing import Optional
from dataclasses import asdict

from .xmpp_client import XMPPClient
from .config import Config

logger = logging.getLogger(__name__)

# Ensure privacy redaction can be configured during login
try:
    from aztm.observability.privacy import configure_privacy_logging
except Exception:  # pragma: no cover
    configure_privacy_logging = None  # type: ignore

# Global client instance
_client: Optional[XMPPClient] = None
_client_lock = threading.Lock()
_loop_thread: Optional[threading.Thread] = None


def login(userid: str, password: str, server_mode: bool = False, **kwargs) -> None:
    """
    Main entry point for AZTM initialization
    
    Args:
        userid: User ID (e.g. user@domain)
        password: Password
        server_mode: If True, only receives messages (doesn't patch HTTP libraries)
        **kwargs: Additional configuration options
    
    SIMPLE VERSION: Runs in main thread (blocks during initial connection)
    This follows the exact documentation pattern and is proven to work.
    
    TODO: See GitHub issue for threaded implementation
    """
    global _client, _loop_thread
    
    with _client_lock:
        if _client is not None:
            logger.warning("Already logged in, logging out first")
            logout()
        
        # Filter out credential-related kwargs that shouldn't go to Config
        credential_keys = {'server_password', 'server_jid', 'client_password', 'client_jid'}
        config_kwargs = {k: v for k, v in kwargs.items() if k not in credential_keys}
        
        # Map generic config keys to internal keys (for backward compatibility and ease of use)
        if 'host' in config_kwargs:
            config_kwargs['xmpp_host'] = config_kwargs.pop('host')
        if 'port' in config_kwargs:
            config_kwargs['xmpp_port'] = config_kwargs.pop('port')
        if 'domain' in config_kwargs:
            config_kwargs['xmpp_domain'] = config_kwargs.pop('domain')
        
        # Handle TLS mode if present
        if 'tls_mode' in config_kwargs:
            tls_mode = config_kwargs.pop('tls_mode')
            # 'direct' usually implies legacy SSL on a specific port (like 443 or 5223)
            # Slixmpp uses 'use_ssl' for legacy SSL and 'use_tls' for STARTTLS.
            # Config currently only exposes 'xmpp_use_tls'. 
            # If tls_mode is 'direct', we might need to set extra params or ensure Config supports it.
            # For now, we will assume 'direct' implies we want secure connection.
            if tls_mode == 'direct':
                config_kwargs['xmpp_use_tls'] = True
                # Ideally Config/XMPPClient should support 'use_ssl' explicitly.
                # Adding it to extra config which XMPPClient receives.
                config_kwargs['use_ssl'] = True
                # Disable STARTTLS if using direct SSL
                config_kwargs['use_tls'] = False 
            elif tls_mode == 'starttls':
                config_kwargs['xmpp_use_tls'] = True
                config_kwargs['use_ssl'] = False
            elif tls_mode == 'disable':
                config_kwargs['xmpp_use_tls'] = False
                config_kwargs['use_ssl'] = False

        # Load configuration
        config = Config.from_env()
        config.update(config_kwargs)
        
        # Validate configuration
        errors = config.validate()
        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")
        
        config_dict = asdict(config)

        # Apply privacy configuration based on Config
        if configure_privacy_logging is not None:
            try:
                configure_privacy_logging(
                    privacy_mode=bool(config.privacy_mode),
                    internal_debug=bool(config.internal_debug),
                )
            except Exception:
                pass
        
        # Extract domain if needed
        if "@" in userid and not config.xmpp_domain:
            config.xmpp_domain = userid.split("@")[1]
            config_dict["xmpp_domain"] = config.xmpp_domain
        
        # Create transport client
        logger.info(f"Initializing secure transport client for {userid}")
        _client = XMPPClient(userid, password, config_dict)
        
        # Connect (following exact connection pattern)
        logger.debug(f"Connecting secure transport for {userid}")
        if config.xmpp_host:
            logger.debug(f"Using host: {config.xmpp_host}:{config.xmpp_port}")
            _client.connect(host=config.xmpp_host, port=config.xmpp_port)
        else:
            logger.debug(f"Using DNS for domain: {userid.split('@')[1]}")
            _client.connect()
        
        # Run event loop briefly to establish connection
        logger.info("Establishing secure transport session (this may take a few seconds)...")
        loop = asyncio.get_event_loop()
        
        # Store the loop reference in the client
        _client.event_loop = loop
        
        # Run until connected or timeout
        start_time = time.time()
        while not _client.connected.is_set():
            if time.time() - start_time > config.xmpp_timeout:
                _cleanup()
                raise TimeoutError(f"Connection timeout after {config.xmpp_timeout}s")
            
            # Run the event loop for a short time to process connection
            loop.run_until_complete(asyncio.sleep(0.1))
        
        logger.info("Transport connected successfully")
        
        # Now run the event loop in a background thread
        def run_background_loop():
            """Keep the transport connection alive in background"""
            try:
                # The loop is already set up, just keep it running
                loop.run_forever()
            except Exception as e:
                logger.error(f"Background loop error: {e}")
        
        _loop_thread = threading.Thread(
            target=run_background_loop,
            daemon=True,
            name="AZTM-Background"
        )
        _loop_thread.start()
        
        # Patch HTTP libraries (only for clients, not servers)
        if not server_mode:
            # Check for intercept_http flag (passed from new login wrapper if any)
            # Or assume true if not present (legacy behavior)
            intercept_http = kwargs.get('intercept_http', True)
            
            if intercept_http:
                try:
                    from aztm.interceptors import patch_all
                    patch_all(_client, config)
                    logger.info("HTTP libraries patched for client mode")
                except ImportError as e:
                    logger.warning(f"Could not patch HTTP libraries: {e}")
            else:
                logger.info("HTTP interception disabled by configuration")
        else:
            logger.info("Server mode - HTTP libraries NOT patched")
        
        # Auto-hook FastAPI
        try:
            from aztm.server import auto_hook_fastapi
            if auto_hook_fastapi(_client, config):
                logger.info("FastAPI auto-hooked")
        except ImportError:
            pass


def logout():
    """Disconnect from transport server"""
    global _client, _loop_thread
    
    with _client_lock:
        if _client is None:
            return
        
        logger.info("Disconnecting transport")
        _cleanup()


def _cleanup():
    """Internal cleanup"""
    global _client, _loop_thread
    
    if _client:
        try:
            _client.disconnect()
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
        _client = None
    
    _loop_thread = None
    
    try:
        from aztm.interceptors import unpatch_all
        unpatch_all()
    except ImportError:
        pass


def get_client() -> XMPPClient:
    """Get current XMPP client"""
    if _client is None:
        raise RuntimeError("Not logged in. Call aztm.login() first")
    return _client


def get_jid() -> str:
    """Get current JID"""
    client = get_client()
    return str(client.boundjid)
