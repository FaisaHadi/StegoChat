"""Pengujian batas kapasitas RGB dengan ruang header dan tag GCM."""

from __future__ import annotations

import pytest

from stego.capacity import (
    HEADER_BITS,
    can_embed,
    capacity_bits,
    max_body_length,
    max_plaintext_bytes,
    required_bits,
)
from stego.payload import AUTH_TAG_LENGTH


def test_capacity_bits_uses_three_rgb_channels() -> None:
    """Pastikan kapasitas memakai tiga kanal RGB dengan satu bit per kanal."""
    assert capacity_bits(10, 7) == 10 * 7 * 3


def test_required_bits_includes_fixed_header_and_body() -> None:
    """Pastikan kebutuhan bit mencakup header tetap dan seluruh body."""
    body_length = AUTH_TAG_LENGTH + 1

    assert required_bits(body_length) == HEADER_BITS + (body_length * 8)


def test_can_embed_accepts_exact_capacity_boundary() -> None:
    """Pastikan payload yang tepat memenuhi batas kapasitas masih diterima."""
    body_length = AUTH_TAG_LENGTH + 1

    assert required_bits(body_length) == capacity_bits(8, 17)
    assert can_embed(8, 17, body_length) is True


def test_can_embed_rejects_insufficient_capacity() -> None:
    """Pastikan payload lebih besar daripada kapasitas ditolak."""
    assert can_embed(8, 16, AUTH_TAG_LENGTH + 1) is False


def test_max_body_length_reserves_header_bits() -> None:
    """Pastikan batas body sudah mengurangi ruang header."""
    assert max_body_length(8, 17) == AUTH_TAG_LENGTH + 1


def test_max_body_length_is_zero_when_header_cannot_fit() -> None:
    """Pastikan kapasitas body tidak negatif saat gambar terlalu kecil untuk header."""
    assert max_body_length(1, 1) == 0


def test_plaintext_capacity_reserves_header_and_tag() -> None:
    """Pastikan batas pesan sudah mengurangi header dan tag autentikasi."""
    assert max_plaintext_bytes(8, 17) == 1
    assert can_embed(8, 17, AUTH_TAG_LENGTH + 1)
    assert not can_embed(8, 17, AUTH_TAG_LENGTH + 2)


@pytest.mark.parametrize("size", [(1, 1), (10, 10), (8, 16)])
def test_plaintext_capacity_is_never_negative(size) -> None:
    """Pastikan batas pesan minimal nol pada berbagai dimensi kecil."""
    assert max_plaintext_bytes(*size) == 0


@pytest.mark.parametrize("width,height", [(0, 1), (1, 0), (-1, 2)])
def test_capacity_rejects_invalid_dimensions(width: int, height: int) -> None:
    """Pastikan perhitungan kapasitas menolak dimensi tidak valid."""
    with pytest.raises(ValueError):
        capacity_bits(width, height)


def test_required_bits_rejects_body_shorter_than_authentication_tag() -> None:
    """Pastikan body yang tidak cukup untuk tag ditolak."""
    with pytest.raises(ValueError, match="authentication tag"):
        required_bits(AUTH_TAG_LENGTH - 1)
