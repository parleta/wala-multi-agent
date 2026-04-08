"""
JOSE Security Handler for AZTM

Implements JWS signing and JWE encryption for message security.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import jws, jwe, jwt
from jose.exceptions import JWTError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


@dataclass
class KeyPair:
    """RSA key pair for signing and encryption."""
    private_key: rsa.RSAPrivateKey
    public_key: rsa.RSAPublicKey
    key_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if key pair has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def export_public_key_pem(self) -> str:
        """Export public key in PEM format."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
    
    def export_private_key_pem(self, password: Optional[bytes] = None) -> str:
        """Export private key in PEM format."""
        encryption = serialization.NoEncryption()
        if password:
            encryption = serialization.BestAvailableEncryption(password)
        
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption
        ).decode('utf-8')


class JOSEHandler:
    """Handler for JOSE operations (JWS signing and JWE encryption)."""
    
    def __init__(self, key_size: int = 2048):
        """
        Initialize JOSE handler.
        
        Args:
            key_size: RSA key size in bits (default 2048)
        """
        self.key_size = key_size
        self.signing_keys: Dict[str, KeyPair] = {}
        self.encryption_keys: Dict[str, KeyPair] = {}
        self.trusted_keys: Dict[str, rsa.RSAPublicKey] = {}
        self.current_signing_key: Optional[str] = None
        self.current_encryption_key: Optional[str] = None
        
        # Generate initial keys
        self.rotate_keys()
    
    def generate_key_pair(self, key_id: str, expires_in: Optional[int] = None) -> KeyPair:
        """
        Generate a new RSA key pair.
        
        Args:
            key_id: Unique identifier for the key
            expires_in: Optional expiration time in seconds
        
        Returns:
            Generated KeyPair
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        created_at = datetime.now(timezone.utc)
        expires_at = None
        if expires_in:
            expires_at = created_at + timedelta(seconds=expires_in)
        
        logger.info(f"Generated new key pair: {key_id}")
        
        return KeyPair(
            private_key=private_key,
            public_key=public_key,
            key_id=key_id,
            created_at=created_at,
            expires_at=expires_at
        )
    
    def rotate_keys(self, expires_in: int = 86400) -> None:
        """
        Rotate signing and encryption keys.
        
        Args:
            expires_in: Expiration time for new keys in seconds (default 24 hours)
        """
        from uuid import uuid4
        
        # Generate new signing key
        signing_key_id = f"sign_{uuid4().hex[:8]}"
        signing_pair = self.generate_key_pair(signing_key_id, expires_in)
        self.signing_keys[signing_key_id] = signing_pair
        self.current_signing_key = signing_key_id
        
        # Generate new encryption key
        encryption_key_id = f"enc_{uuid4().hex[:8]}"
        encryption_pair = self.generate_key_pair(encryption_key_id, expires_in)
        self.encryption_keys[encryption_key_id] = encryption_pair
        self.current_encryption_key = encryption_key_id
        
        # Clean up expired keys
        self._cleanup_expired_keys()
        
        logger.info("Keys rotated successfully")
    
    def _cleanup_expired_keys(self) -> None:
        """Remove expired keys from storage."""
        # Keep at least one key of each type
        for key_store in [self.signing_keys, self.encryption_keys]:
            expired_keys = [
                kid for kid, kp in key_store.items()
                if kp.is_expired() and kid not in [
                    self.current_signing_key,
                    self.current_encryption_key
                ]
            ]
            for kid in expired_keys:
                del key_store[kid]
                logger.info(f"Removed expired key: {kid}")
    
    def sign_payload(self, payload: Dict[str, Any], algorithm: str = "RS256") -> str:
        """
        Sign a payload with JWS.
        
        Args:
            payload: Data to sign
            algorithm: Signing algorithm (default RS256)
        
        Returns:
            JWS compact serialization
        """
        if not self.current_signing_key:
            raise ValueError("No signing key available")
        
        key_pair = self.signing_keys[self.current_signing_key]
        
        # Add standard claims
        payload = {
            **payload,
            "iat": datetime.now(timezone.utc).timestamp(),
            "kid": self.current_signing_key
        }
        
        # Convert private key to PEM for python-jose
        private_pem = key_pair.export_private_key_pem()
        
        # Sign with JWS
        token = jws.sign(
            payload,
            private_pem,
            algorithm=algorithm,
            headers={"kid": self.current_signing_key}
        )
        
        logger.debug(f"Signed payload with key {self.current_signing_key}")
        return token
    
    def verify_signature(
        self,
        token: str,
        algorithms: list[str] = ["RS256"]
    ) -> Dict[str, Any]:
        """
        Verify a JWS signature.
        
        Args:
            token: JWS token to verify
            algorithms: Allowed algorithms
        
        Returns:
            Verified payload
        
        Raises:
            JWTError: If verification fails
        """
        # Extract key ID from header
        try:
            headers = jws.get_unverified_headers(token)
            kid = headers.get("kid")
        except Exception as e:
            raise JWTError(f"Invalid token format: {e}")
        
        # Find the public key
        public_key = None
        
        # Check signing keys first
        if kid and kid in self.signing_keys:
            public_key = self.signing_keys[kid].export_public_key_pem()
        # Check trusted external keys
        elif kid and kid in self.trusted_keys:
            public_key = self.trusted_keys[kid].public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
        else:
            raise JWTError(f"Unknown key ID: {kid}")
        
        # Verify signature
        try:
            payload = jws.verify(token, public_key, algorithms)
            logger.debug(f"Verified signature with key {kid}")
            return json.loads(payload)
        except Exception as e:
            raise JWTError(f"Signature verification failed: {e}")
    
    def encrypt_payload(
        self,
        payload: Dict[str, Any],
        recipient_key: Optional[str] = None,
        algorithm: str = "RSA-OAEP",
        encryption: str = "A256GCM"
    ) -> str:
        """
        Encrypt a payload with JWE.
        
        Args:
            payload: Data to encrypt
            recipient_key: Recipient's public key (PEM format)
            algorithm: Key encryption algorithm
            encryption: Content encryption algorithm
        
        Returns:
            JWE compact serialization
        """
        # Use recipient key if provided, otherwise use our own encryption key
        if recipient_key:
            public_key_pem = recipient_key
        elif self.current_encryption_key:
            key_pair = self.encryption_keys[self.current_encryption_key]
            public_key_pem = key_pair.export_public_key_pem()
        else:
            raise ValueError("No encryption key available")
        
        # Encrypt with JWE
        token = jwe.encrypt(
            json.dumps(payload).encode('utf-8'),
            public_key_pem,
            algorithm=algorithm,
            encryption=encryption,
            kid=self.current_encryption_key
        )
        
        logger.debug("Encrypted payload")
        return token.decode('utf-8') if isinstance(token, bytes) else token
    
    def decrypt_payload(self, token: str) -> Dict[str, Any]:
        """
        Decrypt a JWE payload.
        
        Args:
            token: JWE token to decrypt
        
        Returns:
            Decrypted payload
        
        Raises:
            JWTError: If decryption fails
        """
        # Try to decrypt with our encryption keys
        last_error = None
        
        for kid, key_pair in self.encryption_keys.items():
            try:
                private_pem = key_pair.export_private_key_pem()
                decrypted = jwe.decrypt(token.encode('utf-8'), private_pem)
                logger.debug(f"Decrypted payload with key {kid}")
                return json.loads(decrypted)
            except Exception as e:
                last_error = e
                continue
        
        raise JWTError(f"Decryption failed: {last_error}")
    
    def add_trusted_key(self, key_id: str, public_key_pem: str) -> None:
        """
        Add a trusted public key for signature verification.
        
        Args:
            key_id: Key identifier
            public_key_pem: Public key in PEM format
        """
        from cryptography.hazmat.primitives import serialization
        
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )
        
        self.trusted_keys[key_id] = public_key
        logger.info(f"Added trusted key: {key_id}")
    
    def create_signed_encrypted_message(
        self,
        payload: Dict[str, Any],
        recipient_key: Optional[str] = None
    ) -> str:
        """
        Create a message that is both signed and encrypted (JWS inside JWE).
        
        Args:
            payload: Data to protect
            recipient_key: Optional recipient's public key
        
        Returns:
            JWE token containing signed payload
        """
        # First sign the payload
        signed = self.sign_payload(payload)
        
        # Then encrypt the signed payload
        encrypted = self.encrypt_payload(
            {"jws": signed},
            recipient_key
        )
        
        return encrypted
    
    def verify_signed_encrypted_message(self, token: str) -> Dict[str, Any]:
        """
        Verify and decrypt a signed and encrypted message.
        
        Args:
            token: JWE token containing JWS
        
        Returns:
            Verified payload
        """
        # First decrypt
        decrypted = self.decrypt_payload(token)
        
        # Extract and verify the JWS
        if "jws" not in decrypted:
            raise JWTError("No signed payload in encrypted message")
        
        return self.verify_signature(decrypted["jws"])
    
    def export_public_keys(self) -> Dict[str, str]:
        """
        Export all public keys for sharing.
        
        Returns:
            Dictionary of key IDs to public keys in PEM format
        """
        keys = {}
        
        # Export signing keys
        for kid, key_pair in self.signing_keys.items():
            if not key_pair.is_expired():
                keys[kid] = key_pair.export_public_key_pem()
        
        # Export encryption keys
        for kid, key_pair in self.encryption_keys.items():
            if not key_pair.is_expired():
                keys[kid] = key_pair.export_public_key_pem()
        
        return keys