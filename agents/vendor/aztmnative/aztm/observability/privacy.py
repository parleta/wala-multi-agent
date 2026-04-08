"""
Privacy redaction utilities for AZTM logging and exceptions.
Ensures user-visible output does not reveal underlying transport (xmpp/slixmpp/JIDs/domains).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Iterable, Pattern


BANNED_TOKEN_PATTERNS: list[tuple[Pattern[str], str]] = [
    # Protocols/libs
    (re.compile(r"\bxmpp\b", re.IGNORECASE), "transport"),
    (re.compile(r"\bslixmpp\b", re.IGNORECASE), "transport-lib"),
    (re.compile(r"\bstanza\b", re.IGNORECASE), "message"),
    (re.compile(r"\biq\b", re.IGNORECASE), "message"),
    (re.compile(r"\bpresence\b", re.IGNORECASE), "signal"),
    # Servers/domains commonly used in examples/tests
    (re.compile(r"\bopenfire\b", re.IGNORECASE), "server"),
    (re.compile(r"\bejabberd\b", re.IGNORECASE), "server"),
    (re.compile(r"\bsure\.im\b", re.IGNORECASE), "mesh.local"),
    # Identity terms
    (re.compile(r"\bjid\b", re.IGNORECASE), "identity"),
    # Email-like identities (user@domain) and JIDs
    (re.compile(r"\b[\w\.-]+@[\w\.-]+\b"), "[identity]"),
]


def _redact_text(text: str, patterns: Iterable[tuple[Pattern[str], str]]) -> str:
    redacted = text
    for pat, repl in patterns:
        redacted = pat.sub(repl, redacted)
    return redacted


class PrivacyRedactor(logging.Filter):
    """Logging filter that redacts sensitive transport details in log messages."""

    def __init__(self, privacy_mode: bool = True, internal_debug: bool = False):
        super().__init__()
        self.privacy_mode = privacy_mode
        self.internal_debug = internal_debug

    def filter(self, record: logging.LogRecord) -> bool:
        # If privacy disabled or developer debug enabled, pass through unchanged
        if not self.privacy_mode or self.internal_debug:
            return True

        try:
            msg = record.getMessage()
            sanitized = _redact_text(msg, BANNED_TOKEN_PATTERNS)
            # Replace the message and clear args to avoid re-formatting
            record.msg = sanitized
            record.args = ()
        except Exception:
            # Fail open on any issues to avoid breaking logging
            pass
        return True


def configure_privacy_from_env() -> None:
    """Configure the AZTM logger with privacy redaction using environment defaults.

    AZTM_PRIVACY_MODE: 1/true/on to enable (default: 1)
    AZTM_INTERNAL_DEBUG: 1/true/on to disable redaction for developers (default: 0)
    """
    env = os.environ
    privacy_mode = str(env.get("AZTM_PRIVACY_MODE", "1")).lower() in ("1", "true", "yes", "on")
    internal_debug = str(env.get("AZTM_INTERNAL_DEBUG", "0")).lower() in ("1", "true", "yes", "on")
    _apply_privacy_filter(privacy_mode=privacy_mode, internal_debug=internal_debug)


def configure_privacy_logging(*, privacy_mode: bool = True, internal_debug: bool = False) -> None:
    """Configure the AZTM logger with explicit settings (from Config)."""
    _apply_privacy_filter(privacy_mode=privacy_mode, internal_debug=internal_debug)


def _apply_privacy_filter(*, privacy_mode: bool, internal_debug: bool) -> None:
    aztm_logger = logging.getLogger("aztm")
    # Ensure the logger exists and is a parent for all AZTM modules
    aztm_logger.propagate = True
    # Avoid duplicate filters on reconfiguration for AZTM logger
    for f in list(aztm_logger.filters):
        if isinstance(f, PrivacyRedactor):
            aztm_logger.removeFilter(f)
    aztm_logger.addFilter(PrivacyRedactor(privacy_mode=privacy_mode, internal_debug=internal_debug))

    # Also attach the filter to the root logger to catch propagated records
    root_logger = logging.getLogger()
    for f in list(root_logger.filters):
        if isinstance(f, PrivacyRedactor):
            root_logger.removeFilter(f)
    root_logger.addFilter(PrivacyRedactor(privacy_mode=privacy_mode, internal_debug=internal_debug))

    # Attach filter to existing handlers to sanitize at formatting time
    for logger in (aztm_logger, root_logger):
        for h in list(logger.handlers):
            # Remove existing PrivacyRedactor filters to avoid duplicates
            if hasattr(h, "filters"):
                for f in list(h.filters):
                    if isinstance(f, PrivacyRedactor):
                        h.removeFilter(f)
                h.addFilter(PrivacyRedactor(privacy_mode=privacy_mode, internal_debug=internal_debug))
