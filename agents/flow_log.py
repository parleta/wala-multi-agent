from __future__ import annotations

import json
import os
from urllib.parse import urlparse


_AZTM_DEBUG_PREFIXES = (
    "DEBUG: Message keys:",
    "DEBUG: Message body:",
    "DEBUG: Message body type:",
)


def install_aztm_print_filter() -> None:
    import builtins

    if getattr(builtins, "_wala_print_filter_installed", False):
        return

    original_print = builtins.print

    def filtered_print(*args, **kwargs):
        if args and isinstance(args[0], str) and args[0].startswith(_AZTM_DEBUG_PREFIXES):
            return
        return original_print(*args, **kwargs)

    builtins.print = filtered_print
    setattr(builtins, "_wala_print_filter_installed", True)


def flow_log(
    *,
    sender: str,
    destination: str,
    transport: str,
    path: str,
    phase: str = "",
    request_id: str = "",
    corr: str = "",
    status: str = "",
    extra: str = "",
) -> None:
    # Keep runtime logs minimal and readable: only the routing essentials.
    print(
        f"[FLOW] sender={sender} destination={destination} transport={transport}",
        flush=True,
    )


def _load_service_map() -> dict[str, str]:
    raw = (os.getenv("SERVICE_MAP") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def outbound_transport_for_url(url: str) -> str:
    service_map = _load_service_map()
    key = urlparse(url).netloc
    return "xmpp" if key in service_map else "http"


def service_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname:
        return parsed.hostname
    return parsed.netloc or url


def request_transport(request) -> str:
    return "xmpp" if request.headers.get("x-aztm-from-jid") else "http"


def request_sender(request, fallback_sender: str) -> str:
    return request.headers.get("x-aztm-from-jid") or fallback_sender


def request_correlation_id(request) -> str:
    return request.headers.get("x-aztm-correlation-id", "")
