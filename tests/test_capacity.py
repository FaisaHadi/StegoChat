"""Tests for StegoChat V1 RGB capacity calculations."""

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
    assert capacity_bits(10, 7) == 10 * 7 * 3


def test_required_bits_includes_fixed_header_and_body() -> None:
    body_length = AUTH_TAG_LENGTH + 1

    assert required_bits(body_length) == HEADER_BITS + (body_length * 8)


def test_can_embed_accepts_exact_capacity_boundary() -> None:
    body_length = AUTH_TAG_LENGTH + 1

    assert required_bits(body_length) == capacity_bits(8, 17)
    assert can_embed(8, 17, body_length) is True


def test_can_embed_rejects_insufficient_capacity() -> None:
    assert can_embed(8, 16, AUTH_TAG_LENGTH + 1) is False


def test_max_body_length_reserves_header_bits() -> None:
    assert max_body_length(8, 17) == AUTH_TAG_LENGTH + 1


def test_max_body_length_is_zero_when_header_cannot_fit() -> None:
    assert max_body_length(1, 1) == 0


def test_plaintext_capacity_reserves_header_and_tag() -> None:
    assert max_plaintext_bytes(8, 17) == 1
    assert can_embed(8, 17, AUTH_TAG_LENGTH + 1)
    assert not can_embed(8, 17, AUTH_TAG_LENGTH + 2)


@pytest.mark.parametrize("size", [(1, 1), (10, 10), (8, 16)])
def test_plaintext_capacity_is_never_negative(size) -> None:
    assert max_plaintext_bytes(*size) == 0


@pytest.mark.parametrize("width,height", [(0, 1), (1, 0), (-1, 2)])
def test_capacity_rejects_invalid_dimensions(width: int, height: int) -> None:
    with pytest.raises(ValueError):
        capacity_bits(width, height)


def test_required_bits_rejects_body_shorter_than_authentication_tag() -> None:
    with pytest.raises(ValueError, match="authentication tag"):
        required_bits(AUTH_TAG_LENGTH - 1)
