"""
URL to JID mapping utilities for AZTM
Handles conversion between HTTP URLs and XMPP addresses
"""

from typing import Tuple, Optional
from urllib.parse import urlparse, unquote
import logging

logger = logging.getLogger(__name__)


def url_to_jid(url: str, client_jid: str) -> str:
    """
    Convert URL host to XMPP JID

    Args:
        url: Full URL (e.g., "https://orders.api/path")
        client_jid: Client's JID to extract domain

    Returns:
        Target JID (e.g., "orders.api@xmpp.example")
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or parsed.netloc

    # Extract domain from client JID
    if "@" in client_jid:
        domain = client_jid.split("@")[1]
    else:
        raise ValueError(f"Invalid client JID: {client_jid}")

    # Build target JID
    target_jid = f"{hostname}@{domain}"
    logger.debug(f"Mapped URL host {hostname} to JID {target_jid}")

    return target_jid


def path_to_subject(path: str, query: str = "") -> str:
    """
    Convert URL path to XMPP message subject

    Args:
        path: URL path (e.g., "/orders/create")
        query: Query string (ignored for subject)

    Returns:
        Message subject (e.g., "orders/create")
    """
    # URL decode the path
    path = unquote(path)

    # Remove leading slash
    if path.startswith("/"):
        path = path[1:]

    # Handle root path
    if not path or path == "/":
        return "root"

    # Remove query string if accidentally included
    if "?" in path:
        path = path.split("?")[0]

    logger.debug(f"Mapped path /{path} to subject '{path}'")
    return path


def parse_url_components(url: str, client_jid: str) -> Tuple[str, str, str, str]:
    """
    Parse URL into components needed for XMPP routing

    Args:
        url: Full URL
        client_jid: Client's JID

    Returns:
        Tuple of (target_jid, subject, path, query)
    """
    parsed = urlparse(url)

    target_jid = url_to_jid(url, client_jid)
    subject = path_to_subject(parsed.path, parsed.query or "")

    return target_jid, subject, parsed.path, parsed.query or ""


def jid_to_host(jid: str) -> str:
    """
    Convert JID back to hostname

    Args:
        jid: XMPP JID (e.g., "orders.api@xmpp.example")

    Returns:
        Hostname (e.g., "orders.api")
    """
    if "@" in jid:
        return jid.split("@")[0]
    return jid


def subject_to_path(subject: str) -> str:
    """
    Convert XMPP subject back to URL path

    Args:
        subject: Message subject (e.g., "orders/create")

    Returns:
        URL path (e.g., "/orders/create")
    """
    if subject == "root":
        return "/"

    # Ensure leading slash
    if not subject.startswith("/"):
        return f"/{subject}"

    return subject
