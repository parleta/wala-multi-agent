"""
FastAPI server integration for AZTM
Auto-detects FastAPI apps and hooks them to receive HTTP via XMPP
"""

import sys
import json
import logging
import asyncio
from typing import Optional, Dict, Any, Callable
from dataclasses import asdict

logger = logging.getLogger(__name__)


def find_fastapi_app():
    """
    Auto-detect FastAPI application in current process

    Returns:
        FastAPI app instance or None
    """
    try:
        from fastapi import FastAPI
    except ImportError:
        logger.debug("FastAPI not installed")
        return None

    # Search through all modules for FastAPI instances
    # Make a copy of module names to avoid RuntimeError during iteration
    module_names = list(sys.modules.keys())
    for module_name in module_names:
        module = sys.modules.get(module_name)
        if module is None:
            continue

        # Skip built-in modules and internal modules
        if module_name.startswith("_") and module_name != "__main__":
            continue

        # Check module's global namespace
        try:
            if hasattr(module, "__dict__"):
                # Make a copy of the dict items to avoid iteration issues
                items = list(module.__dict__.items()) if hasattr(module.__dict__, "items") else []
                for name, obj in items:
                    if isinstance(obj, FastAPI):
                        logger.info(f"Found FastAPI app: {module_name}.{name}")
                        return obj
        except Exception as e:
            # Some modules might not allow iteration
            logger.debug(f"Could not check module {module_name}: {e}")
            continue

    logger.debug("No FastAPI app found")
    return None


def hook_fastapi(app, client, config):
    """
    Hook a FastAPI application to receive HTTP requests via XMPP

    Args:
        app: FastAPI application instance
        client: XMPP client
        config: Configuration object

    Returns:
        bool: True if successfully hooked
    """
    from aztm.protocol.message import parse_request_envelope, create_response_envelope
    from aztm.core.mapping import subject_to_path

    logger.info("Hooking FastAPI application for secure transport")

    async def handle_xmpp_request(msg):
        """Handle incoming XMPP message as HTTP request"""
        logger.info("🔵 FastAPI hook received inbound request")
        logger.info(f"   Type: {msg.get('type')}, Has body: {bool(msg.get('body'))}")
        
        # Debug: Print the entire message structure
        print(f"DEBUG: Message keys: {list(msg.keys())}")
        print(f"DEBUG: Message body: '{msg.get('body', 'NO BODY')}'")
        print(f"DEBUG: Message body type: {type(msg.get('body'))}")
        
        try:
            # Parse the XMPP message
            from_jid = msg["from"].bare
            subject = msg.get("subject", "")
            body = msg.get("body", "")
            if not body:
                print(f"WARNING: Empty body received from {from_jid}")
                return
            msg_id = msg.get("id", "")

            logger.debug(f"Handling request from {from_jid}: {subject}")

            # Parse request envelope
            envelope = parse_request_envelope(body)
            aztm = envelope["_aztm"]
            payload = envelope.get("payload")

            # Create a mock request
            from starlette.requests import Request
            from starlette.responses import Response, JSONResponse
            from io import BytesIO

            # Build ASGI scope
            path = aztm["path"]
            query_string = aztm.get("query", "").encode("utf-8")

            # Convert headers
            headers = []
            for key, value in aztm.get("headers", {}).items():
                headers.append((key.lower().encode(), value.encode()))

            # Add AZTM-specific headers
            headers.append((b"x-aztm-from-jid", from_jid.encode()))
            headers.append((b"x-aztm-correlation-id", aztm["corr"].encode()))

            # Build body
            if payload:
                if isinstance(payload, dict) or isinstance(payload, list):
                    body_bytes = json.dumps(payload).encode("utf-8")
                elif isinstance(payload, str):
                    body_bytes = payload.encode("utf-8")
                elif isinstance(payload, bytes):
                    body_bytes = payload
                else:
                    body_bytes = str(payload).encode("utf-8")
            else:
                body_bytes = b""

            # Create ASGI scope
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": aztm["method"],
                "scheme": "https",
                "path": path,
                "query_string": query_string,
                "headers": headers,
                "server": ("aztm.local", 443),
                "client": (from_jid, 0),
                "root_path": "",
            }

            # Create receive callable
            async def receive():
                return {
                    "type": "http.request",
                    "body": body_bytes,
                }

            # Create send callable to capture response
            response_data = {}

            async def send(message):
                if message["type"] == "http.response.start":
                    response_data["status"] = message["status"]
                    response_data["headers"] = {}
                    for header_name, header_value in message.get("headers", []):
                        response_data["headers"][header_name.decode()] = header_value.decode()
                elif message["type"] == "http.response.body":
                    body = message.get("body", b"")
                    if "body" not in response_data:
                        response_data["body"] = b""
                    response_data["body"] += body

            # Call the FastAPI app
            await app(scope, receive, send)

            # Parse response body
            response_body = response_data.get("body", b"")
            content_type = response_data.get("headers", {}).get("content-type", "")

            if "application/json" in content_type and response_body:
                try:
                    response_payload = json.loads(response_body.decode("utf-8"))
                except:
                    response_payload = response_body.decode("utf-8", errors="ignore")
            elif response_body:
                response_payload = response_body.decode("utf-8", errors="ignore")
            else:
                response_payload = None

            # Create response envelope
            response_envelope = create_response_envelope(
                status=response_data.get("status", 200),
                headers=response_data.get("headers", {}),
                body=response_payload,
                corr=aztm["corr"],
            )

            # Send response back via XMPP
            msg = client.make_message(
                mto=from_jid,
                mbody=response_envelope,
                msubject=f"{subject}:response",
                mtype="chat"
            )
            if msg_id:
                msg['id'] = msg_id  # Set message ID for correlation
            msg.send()

            logger.debug(f"Sent response: status={response_data.get('status', 200)}")

        except Exception as e:
            logger.error(f"Error handling transport request: {e}", exc_info=True)

            # Send error response
            try:
                error_envelope = create_response_envelope(
                    status=500,
                    headers={"Content-Type": "text/plain"},
                    body="Internal Server Error",
                    corr=aztm.get("corr") if "aztm" in locals() else None,
                    error=str(e),
                )

                error_msg = client.make_message(
                    mto=from_jid if "from_jid" in locals() else msg["from"].bare,
                    mbody=error_envelope,
                    msubject=f"{subject}:error" if "subject" in locals() else "error",
                    mtype="chat"
                )
                error_msg.send()
            except:
                logger.error("Failed to send error response", exc_info=True)

    # Register handler for all messages using XMPPClient's method
    # Use wildcard '*' to handle all message subjects
    if hasattr(client, 'register_message_handler'):
        client.register_message_handler('*', handle_xmpp_request)
        logger.info("FastAPI app hooked successfully using register_message_handler")
    elif hasattr(client, '_message_handlers'):
        # Direct access if method not available
        client._message_handlers['*'] = handle_xmpp_request
        logger.info("FastAPI app hooked successfully using direct handler registration")
    else:
        # Fallback to event handler (might not work if already connected)
        client.add_event_handler("message", handle_xmpp_request)
        logger.warning("FastAPI app hooked using add_event_handler - may not work properly")

    return True
