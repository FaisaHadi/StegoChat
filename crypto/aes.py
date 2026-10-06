"""Enkripsi dan dekripsi pesan dengan AES-256-GCM, termasuk pemeriksaan integritas."""

from __future__ import annotations

import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from stego.payload import AUTH_TAG_LENGTH, NONCE_LENGTH

AES_KEY_LENGTH = 32


def generate_nonce() -> bytes:
    """Buat nonce acak 12 byte sebagai masukan baru untuk setiap enkripsi GCM."""
    return secrets.token_bytes(NONCE_LENGTH)


def encrypt_gcm(
    plaintext_bytes: bytes, aes_key_bytes: bytes, nonce: bytes
) -> tuple[bytes, bytes]:
    """Enkripsi byte pesan dengan kunci AES 256 bit dan nonce.

    Hasil pustaka berisi ciphertext diikuti tag 16 byte; keduanya dipisahkan
    agar dapat disusun ke dalam format payload StegoChat.
    """
    _require_bytes("plaintext_bytes", plaintext_bytes)
    _validate_key(aes_key_bytes)
    _validate_nonce(nonce)

    # Pustaka menambahkan tag di akhir; tag dipakai untuk mendeteksi perubahan data.
    encrypted = AESGCM(aes_key_bytes).encrypt(nonce, plaintext_bytes, None)
    return encrypted[:-AUTH_TAG_LENGTH], encrypted[-AUTH_TAG_LENGTH:]


def decrypt_gcm(
    ciphertext: bytes, auth_tag: bytes, aes_key_bytes: bytes, nonce: bytes
) -> bytes:
    """Verifikasi tag GCM dan dekripsi ciphertext menjadi byte pesan asli.

    Jika autentikasi gagal, pustaka melempar InvalidTag dan tidak mengembalikan
    plaintext; pemanggil menangani kegagalan tersebut.
    """
    _require_bytes("ciphertext", ciphertext)
    _require_bytes("auth_tag", auth_tag)
    _validate_key(aes_key_bytes)
    _validate_nonce(nonce)

    if len(auth_tag) != AUTH_TAG_LENGTH:
        raise ValueError(f"auth_tag must be exactly {AUTH_TAG_LENGTH} bytes")

    return AESGCM(aes_key_bytes).decrypt(nonce, ciphertext + auth_tag, None)


def _validate_key(aes_key_bytes: bytes) -> None:
    """Pastikan kunci berupa bytes sepanjang 32 byte, sesuai AES-256."""
    _require_bytes("aes_key_bytes", aes_key_bytes)
    if len(aes_key_bytes) != AES_KEY_LENGTH:
        raise ValueError(f"aes_key_bytes must be exactly {AES_KEY_LENGTH} bytes")


def _validate_nonce(nonce: bytes) -> None:
    """Pastikan nonce berupa bytes sepanjang 12 byte, sesuai format proyek."""
    _require_bytes("nonce", nonce)
    if len(nonce) != NONCE_LENGTH:
        raise ValueError(f"nonce must be exactly {NONCE_LENGTH} bytes")


def _require_bytes(name: str, value: bytes) -> None:
    """Tolak masukan yang bukan bytes agar operasi kriptografi menerima tipe tepat."""
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
