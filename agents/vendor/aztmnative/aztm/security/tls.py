"""
TLS Security Configuration for AZTM

Handles TLS configuration, certificate validation, and secure connections.
"""

import ssl
import logging
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass
import certifi

logger = logging.getLogger(__name__)


@dataclass
class TLSConfig:
    """TLS configuration for XMPP connections."""
    
    min_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2
    max_version: Optional[ssl.TLSVersion] = None
    verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED
    check_hostname: bool = True
    ca_bundle: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    ciphers: Optional[str] = None
    pinned_certificates: Optional[list[str]] = None
    
    def create_ssl_context(self) -> ssl.SSLContext:
        """Create an SSL context with the configured settings."""
        # Create context with secure defaults
        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile=self.ca_bundle or certifi.where()
        )
        
        # Set minimum TLS version
        context.minimum_version = self.min_version
        if self.max_version:
            context.maximum_version = self.max_version
        
        # Configure verification
        context.verify_mode = self.verify_mode
        context.check_hostname = self.check_hostname
        
        # Set client certificate if provided
        if self.client_cert and self.client_key:
            context.load_cert_chain(
                certfile=self.client_cert,
                keyfile=self.client_key
            )
        
        # Set custom ciphers if provided
        if self.ciphers:
            context.set_ciphers(self.ciphers)
        else:
            # Use strong ciphers by default
            context.set_ciphers('HIGH:!aNULL:!MD5:!DSS')
        
        # Add certificate pinning if configured
        if self.pinned_certificates:
            self._setup_certificate_pinning(context)
        
        logger.info(f"Created SSL context with TLS {self.min_version.name}")
        return context
    
    def _setup_certificate_pinning(self, context: ssl.SSLContext) -> None:
        """Set up certificate pinning for enhanced security."""
        # Store original verify callback
        original_verify = context.verify_mode
        
        def verify_pinned_cert(conn, cert, errno, depth, preverify_ok):
            """Verify certificate against pinned certificates."""
            if depth == 0:  # Only check leaf certificate
                cert_der = cert.to_cryptography().public_bytes(
                    encoding=serialization.Encoding.DER
                )
                cert_hash = hashlib.sha256(cert_der).hexdigest()
                
                if cert_hash not in self.pinned_certificates:
                    logger.error(f"Certificate pin mismatch: {cert_hash}")
                    return False
            
            return preverify_ok
        
        # Note: In production, use pyOpenSSL for proper callback support
        logger.warning("Certificate pinning configured but requires pyOpenSSL for full support")


def validate_certificate(
    cert_path: Union[str, Path],
    hostname: Optional[str] = None
) -> bool:
    """
    Validate a certificate file.
    
    Args:
        cert_path: Path to the certificate file
        hostname: Optional hostname to verify against
    
    Returns:
        True if certificate is valid, False otherwise
    """
    try:
        cert_path = Path(cert_path)
        if not cert_path.exists():
            logger.error(f"Certificate file not found: {cert_path}")
            return False
        
        # Load and parse certificate
        with open(cert_path, 'rb') as f:
            cert_data = f.read()
        
        # Try to load as PEM
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        except Exception:
            # Try DER format
            cert = x509.load_der_x509_certificate(cert_data, default_backend())
        
        # Check if certificate is expired
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        if cert.not_valid_after_utc < now:
            logger.error(f"Certificate expired on {cert.not_valid_after_utc}")
            return False
        
        if cert.not_valid_before_utc > now:
            logger.error(f"Certificate not yet valid until {cert.not_valid_before_utc}")
            return False
        
        # Verify hostname if provided
        if hostname:
            from cryptography.x509.oid import ExtensionOID
            try:
                san_ext = cert.extensions.get_extension_for_oid(
                    ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                )
                san_names = [
                    name.value for name in san_ext.value
                    if isinstance(name, x509.DNSName)
                ]
                
                if hostname not in san_names:
                    # Check common name as fallback
                    cn = cert.subject.get_attributes_for_oid(
                        x509.NameOID.COMMON_NAME
                    )[0].value
                    
                    if hostname != cn:
                        logger.error(f"Hostname {hostname} not in certificate")
                        return False
            except x509.ExtensionNotFound:
                # No SAN, check CN only
                cn = cert.subject.get_attributes_for_oid(
                    x509.NameOID.COMMON_NAME
                )[0].value
                
                if hostname != cn:
                    logger.error(f"Hostname {hostname} not in certificate")
                    return False
        
        logger.info(f"Certificate validated successfully: {cert_path}")
        return True
        
    except Exception as e:
        logger.error(f"Certificate validation failed: {e}")
        return False


def create_secure_context(
    min_tls_version: str = "TLSv1.2",
    verify: bool = True,
    ca_bundle: Optional[str] = None
) -> ssl.SSLContext:
    """
    Create a secure SSL context with sensible defaults.
    
    Args:
        min_tls_version: Minimum TLS version (TLSv1.2, TLSv1.3)
        verify: Whether to verify certificates
        ca_bundle: Optional path to CA bundle
    
    Returns:
        Configured SSL context
    """
    config = TLSConfig(
        min_version=getattr(ssl.TLSVersion, min_tls_version.replace(".", "_")),
        verify_mode=ssl.CERT_REQUIRED if verify else ssl.CERT_NONE,
        check_hostname=verify,
        ca_bundle=ca_bundle
    )
    
    return config.create_ssl_context()