"""
Configuration management for AZTM
Handles environment variables and configuration defaults
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class TransferMode(Enum):
    """Large transfer mode options"""

    AUTO = "auto"
    SLOT = "slot"
    INBAND = "inband"
    P2P = "p2p"


class ApprovalMode(Enum):
    """Approval modes for sensitive operations"""

    USER = "user"
    AUTO = "auto"
    AI = "ai"


@dataclass
class Config:
    """AZTM Configuration"""

    # Connection settings
    xmpp_host: Optional[str] = None
    xmpp_port: int = 5222
    xmpp_domain: Optional[str] = None
    xmpp_use_tls: bool = True
    xmpp_verify_cert: bool = True
    xmpp_timeout: float = 30.0

    # Size thresholds
    inline_limit_kb: int = 128
    stream_limit_mb: int = 5
    chunk_size_kb: int = 64

    # Transfer modes
    large_transfer_mode: TransferMode = TransferMode.AUTO
    large_transfer_fallback: TransferMode = TransferMode.INBAND

    # Features
    feature_upload_slots: bool = True
    feature_inband_stream: bool = True
    feature_peer_stream: bool = False
    feature_omemo: bool = False
    feature_jose: bool = False

    # Flow control
    stream_window: int = 8
    checksum_alg: str = "sha256"
    max_retries: int = 3
    retry_backoff_ms: int = 1000

    # Behavior
    empty_subject: str = "root"
    function_mapper: Optional[str] = None

    # Observability
    log_level: str = "INFO"
    metrics_enabled: bool = True
    tracing_enabled: bool = False

    # Privacy
    privacy_mode: bool = True
    internal_debug: bool = False

    # Security
    require_tls: bool = True
    min_tls_version: str = "1.2"
    allowed_ciphers: Optional[List[str]] = None

    # Connection pooling
    max_connections: int = 10
    connection_ttl: int = 3600
    keepalive_interval: int = 60

    # Routing
    # If multiple endpoints are connected under the same identity, the backend may route
    # traffic based on weight/bias. Higher values typically win.
    route_weight: int = 0

    # Approvals
    approval_mode: ApprovalMode = ApprovalMode.AUTO
    approval_timeout: int = 300

    # Extra settings
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls, prefix: str = "AZTM_") -> "Config":
        """Load configuration from environment variables"""
        config_dict = {}

        # Parse environment variables
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix) :].lower()

                # Handle special types
                if config_key == "large_transfer_mode":
                    config_dict[config_key] = TransferMode(value.lower())
                elif config_key == "large_transfer_fallback":
                    config_dict[config_key] = TransferMode(value.lower())
                elif config_key == "approval_mode":
                    config_dict[config_key] = ApprovalMode(value.lower())
                elif config_key.endswith("_kb") or config_key.endswith("_mb"):
                    config_dict[config_key] = int(value)
                elif config_key.startswith("feature_"):
                    config_dict[config_key] = value.lower() in ("1", "true", "yes", "on")
                elif config_key in (
                    "xmpp_port",
                    "stream_window",
                    "max_retries",
                    "retry_backoff_ms",
                    "max_connections",
                    "connection_ttl",
                    "keepalive_interval",
                    "approval_timeout",
                    "route_weight",
                    # Backward-compat alias (avoid documenting)
                    "presence_priority",
                ):
                    # Map legacy field name to new field
                    if config_key == "presence_priority":
                        config_dict["route_weight"] = int(value)
                    else:
                        config_dict[config_key] = int(value)
                elif config_key == "xmpp_timeout":
                    config_dict[config_key] = float(value)
                elif config_key in (
                    "xmpp_use_tls",
                    "xmpp_verify_cert",
                    "require_tls",
                    "metrics_enabled",
                    "tracing_enabled",
                    "privacy_mode",
                    "internal_debug",
                ):
                    config_dict[config_key] = value.lower() in ("1", "true", "yes", "on")
                else:
                    config_dict[config_key] = value

        # Also check non-prefixed common variables (legacy)
        if "XMPP_HOST" in os.environ:
            config_dict["xmpp_host"] = os.environ["XMPP_HOST"]
        if "XMPP_PORT" in os.environ:
            config_dict["xmpp_port"] = int(os.environ["XMPP_PORT"])
        if "XMPP_DOMAIN" in os.environ:
            config_dict["xmpp_domain"] = os.environ["XMPP_DOMAIN"]
            
        # Check generic AZTM variables (Native API friendly)
        if "AZTM_HOST" in os.environ:
            config_dict["xmpp_host"] = os.environ["AZTM_HOST"]
        if "AZTM_PORT" in os.environ:
            config_dict["xmpp_port"] = int(os.environ["AZTM_PORT"])
        if "AZTM_DOMAIN" in os.environ:
            config_dict["xmpp_domain"] = os.environ["AZTM_DOMAIN"]

        # Filter config_dict to only include valid fields
        import inspect
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_dict = {k: v for k, v in config_dict.items() if k in valid_fields}
        
        return cls(**filtered_dict)

    def update(self, updates: Dict[str, Any]) -> None:
        """Update configuration with dictionary"""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.extra[key] = value

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []

        if self.inline_limit_kb <= 0:
            errors.append("inline_limit_kb must be positive")

        if self.stream_limit_mb <= 0:
            errors.append("stream_limit_mb must be positive")

        if self.inline_limit_kb >= self.stream_limit_mb * 1024:
            errors.append("inline_limit_kb must be less than stream_limit_mb")

        if self.stream_window <= 0:
            errors.append("stream_window must be positive")

        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")

        if self.xmpp_port <= 0 or self.xmpp_port > 65535:
            errors.append("xmpp_port must be between 1 and 65535")

        if self.require_tls and not self.xmpp_use_tls:
            errors.append("require_tls is True but xmpp_use_tls is False")

        return errors
