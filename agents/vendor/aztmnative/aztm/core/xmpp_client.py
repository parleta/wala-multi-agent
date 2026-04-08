"""
XMPP Client implementation for AZTM
Handles connection lifecycle, messaging, and reconnection
"""

import asyncio
import logging
import time
import uuid
from typing import Optional, Dict, Any, Callable, Coroutine
from collections import defaultdict

import slixmpp
from slixmpp.exceptions import IqError, IqTimeout, XMPPError
from aztm.protocol.errors import TransportTimeout, TransportError, TransportConnectionError

logger = logging.getLogger(__name__)


class XMPPClient(slixmpp.ClientXMPP):
    """
    XMPP Client wrapper for AZTM
    Provides connection management, message handling, and automatic reconnection
    """

    def __init__(self, jid: str, password: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize XMPP client

        Args:
            jid: Jabber ID (user@domain)
            password: Authentication password
            config: Optional configuration dictionary
        """
        super().__init__(jid, password)

        self.config = config or {}
        self.connected = asyncio.Event()
        self.connecting = False
        self.disconnecting = False
        self.event_loop = None  # Will be set when connected
        # Keep reconnect enabled by default, but avoid reconnect storms.
        self.auto_reconnect = bool(self.config.get("auto_reconnect", True))

        # Reconnection settings
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = self.config.get("max_retries", 10)
        self.reconnect_base_delay = self.config.get("retry_backoff_ms", 1000) / 1000

        # Message handlers
        self._message_handlers: Dict[str, Callable] = {}
        self._response_futures: Dict[str, asyncio.Future] = {}
        self._iq_handlers: Dict[str, Callable] = {}

        # Connection pool for multiple JIDs (future feature)
        self._connection_pool: Dict[str, "XMPPClient"] = {}

        # Register event handlers
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("disconnected", self.on_disconnected)
        self.add_event_handler("message", self.on_message)
        self.add_event_handler("connection_failed", self.on_connection_failed)

        # Configure SSL/TLS
        if self.config.get("xmpp_use_tls", True):
            self.use_tls = True
            self.ca_certs = self.config.get("ca_certs")
            if not self.config.get("xmpp_verify_cert", True):
                self.disable_starttls = False
                import ssl

                self.ssl_context = ssl.create_default_context()
                self.ssl_context.check_hostname = False
                self.ssl_context.verify_mode = ssl.CERT_NONE

        # Register plugins
        self.register_plugin("xep_0030")  # Service Discovery
        self.register_plugin("xep_0199")  # XMPP Ping
        self.register_plugin("xep_0045")  # Multi-User Chat
        
        # Try to register HTTP File Upload plugin (requires aiohttp)
        try:
            self.register_plugin("xep_0363")  # HTTP File Upload
            logger.debug("XEP-0363 (HTTP File Upload) plugin loaded")
        except Exception as e:
            logger.debug(f"XEP-0363 not available (optional): {e}")

    def _start_keepalive(self, event: Any) -> None:
        """
        Start whitespace keepalive safely.

        Slixmpp may call this during reconnect races before disconnected cleanup
        runs, which can raise duplicate schedule ValueError and destabilize the
        reconnect loop.
        """
        try:
            self.cancel_schedule("Whitespace Keepalive")
        except Exception:
            pass

        try:
            super()._start_keepalive(event)
        except ValueError as exc:
            if "Whitespace Keepalive" in str(exc):
                logger.debug("Whitespace keepalive already scheduled; skipping duplicate")
            else:
                raise

    def session_start(self, event):
        """Handle successful session start - NOT async per slixmpp docs"""
        logger.info("Transport session started")

        # Store the event loop we're running in
        try:
            self.event_loop = asyncio.get_running_loop()
        except RuntimeError:
            self.event_loop = asyncio.get_event_loop()

        # Announce availability with an optional routing weight to prefer this endpoint
        # when multiple endpoints are connected under the same identity.
        try:
            weight = int(self.config.get("route_weight", 0))
        except Exception:
            weight = 0
        self.send_presence(ppriority=weight)
        
        # Get roster - don't await, just call it
        self.get_roster()

        # Reset reconnection counter
        self.reconnect_attempts = 0
        self.connecting = False
        self.connected.set()

        logger.info("Connected to messaging service")

    async def on_disconnected(self, event):
        """Handle disconnection"""
        self.connected.clear()

        if not self.auto_reconnect:
            logger.info("Transport disconnected (auto-reconnect disabled)")
            return

        if not self.disconnecting and not self.connecting:
            logger.warning("Unexpected disconnection, attempting reconnection...")
            await self._reconnect_with_backoff()

    async def on_connection_failed(self, event):
        """Handle connection failure"""
        logger.error(f"Connection failed: {event}")

        if not self.auto_reconnect:
            return

        # Ignore transient failures once a working session already exists.
        if self.connected.is_set():
            logger.debug("Ignoring connection_failed event because session is already active")
            return

        if not self.disconnecting and not self.connecting:
            await self._reconnect_with_backoff()

    async def on_message(self, msg):
        """Handle incoming messages"""
        msg_from = msg["from"].bare
        msg_subject = msg.get("subject", "")
        msg_body = msg["body"]
        msg_id = msg.get("id", "")

        logger.info(f"📨 Received message from {msg_from}: subject={msg_subject}, id={msg_id}")
        logger.info(f"   Pending futures: {list(self._response_futures.keys())}")

        # Check if this is a response to a pending request
        if msg_id and msg_id in self._response_futures:
            logger.info(f"   ✅ Found matching future for ID {msg_id}")
            future = self._response_futures.pop(msg_id)
            if not future.done():
                future.set_result(
                    {"from": msg_from, "subject": msg_subject, "body": msg_body, "id": msg_id}
                )
            return

        # Route to registered handlers
        # First try exact subject match
        if msg_subject in self._message_handlers:
            handler = self._message_handlers[msg_subject]
            asyncio.create_task(self._safe_handler_call(handler, msg))
        # Then try wildcard handler
        elif "*" in self._message_handlers:
            handler = self._message_handlers["*"]
            asyncio.create_task(self._safe_handler_call(handler, msg))

    async def _safe_handler_call(self, handler: Callable, msg):
        """Safely call a message handler"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(msg)
            else:
                handler(msg)
        except Exception as e:
            logger.error(f"Error in message handler: {e}", exc_info=True)

    async def _reconnect_with_backoff(self):
        """Implement exponential backoff reconnection"""
        if not self.auto_reconnect:
            return

        if self.connecting or self.disconnecting or self.connected.is_set():
            return

        self.connecting = True

        while self.reconnect_attempts < self.max_reconnect_attempts:
            if self.disconnecting or self.connected.is_set():
                self.connecting = False
                return

            self.reconnect_attempts += 1

            # Calculate backoff delay with jitter
            delay = min(
                self.reconnect_base_delay * (2 ** (self.reconnect_attempts - 1)),
                60,  # Max 60 seconds
            )
            # Add jitter (±20%)
            import random

            delay *= 0.8 + random.random() * 0.4

            logger.info(
                f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay:.1f}s"
            )
            await asyncio.sleep(delay)

            # Connection may have been restored while sleeping.
            if self.disconnecting or self.connected.is_set():
                self.connecting = False
                return

            try:
                # Attempt reconnection
                host = self.config.get("xmpp_host")
                port = self.config.get("xmpp_port")
                if host:
                    connected = self.connect(host=host, port=port)
                else:
                    connected = self.connect()

                if connected:
                    logger.info("Reconnection successful")
                    break
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")

        self.connecting = False

        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Maximum reconnection attempts reached, giving up")

    def register_message_handler(self, subject: str, handler: Callable):
        """
        Register a message handler for a specific subject

        Args:
            subject: Message subject to handle ('*' for wildcard)
            handler: Callback function
        """
        self._message_handlers[subject] = handler
        logger.debug(f"Registered handler for subject: {subject}")

    def unregister_message_handler(self, subject: str):
        """Unregister a message handler"""
        if subject in self._message_handlers:
            del self._message_handlers[subject]
            logger.debug(f"Unregistered handler for subject: {subject}")

    async def send_http_over_xmpp(
        self, to_jid: str, subject: str, body: str, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Send HTTP request over XMPP and wait for response

        Args:
            to_jid: Recipient JID
            subject: Message subject (HTTP path)
            body: Message body (JSON envelope)
            timeout: Optional timeout in seconds

        Returns:
            Response dictionary
        """
        msg_id = str(uuid.uuid4())
        timeout = timeout or self.config.get("xmpp_timeout", 30.0)

        # Create future for response
        future = asyncio.Future()
        self._response_futures[msg_id] = future

        # Send message
        msg = self.make_message(mto=to_jid, mbody=body, msubject=subject, mtype="chat")
        msg['id'] = msg_id
        msg.send()

        logger.info(f"📤 Sent message to {to_jid}: subject={subject}, id={msg_id}")

        try:
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            # Clean up future
            self._response_futures.pop(msg_id, None)
            raise TransportTimeout(f"No response received within {timeout}s")
        except Exception as e:
            # Clean up future
            self._response_futures.pop(msg_id, None)
            raise

    async def wait_until_connected(self, timeout: Optional[float] = None):
        """Wait until connected to XMPP server"""
        timeout = timeout or self.config.get("xmpp_timeout", 30.0)
        try:
            await asyncio.wait_for(self.connected.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TransportTimeout(f"Failed to establish transport session within {timeout}s")

    def disconnect(self):
        """Disconnect from XMPP server"""
        self.disconnecting = True
        super().disconnect()
        self.connected.clear()

    async def upload_slot_request(
        self, filename: str, size: int, content_type: str = "application/octet-stream"
    ) -> Dict[str, str]:
        """
        Request an HTTP upload slot (XEP-0363)

        Args:
            filename: Name of the file
            size: Size in bytes
            content_type: MIME type

        Returns:
            Dictionary with 'put' and 'get' URLs
        """
        if "xep_0363" not in self.plugin:
            raise RuntimeError("HTTP File Upload plugin not available")

        try:
            slot = await self.plugin["xep_0363"].upload_file(
                filename=filename, size=size, content_type=content_type, domain=self.boundjid.domain
            )
            return {"put": slot["put"], "get": slot["get"]}
        except IqTimeout as e:
            logger.error(f"Failed to request upload slot: timeout")
            raise TransportTimeout("Upload slot request timed out") from e
        except IqError as e:
            logger.error("Failed to request upload slot: error")
            raise TransportError("Upload slot request failed") from e
