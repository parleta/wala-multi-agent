import json
import logging
import os
import time
from typing import Dict

import aztm

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_service_map() -> Dict[str, str]:
    raw = (os.getenv("SERVICE_MAP") or "").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid SERVICE_MAP JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("SERVICE_MAP must be a JSON object")

    normalized: Dict[str, str] = {}
    for key, value in parsed.items():
        normalized[str(key)] = str(value)
    return normalized


def login_aztm_from_env(*, server_mode: bool) -> None:
    jid = os.getenv("AZTM_JID")
    password = os.getenv("AZTM_PASSWORD")

    if not jid or not password:
        logger.warning("AZTM disabled: AZTM_JID/AZTM_PASSWORD not set")
        return

    host = os.getenv("AZTM_HOST", "xmpp")
    port = int(os.getenv("AZTM_PORT", "5222"))
    domain = os.getenv("AZTM_DOMAIN", "xmpp.local")
    xmpp_use_tls = _env_bool("AZTM_XMPP_USE_TLS", True)
    xmpp_verify_cert = _env_bool("AZTM_XMPP_VERIFY_CERT", False)
    xmpp_timeout = float(os.getenv("AZTM_XMPP_TIMEOUT", "30"))

    max_attempts = int(os.getenv("AZTM_LOGIN_MAX_ATTEMPTS", "60"))
    retry_sleep = float(os.getenv("AZTM_LOGIN_RETRY_SEC", "2"))

    service_map = _load_service_map()
    if service_map:
        aztm.register_service_mapping(service_map)
        logger.info("AZTM service mapping loaded: %s", list(service_map.keys()))

    for attempt in range(1, max_attempts + 1):
        try:
            aztm.login(
                userid=jid,
                password=password,
                server_mode=server_mode,
                host=host,
                port=port,
                domain=domain,
                xmpp_use_tls=xmpp_use_tls,
                xmpp_verify_cert=xmpp_verify_cert,
                xmpp_timeout=xmpp_timeout,
            )
            logger.info("AZTM login successful as %s (server_mode=%s)", jid, server_mode)
            return
        except Exception as exc:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"AZTM login failed after {max_attempts} attempts for {jid}"
                ) from exc

            logger.warning(
                "AZTM login attempt %s/%s failed for %s: %s; retrying in %.1fs",
                attempt,
                max_attempts,
                jid,
                exc,
                retry_sleep,
            )
            time.sleep(retry_sleep)
