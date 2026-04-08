"""
Wire protocol message format for AZTM
Defines JSON envelope structure for HTTP over XMPP
"""

import json
import uuid
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

# Protocol version
PROTOCOL_VERSION = "1.0"
PROTOCOL_NAMESPACE = "urn:aztm:v1"


@dataclass
class AztmRequest:
    """AZTM request message structure"""

    method: str
    path: str
    query: str = ""
    headers: Dict[str, str] = None
    body: Any = None
    corr: str = None
    ts: int = None
    ns: str = PROTOCOL_NAMESPACE
    version: str = PROTOCOL_VERSION

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.corr is None:
            self.corr = str(uuid.uuid4())
        if self.ts is None:
            self.ts = int(time.time())


@dataclass
class AztmResponse:
    """AZTM response message structure"""

    status: int
    headers: Dict[str, str] = None
    body: Any = None
    corr: str = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


def create_request_envelope(
    method: str,
    path: str,
    query: str = "",
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    corr: Optional[str] = None,
) -> str:
    """
    Create AZTM request envelope

    Args:
        method: HTTP method (GET, POST, etc.)
        path: URL path
        query: Query string
        headers: HTTP headers
        body: Request body
        corr: Correlation ID (auto-generated if not provided)

    Returns:
        JSON string of the envelope
    """
    request = AztmRequest(
        method=method.upper(), path=path, query=query, headers=headers or {}, body=body, corr=corr
    )

    envelope = {
        "_aztm": {
            "ns": request.ns,
            "version": request.version,
            "method": request.method,
            "path": request.path,
            "query": request.query,
            "headers": request.headers,
            "corr": request.corr,
            "ts": request.ts,
        },
        "payload": request.body,
    }

    logger.debug(f"Created request envelope: method={method}, path={path}, corr={request.corr}")
    return json.dumps(envelope, separators=(",", ":"))


def create_response_envelope(
    status: int,
    headers: Optional[Dict[str, str]] = None,
    body: Any = None,
    corr: Optional[str] = None,
    error: Optional[str] = None,
) -> str:
    """
    Create AZTM response envelope

    Args:
        status: HTTP status code
        headers: Response headers
        body: Response body
        corr: Correlation ID from request
        error: Error message if any

    Returns:
        JSON string of the envelope
    """
    response = AztmResponse(status=status, headers=headers or {}, body=body, corr=corr, error=error)

    envelope = {
        "_aztm": {
            "status": response.status,
            "headers": response.headers,
            "corr": response.corr,
        },
        "payload": response.body,
    }

    if error:
        envelope["_aztm"]["error"] = error

    logger.debug(f"Created response envelope: status={status}, corr={corr}")
    return json.dumps(envelope, separators=(",", ":"))


def parse_request_envelope(json_str: str) -> Dict[str, Any]:
    """
    Parse AZTM request envelope from JSON

    Args:
        json_str: JSON string

    Returns:
        Parsed envelope dictionary

    Raises:
        ValueError: If envelope is invalid
    """
    try:
        envelope = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in envelope: {e}")

    if "_aztm" not in envelope:
        raise ValueError("Missing '_aztm' control block in envelope")

    aztm = envelope["_aztm"]

    # Validate required fields
    required = ["method", "path", "corr"]
    for field in required:
        if field not in aztm:
            raise ValueError(f"Missing required field '{field}' in _aztm block")

    return envelope


def parse_response_envelope(json_str: str) -> Dict[str, Any]:
    """
    Parse AZTM response envelope from JSON

    Args:
        json_str: JSON string

    Returns:
        Parsed envelope dictionary

    Raises:
        ValueError: If envelope is invalid
    """
    try:
        envelope = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in envelope: {e}")

    if "_aztm" not in envelope:
        raise ValueError("Missing '_aztm' control block in envelope")

    aztm = envelope["_aztm"]

    # Validate required fields
    if "status" not in aztm:
        raise ValueError("Missing required field 'status' in _aztm block")

    return envelope


def validate_envelope(envelope: Dict[str, Any], is_request: bool = True) -> List[str]:
    """
    Validate an envelope structure

    Args:
        envelope: Parsed envelope dictionary
        is_request: True for request, False for response

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if "_aztm" not in envelope:
        errors.append("Missing '_aztm' control block")
        return errors

    aztm = envelope["_aztm"]

    if is_request:
        # Validate request
        required = ["method", "path", "corr"]
        for field in required:
            if field not in aztm:
                errors.append(f"Missing required field '{field}'")

        if "method" in aztm and aztm["method"] not in [
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            "HEAD",
            "OPTIONS",
        ]:
            errors.append(f"Invalid HTTP method: {aztm['method']}")
    else:
        # Validate response
        if "status" not in aztm:
            errors.append("Missing required field 'status'")
        elif not isinstance(aztm["status"], int) or aztm["status"] < 100 or aztm["status"] > 599:
            errors.append(f"Invalid HTTP status code: {aztm['status']}")

    return errors
