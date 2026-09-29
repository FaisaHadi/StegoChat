"""Deterministic RGB-channel position selection for StegoChat V1."""

from __future__ import annotations

import hashlib
import hmac
from bisect import bisect_right
from collections.abc import Iterable

from stego.capacity import HEADER_BITS, RGB_CHANNELS
from stego.payload import SALT_LENGTH

Position = tuple[int, int, int]

HEADER_POSITION_COUNT = HEADER_BITS
_HEADER_CONTEXT = b"STEGOCHAT-HEADER"
_BODY_CONTEXT = b"STEGOCHAT-BODY"
_POSITION_CONTEXT = b"STEGOCHAT-POSITIONS-V1"
_HMAC_BLOCK_BITS = 256
_COUNTER_MAX = (1 << 64) - 1


def header_seed(stego_key_bytes: bytes) -> bytes:
    """Return the V1 HMAC-SHA256 seed used for header positions."""
    _require_bytes("stego_key_bytes", stego_key_bytes)
    return hmac.new(stego_key_bytes, _HEADER_CONTEXT, hashlib.sha256).digest()


def body_seed(stego_key_bytes: bytes, salt: bytes) -> bytes:
    """Return the V1 HMAC-SHA256 seed used for body positions."""
    _require_bytes("stego_key_bytes", stego_key_bytes)
    _require_bytes("salt", salt)
    if len(salt) != SALT_LENGTH:
        raise ValueError(f"salt must be exactly {SALT_LENGTH} bytes")
    return hmac.new(stego_key_bytes, _BODY_CONTEXT + salt, hashlib.sha256).digest()


def select_header_positions(
    stego_key_bytes: bytes, width: int, height: int
) -> list[Position]:
    """Select the fixed 272 unique V1 header positions."""
    return select_positions(
        header_seed(stego_key_bytes), width, height, HEADER_POSITION_COUNT
    )


def select_body_positions(
    stego_key_bytes: bytes,
    salt: bytes,
    width: int,
    height: int,
    requested_count: int,
    reserved_header_positions: Iterable[Position],
) -> list[Position]:
    """Select body positions while excluding every reserved header position."""
    return select_positions(
        body_seed(stego_key_bytes, salt),
        width,
        height,
        requested_count,
        reserved_header_positions,
    )


def select_positions(
    seed: bytes,
    width: int,
    height: int,
    count: int,
    excluded_positions: Iterable[Position] = (),
) -> list[Position]:
    """Deterministically select unique RGB-channel positions.

    Positions use row-major RGB-channel indexing: index zero is ``(0, 0, 0)``,
    followed by ``(0, 0, 1)`` and ``(0, 0, 2)``. The position stream is based
    on HMAC-SHA256 counter blocks and does not use Python's built-in ``hash()``.
    """
    _require_bytes("seed", seed)
    _validate_dimension("width", width)
    _validate_dimension("height", height)
    _validate_count(count)

    total_positions = width * height * RGB_CHANNELS
    reserved_indices = _reserved_indices(excluded_positions, width, height)
    available_count = total_positions - len(reserved_indices)
    if count > available_count:
        raise ValueError("insufficient non-reserved RGB-channel positions")

    rng = _HmacCounterRng(seed)
    swaps: dict[int, int] = {}
    selected: list[Position] = []

    # This is a partial Fisher-Yates shuffle over unreserved ordinal positions.
    for drawn_count in range(count):
        remaining_count = available_count - drawn_count
        chosen_ordinal = rng.randbelow(remaining_count)
        selected_ordinal = swaps.get(chosen_ordinal, chosen_ordinal)
        final_ordinal = remaining_count - 1
        swaps[chosen_ordinal] = swaps.get(final_ordinal, final_ordinal)

        flat_index = _allowed_index_at(
            selected_ordinal, total_positions, reserved_indices
        )
        selected.append(_index_to_position(flat_index, width))

    return selected


class _HmacCounterRng:
    """A process-stable, deterministic random-number stream from HMAC blocks."""

    def __init__(self, seed: bytes) -> None:
        self._seed = seed
        self._counter = 0

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be greater than zero")

        modulus = 1 << _HMAC_BLOCK_BITS
        acceptance_limit = modulus - (modulus % upper_bound)
        while True:
            candidate = int.from_bytes(self._next_block(), byteorder="big")
            if candidate < acceptance_limit:
                return candidate % upper_bound

    def _next_block(self) -> bytes:
        if self._counter > _COUNTER_MAX:
            raise RuntimeError("deterministic position stream is exhausted")
        counter_bytes = self._counter.to_bytes(8, byteorder="big")
        self._counter += 1
        return hmac.new(
            self._seed, _POSITION_CONTEXT + counter_bytes, hashlib.sha256
        ).digest()


def _reserved_indices(
    positions: Iterable[Position], width: int, height: int
) -> list[int]:
    indices = {
        _position_to_index(position, width, height)
        for position in positions
    }
    return sorted(indices)


def _allowed_index_at(
    ordinal: int, total_positions: int, reserved_indices: list[int]
) -> int:
    """Map an ordinal among unreserved positions to its flat RGB index."""
    target_rank = ordinal + 1
    low = 0
    high = total_positions - 1

    while low < high:
        midpoint = (low + high) // 2
        allowed_through_midpoint = midpoint + 1 - bisect_right(reserved_indices, midpoint)
        if allowed_through_midpoint >= target_rank:
            high = midpoint
        else:
            low = midpoint + 1

    return low


def _index_to_position(flat_index: int, width: int) -> Position:
    pixel_index, channel = divmod(flat_index, RGB_CHANNELS)
    y, x = divmod(pixel_index, width)
    return x, y, channel


def _position_to_index(position: Position, width: int, height: int) -> int:
    if not isinstance(position, tuple) or len(position) != 3:
        raise TypeError("each position must be a tuple of (x, y, channel)")

    x, y, channel = position
    for name, value in (("x", x), ("y", y), ("channel", channel)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"position {name} must be an integer")

    if not 0 <= x < width or not 0 <= y < height:
        raise ValueError("reserved position is outside image bounds")
    if not 0 <= channel < RGB_CHANNELS:
        raise ValueError("reserved position channel must be 0, 1, or 2")

    return ((y * width) + x) * RGB_CHANNELS + channel


def _validate_dimension(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _validate_count(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if count < 0:
        raise ValueError("count must not be negative")


def _require_bytes(name: str, value: bytes) -> None:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
