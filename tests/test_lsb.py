"""Pengujian penyisipan dan pembacaan LSB pada kanal RGB."""

from __future__ import annotations

import io
import secrets

import pytest
from PIL import Image

from stego.lsb import embed_payload, extract_body, extract_header, extract_payload
from stego.payload import (
    AUTH_TAG_LENGTH,
    HEADER_SIZE,
    NONCE_LENGTH,
    SALT_LENGTH,
    build_payload,
    parse_header,
)
from stego.prng import select_body_positions, select_header_positions

WIDTH = 24
HEIGHT = 24


def _cover_image() -> Image.Image:
    """Buat cover RGB berwarna tetap agar perubahan LSB mudah dibandingkan."""
    return Image.new("RGB", (WIDTH, HEIGHT), color=(100, 101, 102))


def _payload_parts() -> tuple[bytes, bytes, bytes]:
    """Buat payload uji acak dan pisahkan header serta body untuk pengujian LSB."""
    payload = build_payload(
        secrets.token_bytes(19),
        secrets.token_bytes(AUTH_TAG_LENGTH),
        secrets.token_bytes(SALT_LENGTH),
        secrets.token_bytes(NONCE_LENGTH),
    )
    return payload[:HEADER_SIZE], payload[HEADER_SIZE:], payload


def test_embed_then_extract_header_and_payload() -> None:
    """Pastikan header dan payload dapat dibaca kembali sesudah embedding."""
    cover = _cover_image()
    header, body, payload = _payload_parts()
    stego_key = secrets.token_bytes(32)

    stego = embed_payload(cover, header, body, stego_key)

    assert extract_header(stego, stego_key) == header
    assert extract_body(stego, header, stego_key) == body
    assert extract_payload(stego, stego_key) == payload


def test_extracted_payload_is_identical_to_embedded_payload() -> None:
    """Pastikan bytes hasil ekstraksi identik dengan payload yang disisipkan."""
    header, body, payload = _payload_parts()
    stego_key = secrets.token_bytes(32)

    stego = embed_payload(_cover_image(), header, body, stego_key)

    assert extract_payload(stego, stego_key) == payload


def test_header_and_body_positions_do_not_overlap() -> None:
    """Pastikan posisi penyimpanan header dan body tidak bertabrakan."""
    header, body, _ = _payload_parts()
    stego_key = secrets.token_bytes(32)
    _, salt, _ = parse_header(header)

    header_positions = select_header_positions(stego_key, WIDTH, HEIGHT)
    body_positions = select_body_positions(
        stego_key, salt, WIDTH, HEIGHT, len(body) * 8, header_positions
    )

    assert set(header_positions).isdisjoint(body_positions)


def test_embed_rejects_insufficient_capacity() -> None:
    """Pastikan embedding menolak payload yang melampaui kapasitas."""
    header, body, _ = _payload_parts()

    with pytest.raises(ValueError, match="insufficient RGB capacity"):
        embed_payload(Image.new("RGB", (9, 10)), header, body, secrets.token_bytes(32))


def test_non_rgb_image_is_rejected_with_clear_error() -> None:
    """Pastikan gambar bukan RGB ditolak sebelum operasi kanal."""
    header, body, _ = _payload_parts()

    with pytest.raises(ValueError, match="RGB"):
        embed_payload(Image.new("L", (WIDTH, HEIGHT)), header, body, secrets.token_bytes(32))


def test_embedding_does_not_modify_the_original_image() -> None:
    """Pastikan embedding menghasilkan salinan tanpa mengubah cover asli."""
    cover = _cover_image()
    original_bytes = cover.tobytes()
    header, body, _ = _payload_parts()

    stego = embed_payload(cover, header, body, secrets.token_bytes(32))

    assert cover.tobytes() == original_bytes
    assert stego is not cover


def test_pixel_changes_are_limited_to_the_least_significant_bit() -> None:
    """Pastikan hanya bit terakhir yang berubah dan selisih nilai kanal maksimal satu."""
    cover = _cover_image()
    header, body, _ = _payload_parts()

    stego = embed_payload(cover, header, body, secrets.token_bytes(32))

    for original_value, stego_value in zip(cover.tobytes(), stego.tobytes(), strict=True):
        assert original_value ^ stego_value in (0, 1)


def test_extraction_is_deterministic_for_the_same_key() -> None:
    """Pastikan kunci yang sama membaca payload yang sama pada ekstraksi berulang."""
    header, body, payload = _payload_parts()
    stego_key = secrets.token_bytes(32)
    stego = embed_payload(_cover_image(), header, body, stego_key)

    assert extract_payload(stego, stego_key) == extract_payload(stego, stego_key) == payload


def test_wrong_stego_key_does_not_return_the_embedded_payload() -> None:
    """Pastikan kunci berbeda tidak mengembalikan payload asli."""
    header, body, payload = _payload_parts()
    stego = embed_payload(_cover_image(), header, body, secrets.token_bytes(32))

    try:
        extracted = extract_payload(stego, secrets.token_bytes(32))
    except ValueError:
        return

    assert extracted != payload


def test_png_round_trip_preserves_embedded_payload() -> None:
    """Pastikan simpan-baca PNG mempertahankan seluruh bit payload."""
    header, body, payload = _payload_parts()
    stego_key = secrets.token_bytes(32)
    stego = embed_payload(_cover_image(), header, body, stego_key)
    buffer = io.BytesIO()
    stego.save(buffer, format="PNG")
    buffer.seek(0)

    with Image.open(buffer) as restored:
        restored.load()
        assert extract_payload(restored, stego_key) == payload
