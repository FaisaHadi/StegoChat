"""Binary payload construction and validation for StegoChat V1."""

from __future__ import annotations

MAGIC = b"SG"
MAGIC_LENGTH = 2
LENGTH_FIELD_LENGTH = 4
SALT_LENGTH = 16
NONCE_LENGTH = 12
AUTH_TAG_LENGTH = 16
HEADER_SIZE = MAGIC_LENGTH + LENGTH_FIELD_LENGTH + SALT_LENGTH + NONCE_LENGTH
MIN_BODY_LENGTH = AUTH_TAG_LENGTH
MAX_BODY_LENGTH = (1 << (LENGTH_FIELD_LENGTH * 8)) - 1


def build_header(length: int, salt: bytes, nonce: bytes) -> bytes:
    """Build the fixed 34-byte V1 header.

    ``length`` is the body size only: ciphertext plus the 16-byte AES-GCM
    authentication tag.
    """
    _validate_body_length(length)
    _require_exact_bytes("salt", salt, SALT_LENGTH)
    _require_exact_bytes("nonce", nonce, NONCE_LENGTH)

    return MAGIC + length.to_bytes(LENGTH_FIELD_LENGTH, byteorder="big") + salt + nonce


def parse_header(header_bytes: bytes) -> tuple[int, bytes, bytes]:
    """Validate and parse a fixed 34-byte V1 header."""
    _require_bytes("header_bytes", header_bytes)
    if len(header_bytes) != HEADER_SIZE:
        raise ValueError(f"header_bytes must be exactly {HEADER_SIZE} bytes")
    if header_bytes[:MAGIC_LENGTH] != MAGIC:
        raise ValueError("invalid StegoChat V1 magic")

    length_start = MAGIC_LENGTH
    length_end = length_start + LENGTH_FIELD_LENGTH
    salt_end = length_end + SALT_LENGTH

    length = int.from_bytes(header_bytes[length_start:length_end], byteorder="big")
    _validate_body_length(length)
    return length, header_bytes[length_end:salt_end], header_bytes[salt_end:]


def build_payload(ciphertext: bytes, auth_tag: bytes, salt: bytes, nonce: bytes) -> bytes:
    """Build a complete V1 payload from ciphertext and an AES-GCM tag."""
    _require_bytes("ciphertext", ciphertext)
    _require_exact_bytes("auth_tag", auth_tag, AUTH_TAG_LENGTH)

    body = ciphertext + auth_tag
    return build_header(len(body), salt, nonce) + body


def parse_payload(payload: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    """Parse a complete V1 payload into ciphertext, tag, salt, and nonce."""
    _require_bytes("payload", payload)
    if len(payload) < HEADER_SIZE:
        raise ValueError("payload is shorter than the V1 header")

    length, salt, nonce = parse_header(payload[:HEADER_SIZE])
    body = payload[HEADER_SIZE:]
    if len(body) != length:
        raise ValueError("payload body length does not match the V1 header")

    ciphertext, auth_tag = split_body(body)
    return ciphertext, auth_tag, salt, nonce


def split_body(body: bytes) -> tuple[bytes, bytes]:
    """Split a V1 body into ciphertext and its final 16-byte tag."""
    _require_bytes("body", body)
    _validate_body_length(len(body))
    return body[:-AUTH_TAG_LENGTH], body[-AUTH_TAG_LENGTH:]


def _validate_body_length(length: int) -> None:
    if isinstance(length, bool) or not isinstance(length, int):
        raise TypeError("length must be an integer")
    if length < MIN_BODY_LENGTH:
        raise ValueError(
            f"length must include a {AUTH_TAG_LENGTH}-byte authentication tag"
        )
    if length > MAX_BODY_LENGTH:
        raise ValueError(f"length cannot exceed {MAX_BODY_LENGTH} bytes")


def _require_exact_bytes(name: str, value: bytes, expected_length: int) -> None:
    _require_bytes(name, value)
    if len(value) != expected_length:
        raise ValueError(f"{name} must be exactly {expected_length} bytes")


def _require_bytes(name: str, value: bytes) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
