"""End-to-end tests for the StegoChat V1 integration layer."""

from __future__ import annotations

import io
import secrets

import pytest
from cryptography.exceptions import InvalidTag
from PIL import Image

from stego.payload import parse_header
from stego.prng import select_body_positions
from stegochat.core import embed_plaintext, extract_plaintext

WIDTH = 32
HEIGHT = 32


def _cover_image() -> Image.Image:
    return Image.new("RGB", (WIDTH, HEIGHT), color=(100, 101, 102))


def test_plaintext_embed_extract_round_trip() -> None:
    plaintext = "StegoChat integration message"
    stego_key = secrets.token_bytes(32)

    stego = embed_plaintext(_cover_image(), plaintext, stego_key)

    assert extract_plaintext(stego, stego_key) == plaintext


def test_empty_plaintext_round_trip() -> None:
    stego_key = secrets.token_bytes(32)

    stego = embed_plaintext(_cover_image(), "", stego_key)

    assert extract_plaintext(stego, stego_key) == ""


def test_unicode_plaintext_round_trip() -> None:
    plaintext = "Pesan rahasia: halo dunia, kafe, dan こんにちは"
    stego_key = secrets.token_bytes(32)

    stego = embed_plaintext(_cover_image(), plaintext, stego_key)

    assert extract_plaintext(stego, stego_key) == plaintext


def test_wrong_stego_key_fails_extraction_or_authentication() -> None:
    stego = embed_plaintext(
        _cover_image(), "Protected message", secrets.token_bytes(32)
    )

    with pytest.raises((ValueError, InvalidTag)):
        extract_plaintext(stego, secrets.token_bytes(32))


def test_modified_stego_body_fails_aes_gcm_authentication() -> None:
    plaintext = "Authenticated message"
    stego_key = secrets.token_bytes(32)
    stego = embed_plaintext(_cover_image(), plaintext, stego_key)
    tampered = stego.copy()

    from stego.lsb import extract_header
    from stego.prng import select_header_positions

    header = extract_header(tampered, stego_key)
    body_length, salt, _ = parse_header(header)
    header_positions = select_header_positions(stego_key, WIDTH, HEIGHT)
    body_position = select_body_positions(
        stego_key, salt, WIDTH, HEIGHT, body_length * 8, header_positions
    )[0]
    x, y, channel = body_position
    pixel = list(tampered.getpixel((x, y)))
    pixel[channel] ^= 1
    tampered.putpixel((x, y), tuple(pixel))

    with pytest.raises(InvalidTag):
        extract_plaintext(tampered, stego_key)


def test_insufficient_image_capacity_is_rejected() -> None:
    with pytest.raises(ValueError, match="insufficient RGB capacity"):
        embed_plaintext(Image.new("RGB", (9, 10)), "small", secrets.token_bytes(32))


def test_png_round_trip_preserves_plaintext() -> None:
    plaintext = "PNG transport preserves this text"
    stego_key = secrets.token_bytes(32)
    stego = embed_plaintext(_cover_image(), plaintext, stego_key)
    buffer = io.BytesIO()
    stego.save(buffer, format="PNG")
    buffer.seek(0)

    with Image.open(buffer) as restored:
        restored.load()
        assert extract_plaintext(restored, stego_key) == plaintext


def test_cover_image_is_not_modified() -> None:
    cover = _cover_image()
    original_bytes = cover.tobytes()

    stego = embed_plaintext(cover, "Original remains unchanged", secrets.token_bytes(32))

    assert cover.tobytes() == original_bytes
    assert stego is not cover
