"""Pembentukan kunci AES dari stego-key menggunakan PBKDF2-HMAC-SHA256."""

from __future__ import annotations

import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from crypto.aes import AES_KEY_LENGTH
from stego.payload import SALT_LENGTH

PBKDF2_ITERATIONS = 100_000


def generate_salt() -> bytes:
    """Buat salt acak 16 byte agar password yang sama dapat menghasilkan kunci baru."""
    return secrets.token_bytes(SALT_LENGTH)


def derive_aes_key(stego_key_bytes: bytes, salt: bytes) -> bytes:
    """Turunkan kunci AES 32 byte dari password dalam bytes dan salt 16 byte.

    PBKDF2-HMAC-SHA256 memakai 100.000 iterasi untuk memperlambat percobaan
    password. Password dan salt yang sama menghasilkan kunci yang sama.
    """
    _require_bytes("stego_key_bytes", stego_key_bytes)
    _require_bytes("salt", salt)

    if len(salt) != SALT_LENGTH:
        raise ValueError(f"salt must be exactly {SALT_LENGTH} bytes")

    # Salt disimpan di header; password tetap diperlukan untuk membentuk ulang kunci.
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(stego_key_bytes)


def _require_bytes(name: str, value: bytes) -> None:
    """Pastikan password dan salt berupa bytes sebelum diproses PBKDF2."""
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
