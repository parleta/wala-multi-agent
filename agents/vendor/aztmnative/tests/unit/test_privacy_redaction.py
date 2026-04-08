import logging
import os
import asyncio
import pytest

from aztm.observability.privacy import configure_privacy_from_env, configure_privacy_logging


def test_log_redaction_simple(caplog):
    # Ensure privacy is ON
    os.environ["AZTM_PRIVACY_MODE"] = "1"
    os.environ["AZTM_INTERNAL_DEBUG"] = "0"
    configure_privacy_from_env()

    logger = logging.getLogger("aztm.test")

    with caplog.at_level(logging.INFO, logger="aztm"):
        logger.info("Connecting to XMPP at openfire as user test@sure.im via slixmpp; JID=test@sure.im")

    combined = "\n".join(record.message for record in caplog.records if record.name.startswith("aztm"))

    # Banned tokens should not appear
    for token in ["xmpp", "slixmpp", "openfire", "sure.im", "jid", "@"]:
        assert token not in combined.lower()

    # Replacement hints should appear
    assert "transport" in combined.lower()
    assert "identity" in combined.lower() or "[identity]" in combined


@pytest.mark.asyncio
async def test_timeout_message_is_sanitized():
    # Build a minimal client instance without connecting
    from aztm.core.xmpp_client import XMPPClient

    client = XMPPClient("tester@example.com", "pass", config={"xmpp_timeout": 0.01})
    with pytest.raises(TimeoutError) as exc:
        await client.wait_until_connected(timeout=0.01)

    msg = str(exc.value)
    assert "xmpp" not in msg.lower()
    assert "transport" in msg.lower()
