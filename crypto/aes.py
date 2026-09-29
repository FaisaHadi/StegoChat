"""AES-256-GCM encryption helpers for StegoChat V1."""

from __future__ import annotations

import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from stego.payload import AUTH_TAG_LENGTH, NONCE_LENGTH

AES_KEY_LENGTH = 32


def generate_nonce() -> bytes:
    """Return a fresh cryptographically secure V1 AES-GCM nonce."""
    return secrets.token_bytes(NONCE_LENGTH)


def encrypt_gcm(
    plaintext_bytes: bytes, aes_key_bytes: bytes, nonce: bytes
) -> tuple[bytes, bytes]:
    """Encrypt bytes with AES-256-GCM and return ciphertext and tag separately."""
    _require_bytes("plaintext_bytes", plaintext_bytes)
    _validate_key(aes_key_bytes)
    _validate_nonce(nonce)

    encrypted = AESGCM(aes_key_bytes).encrypt(nonce, plaintext_bytes, None)
    return encrypted[:-AUTH_TAG_LENGTH], encrypted[-AUTH_TAG_LENGTH:]


def decrypt_gcm(
    ciphertext: bytes, auth_tag: bytes, aes_key_bytes: bytes, nonce: bytes
) -> bytes:
    """Authenticate and decrypt AES-256-GCM data.

    ``InvalidTag`` from ``cryptography`` is intentionally allowed to propagate
    on failed authentication; plaintext is never returned in that case.
    """
    _require_bytes("ciphertext", ciphertext)
    _require_bytes("auth_tag", auth_tag)
    _validate_key(aes_key_bytes)
    _validate_nonce(nonce)

    if len(auth_tag) != AUTH_TAG_LENGTH:
        raise ValueError(f"auth_tag must be exactly {AUTH_TAG_LENGTH} bytes")

    return AESGCM(aes_key_bytes).decrypt(nonce, ciphertext + auth_tag, None)


def _validate_key(aes_key_bytes: bytes) -> None:
    _require_bytes("aes_key_bytes", aes_key_bytes)
    if len(aes_key_bytes) != AES_KEY_LENGTH:
        raise ValueError(f"aes_key_bytes must be exactly {AES_KEY_LENGTH} bytes")


def _validate_nonce(nonce: bytes) -> None:
    _require_bytes("nonce", nonce)
    if len(nonce) != NONCE_LENGTH:
        raise ValueError(f"nonce must be exactly {NONCE_LENGTH} bytes")


def _require_bytes(name: str, value: bytes) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
