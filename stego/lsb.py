"""RGB one-bit LSB payload embedding and extraction for StegoChat V1."""

from __future__ import annotations

from PIL import Image

from stego.capacity import HEADER_BITS, can_embed, capacity_bits
from stego.payload import HEADER_SIZE, parse_header
from stego.prng import select_body_positions, select_header_positions


def embed_payload(
    cover_rgb: Image.Image,
    header: bytes,
    body: bytes,
    stego_key_bytes: bytes,
) -> Image.Image:
    """Embed a validated V1 header and body into a copied RGB image.

    The caller provides the binary header and body separately. The body is the
    ciphertext followed by its authentication tag, as defined by V1.
    """
    _validate_rgb_image(cover_rgb, "cover_rgb")
    _require_bytes("body", body)

    declared_length, salt, _ = parse_header(header)
    if len(body) != declared_length:
        raise ValueError("body length does not match the V1 header")

    width, height = cover_rgb.size
    if not can_embed(width, height, len(body)):
        raise ValueError("insufficient RGB capacity for the V1 payload")

    header_positions = select_header_positions(stego_key_bytes, width, height)
    body_positions = select_body_positions(
        stego_key_bytes,
        salt,
        width,
        height,
        len(body) * 8,
        header_positions,
    )
    _ensure_non_overlapping(header_positions, body_positions)

    stego_rgb = cover_rgb.copy()
    _embed_bits(stego_rgb, header_positions, header)
    _embed_bits(stego_rgb, body_positions, body)
    return stego_rgb


def extract_header(stego_rgb: Image.Image, stego_key_bytes: bytes) -> bytes:
    """Extract the fixed 34-byte V1 header using header positions only."""
    _validate_rgb_image(stego_rgb, "stego_rgb")
    width, height = stego_rgb.size
    if capacity_bits(width, height) < HEADER_BITS:
        raise ValueError("insufficient RGB capacity for the V1 header")

    header_positions = select_header_positions(stego_key_bytes, width, height)
    return _extract_bits(stego_rgb, header_positions)


def extract_body(
    stego_rgb: Image.Image, header: bytes, stego_key_bytes: bytes
) -> bytes:
    """Extract the declared V1 body while excluding header positions."""
    _validate_rgb_image(stego_rgb, "stego_rgb")
    declared_length, salt, _ = parse_header(header)
    width, height = stego_rgb.size

    if not can_embed(width, height, declared_length):
        raise ValueError("declared V1 payload length exceeds RGB capacity")

    header_positions = select_header_positions(stego_key_bytes, width, height)
    body_positions = select_body_positions(
        stego_key_bytes,
        salt,
        width,
        height,
        declared_length * 8,
        header_positions,
    )
    _ensure_non_overlapping(header_positions, body_positions)
    return _extract_bits(stego_rgb, body_positions)


def extract_payload(stego_rgb: Image.Image, stego_key_bytes: bytes) -> bytes:
    """Extract the raw V1 payload bytes from an RGB stego image.

    This LSB-only layer validates and returns `header + body`. AES-GCM
    authentication and decryption remain the responsibility of the crypto
    layer that consumes the extracted payload.
    """
    header = extract_header(stego_rgb, stego_key_bytes)
    body = extract_body(stego_rgb, header, stego_key_bytes)
    return header + body


def _embed_bits(
    image: Image.Image, positions: list[tuple[int, int, int]], data: bytes
) -> None:
    expected_count = len(data) * 8
    if len(positions) != expected_count:
        raise RuntimeError("position count does not match data bit count")

    pixels = image.load()
    for (x, y, channel), bit in zip(positions, _bytes_to_bits(data), strict=True):
        pixel = list(pixels[x, y])
        pixel[channel] = (pixel[channel] & 0xFE) | bit
        pixels[x, y] = tuple(pixel)


def _extract_bits(
    image: Image.Image, positions: list[tuple[int, int, int]]
) -> bytes:
    pixels = image.load()
    bits = [pixels[x, y][channel] & 1 for x, y, channel in positions]
    return _bits_to_bytes(bits)


def _bytes_to_bits(data: bytes) -> list[int]:
    return [
        (value >> shift) & 1
        for value in data
        for shift in range(7, -1, -1)
    ]


def _bits_to_bytes(bits: list[int]) -> bytes:
    if len(bits) % 8 != 0:
        raise ValueError("bit count must be divisible by eight")

    output = bytearray()
    for start in range(0, len(bits), 8):
        value = 0
        for bit in bits[start : start + 8]:
            value = (value << 1) | bit
        output.append(value)
    return bytes(output)


def _ensure_non_overlapping(
    header_positions: list[tuple[int, int, int]],
    body_positions: list[tuple[int, int, int]],
) -> None:
    if not set(header_positions).isdisjoint(body_positions):
        raise RuntimeError("header and body positions overlap")


def _validate_rgb_image(image: Image.Image, name: str) -> None:
    if not isinstance(image, Image.Image):
        raise TypeError(f"{name} must be a Pillow Image")
    if image.mode != "RGB":
        raise ValueError(f"{name} must use RGB mode")


def _require_bytes(name: str, value: bytes) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
