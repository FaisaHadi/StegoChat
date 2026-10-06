"""Menghubungkan enkripsi AES-GCM dengan penyisipan dan ekstraksi LSB."""

from __future__ import annotations

from PIL import Image

from crypto.aes import decrypt_gcm, encrypt_gcm, generate_nonce
from crypto.kdf import derive_aes_key, generate_salt
from stego.lsb import embed_payload, extract_payload
from stego.payload import HEADER_SIZE, build_payload, parse_payload


def embed_plaintext(
    cover_rgb: Image.Image, plaintext: str, stego_key_bytes: bytes
) -> Image.Image:
    """Enkripsi pesan UTF-8, susun payload, lalu sisipkan ke salinan cover RGB.

    Salt dan nonce acak membuat setiap penyisipan memakai data kriptografi baru.
    Header menyimpan informasi yang dibutuhkan untuk memulihkan pesan.
    """
    _validate_plaintext(plaintext)
    _validate_stego_key(stego_key_bytes)

    # Buat parameter baru, lalu enkripsi sebelum bit payload masuk ke gambar.
    salt = generate_salt()
    aes_key = derive_aes_key(stego_key_bytes, salt)
    nonce = generate_nonce()
    ciphertext, auth_tag = encrypt_gcm(plaintext.encode("utf-8"), aes_key, nonce)
    payload = build_payload(ciphertext, auth_tag, salt, nonce)

    return embed_payload(
        cover_rgb,
        payload[:HEADER_SIZE],
        payload[HEADER_SIZE:],
        stego_key_bytes,
    )


def extract_plaintext(stego_rgb: Image.Image, stego_key_bytes: bytes) -> str:
    """Baca payload LSB, bentuk kembali kunci AES, lalu pulihkan teks UTF-8.

    Pesan hanya dikembalikan jika pemeriksaan tag autentikasi GCM berhasil.
    """
    _validate_stego_key(stego_key_bytes)

    # Header menyediakan salt dan nonce, bukan password atau kunci AES.
    payload = extract_payload(stego_rgb, stego_key_bytes)
    ciphertext, auth_tag, salt, nonce = parse_payload(payload)
    aes_key = derive_aes_key(stego_key_bytes, salt)
    plaintext_bytes = decrypt_gcm(ciphertext, auth_tag, aes_key, nonce)
    return plaintext_bytes.decode("utf-8")


def _validate_plaintext(plaintext: str) -> None:
    """Pastikan pesan berupa teks agar dapat dikodekan sebagai UTF-8."""
    if not isinstance(plaintext, str):
        raise TypeError("plaintext must be a string")


def _validate_stego_key(stego_key_bytes: bytes) -> None:
    """Tolak kunci kosong atau bukan bytes sebelum proses kriptografi berjalan."""
    if not isinstance(stego_key_bytes, bytes):
        raise TypeError("stego_key_bytes must be bytes")
    if not stego_key_bytes:
        raise ValueError("stego_key_bytes must not be empty")
