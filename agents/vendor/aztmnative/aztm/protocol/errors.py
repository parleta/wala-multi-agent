"""
Generic transport exceptions for AZTM.
Designed to avoid protocol-specific naming while preserving compatibility.
"""

from __future__ import annotations


class TransportError(Exception):
    """Base transport error (protocol-agnostic)."""


class TransportTimeout(TimeoutError, TransportError):
    """Timeout during transport operation.
    Subclasses TimeoutError for backward compatibility with existing code/tests.
    """


class TransportAuthError(PermissionError, TransportError):
    """Authentication failure on the transport."""


class TransportConnectionError(ConnectionError, TransportError):
    """Connection-level failure on the transport."""