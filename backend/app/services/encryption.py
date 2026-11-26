import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet_key() -> bytes:
    """Derive a valid 32-byte url-safe base64 key from ENCRYPTION_KEY or SECRET_KEY."""
    key_src = getattr(settings, "ENCRYPTION_KEY", None) or settings.SECRET_KEY
    digest = hashlib.sha256(key_src.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token(plain_token: Optional[str]) -> Optional[str]:
    """Encrypt a plain text token string with Fernet."""
    if not plain_token:
        return None
    try:
        f = Fernet(_get_fernet_key())
        return f.encrypt(plain_token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        # Fallback or raise
        raise RuntimeError(f"Encryption failed: {e}") from e


def decrypt_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypt a Fernet encrypted token string."""
    if not encrypted_token:
        return None
    try:
        f = Fernet(_get_fernet_key())
        return f.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"Decryption failed: {e}") from e
