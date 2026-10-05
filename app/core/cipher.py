import hmac
import hashlib
import ipaddress
import socket
import time
from urllib.parse import urlparse
from cryptography.fernet import Fernet

from app.core.config import settings


class SecretCipher:
    """Fernet symmetric encryption for sensitive credentials and keys at rest."""

    def __init__(self, key: str | None = None) -> None:
        enc_key = key or settings.SECRET_ENCRYPTION_KEY
        if not enc_key:
            # Fallback for dev / unconfigured environments
            enc_key = Fernet.generate_key().decode()
        if isinstance(enc_key, str):
            enc_key = enc_key.encode("utf-8")
        self._fernet = Fernet(enc_key)

    def encrypt(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode("utf-8")).decode("utf-8")

    def decrypt(self, cipher_text: str) -> str:
        return self._fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")


def sign_webhook(secret: str, timestamp: int, body: bytes) -> str:
    """Produce sha256=<hex_digest> HMAC signature over <timestamp>.<raw_body>."""
    payload = f"{timestamp}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(
    secret: str,
    signature: str,
    timestamp: int,
    body: bytes,
    tolerance_seconds: int = 300,
) -> bool:
    """Verify HMAC-SHA256 signature with replay window validation."""
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance_seconds:
        return False

    expected_signature = sign_webhook(secret, timestamp, body)

    # Normalize if signature doesn't include 'sha256=' prefix
    if not signature.startswith("sha256="):
        expected_digest = expected_signature.split("=", 1)[1]
        return hmac.compare_digest(signature, expected_digest)

    return hmac.compare_digest(signature, expected_signature)


def validate_outbound_url(url: str) -> bool:
    """Validate external outbound URL against SSRF (blocks loopback, private IPs, and localhost)."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
            return False

        # Resolve hostname addresses
        addr_infos = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_infos:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)

            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False

        return True
    except Exception:
        return False
