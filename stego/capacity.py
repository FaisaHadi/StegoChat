"""RGB-channel capacity calculations for StegoChat V1."""

from __future__ import annotations

from stego.payload import AUTH_TAG_LENGTH, HEADER_SIZE, MIN_BODY_LENGTH

RGB_CHANNELS = 3
BITS_PER_BYTE = 8
HEADER_BITS = HEADER_SIZE * BITS_PER_BYTE


def capacity_bits(width: int, height: int) -> int:
    """Return the number of one-bit RGB-channel locations in an image."""
    _validate_dimension("width", width)
    _validate_dimension("height", height)
    return width * height * RGB_CHANNELS


def required_bits(body_length: int) -> int:
    """Return V1 header and body bits required for a declared body length."""
    _validate_body_length(body_length)
    return HEADER_BITS + (body_length * BITS_PER_BYTE)


def can_embed(width: int, height: int, body_length: int) -> bool:
    """Return whether an RGB image can hold the V1 header and body."""
    return required_bits(body_length) <= capacity_bits(width, height)


def max_body_length(width: int, height: int) -> int:
    """Return the maximum body-byte count after reserving the V1 header.

    A return value of zero means the image has no valid V1 payload capacity.
    """
    remaining_bits = capacity_bits(width, height) - HEADER_BITS
    return max(0, remaining_bits // BITS_PER_BYTE)


def max_plaintext_bytes(width: int, height: int) -> int:
    """Return the UTF-8 byte limit after reserving the header and auth tag.

    A zero limit does not guarantee even an empty payload fits; use can_embed
    to validate the complete payload before embedding.
    """
    return max(0, max_body_length(width, height) - AUTH_TAG_LENGTH)


def _validate_dimension(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _validate_body_length(body_length: int) -> None:
    if isinstance(body_length, bool) or not isinstance(body_length, int):
        raise TypeError("body_length must be an integer")
    if body_length < MIN_BODY_LENGTH:
        raise ValueError(
            f"body_length must include a {MIN_BODY_LENGTH}-byte authentication tag"
        )
