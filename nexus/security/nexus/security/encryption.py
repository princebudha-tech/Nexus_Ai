"""At-rest encryption using Fernet, with no-op fallback for dev."""
from __future__ import annotations

import os
from typing import Protocol

from nexus.core.exceptions import ConfigurationError


class EncryptionProvider(Protocol):
    def encrypt(self, plaintext: str) -> bytes:
        ...

    def decrypt(self, ciphertext: bytes) -> str:
        ...


class FernetEncryptionProvider:
    def __init__(self, key: bytes | None = None) -> None:
        from cryptography.fernet import Fernet

        if key is None:
            key = Fernet.generate_key()
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        return self._fernet.decrypt(ciphertext).decode("utf-8")


class NullEncryptionProvider:
    def encrypt(self, plaintext: str) -> bytes:
        return plaintext.encode("utf-8")

    def decrypt(self, ciphertext: bytes) -> str:
        return ciphertext.decode("utf-8")


def build_encryption_provider(env: str, key_env_var: str = "NEXUS_ENCRYPTION_KEY") -> EncryptionProvider:
    """
    Factory: in production, key must be set; otherwise fallback to Null.
    """
    if env == "production":
        key = os.environ.get(key_env_var)
        if not key:
            raise ConfigurationError(f"Environment variable {key_env_var} must be set in production")
        try:
            from cryptography.fernet import Fernet
            # Validate key format
            Fernet(key)
        except ImportError:
            raise ConfigurationError("cryptography library is required for production encryption")
        except Exception as exc:
            raise ConfigurationError(f"Invalid encryption key: {exc}")
        return FernetEncryptionProvider(key.encode())
    else:
        return NullEncryptionProvider()