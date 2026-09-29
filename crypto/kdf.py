"""PBKDF2-HMAC-SHA256 key derivation for StegoChat V1."""

from __future__ import annotations

import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from crypto.aes import AES_KEY_LENGTH
from stego.payload import SALT_LENGTH

PBKDF2_ITERATIONS = 100_000


def generate_salt() -> bytes:
    """Return a fresh cryptographically secure V1 salt."""
    return secrets.token_bytes(SALT_LENGTH)


def derive_aes_key(stego_key_bytes: bytes, salt: bytes) -> bytes:
    """Derive a 32-byte AES-256 key from V1 secret bytes and salt.

    The caller owns the stable conversion of the user-provided stego key to
    bytes. The salt must be exactly 16 bytes as required by System Design V1.
    """
    _require_bytes("stego_key_bytes", stego_key_bytes)
    _require_bytes("salt", salt)

    if len(salt) != SALT_LENGTH:
        raise ValueError(f"salt must be exactly {SALT_LENGTH} bytes")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(stego_key_bytes)


def _require_bytes(name: str, value: bytes) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
