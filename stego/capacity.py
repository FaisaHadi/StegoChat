"""Perhitungan kapasitas LSB dengan memperhitungkan header dan tag autentikasi."""

from __future__ import annotations

from stego.payload import AUTH_TAG_LENGTH, HEADER_SIZE, MIN_BODY_LENGTH

RGB_CHANNELS = 3
BITS_PER_BYTE = 8
HEADER_BITS = HEADER_SIZE * BITS_PER_BYTE


def capacity_bits(width: int, height: int) -> int:
    """Hitung kapasitas total: lebar x tinggi x 3, karena tiap kanal RGB menyimpan 1 bit."""
    _validate_dimension("width", width)
    _validate_dimension("height", height)
    return width * height * RGB_CHANNELS


def required_bits(body_length: int) -> int:
    """Hitung kebutuhan bit header dan body; panjang body sudah termasuk tag GCM."""
    _validate_body_length(body_length)
    return HEADER_BITS + (body_length * BITS_PER_BYTE)


def can_embed(width: int, height: int, body_length: int) -> bool:
    """Bandingkan kebutuhan seluruh payload dengan kapasitas gambar untuk mencegah kelebihan data."""
    return required_bits(body_length) <= capacity_bits(width, height)


def max_body_length(width: int, height: int) -> int:
    """Hitung batas byte body setelah kapasitas dikurangi ukuran header.

    Nilai dibatasi minimal nol jika header sendiri tidak muat.
    """
    remaining_bits = capacity_bits(width, height) - HEADER_BITS
    return max(0, remaining_bits // BITS_PER_BYTE)


def max_plaintext_bytes(width: int, height: int) -> int:
    """Hitung batas byte pesan UTF-8 setelah ruang header dan tag GCM dicadangkan.

    Batas nol belum menjamin payload kosong muat; can_embed tetap diperlukan
    untuk memeriksa ukuran lengkap payload.
    """
    return max(0, max_body_length(width, height) - AUTH_TAG_LENGTH)


def _validate_dimension(name: str, value: int) -> None:
    """Tolak dimensi bukan bilangan bulat positif, termasuk nilai boolean."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _validate_body_length(body_length: int) -> None:
    """Pastikan panjang body berupa bilangan bulat dan cukup untuk tag autentikasi."""
    if isinstance(body_length, bool) or not isinstance(body_length, int):
        raise TypeError("body_length must be an integer")
    if body_length < MIN_BODY_LENGTH:
        raise ValueError(
            f"body_length must include a {MIN_BODY_LENGTH}-byte authentication tag"
        )
