"""Pemilihan posisi LSB unik yang dapat diulang dengan kunci dan salt yang sama."""

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
    """Bentuk seed header dengan HMAC-SHA256 dari kunci dan konteks khusus header."""
    _require_bytes("stego_key_bytes", stego_key_bytes)
    return hmac.new(stego_key_bytes, _HEADER_CONTEXT, hashlib.sha256).digest()


def body_seed(stego_key_bytes: bytes, salt: bytes) -> bytes:
    """Bentuk seed body dari kunci, konteks body, dan salt 16 byte.

    Salt membuat posisi isi dapat berbeda pada penyisipan baru dengan password
    yang sama, sementara konteks memisahkan seed header dari seed body.
    """
    _require_bytes("stego_key_bytes", stego_key_bytes)
    _require_bytes("salt", salt)
    if len(salt) != SALT_LENGTH:
        raise ValueError(f"salt must be exactly {SALT_LENGTH} bytes")
    return hmac.new(stego_key_bytes, _BODY_CONTEXT + salt, hashlib.sha256).digest()


def select_header_positions(
    stego_key_bytes: bytes, width: int, height: int
) -> list[Position]:
    """Pilih 272 posisi kanal unik untuk menyimpan header tetap 34 byte."""
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
    """Pilih posisi isi dari kunci dan salt sambil mengecualikan seluruh posisi header."""
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
    """Pilih posisi kanal RGB tanpa pengulangan menggunakan shuffle Fisher-Yates parsial.

    Aliran angka berasal dari HMAC-SHA256, sehingga seed yang sama memberi
    urutan yang sama lintas proses Python. Hanya posisi yang dibutuhkan
    dibentuk, tanpa membuat daftar lengkap semua kanal gambar.
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

    # Pilih posisi tanpa pengulangan lewat shuffle parsial pada posisi yang tersedia.
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
    """Pembuat angka acak semu deterministik dari HMAC-SHA256 dengan counter bertambah."""

    def __init__(self, seed: bytes) -> None:
        """Simpan seed dan mulai counter dari nol untuk membentuk aliran angka yang dapat diulang."""
        self._seed = seed
        self._counter = 0

    def randbelow(self, upper_bound: int) -> int:
        """Ambil angka dari nol sampai batas eksklusif dengan rejection sampling.

        Kandidat di luar kelipatan rentang yang merata ditolak agar operasi modulo
        tidak memberi peluang lebih besar pada angka tertentu.
        """
        if upper_bound <= 0:
            raise ValueError("upper_bound must be greater than zero")

        modulus = 1 << _HMAC_BLOCK_BITS
        # Batasi kandidat ke kelipatan rentang agar semua keluaran sama peluangnya.
        acceptance_limit = modulus - (modulus % upper_bound)
        while True:
            candidate = int.from_bytes(self._next_block(), byteorder="big")
            if candidate < acceptance_limit:
                return candidate % upper_bound

    def _next_block(self) -> bytes:
        """Hasilkan satu blok HMAC dari konteks dan counter, lalu majukan counter."""
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
    """Validasi posisi yang dicadangkan, ubah menjadi indeks datar unik, lalu urutkan."""
    indices = {
        _position_to_index(position, width, height)
        for position in positions
    }
    return sorted(indices)


def _allowed_index_at(
    ordinal: int, total_positions: int, reserved_indices: list[int]
) -> int:
    """Cari indeks kanal dari urutan posisi yang tidak dicadangkan.

    Pencarian biner menghitung berapa posisi tersedia hingga titik tengah
    dengan bisect_right, sehingga lokasi header dapat dilewati.
    """
    target_rank = ordinal + 1
    low = 0
    high = total_positions - 1

    while low < high:
        midpoint = (low + high) // 2
        # Kurangi posisi header dari jumlah indeks hingga titik tengah pencarian.
        allowed_through_midpoint = midpoint + 1 - bisect_right(reserved_indices, midpoint)
        if allowed_through_midpoint >= target_rank:
            high = midpoint
        else:
            low = midpoint + 1

    return low


def _index_to_position(flat_index: int, width: int) -> Position:
    """Ubah indeks datar RGB menjadi koordinat x, y, dan nomor kanal."""
    pixel_index, channel = divmod(flat_index, RGB_CHANNELS)
    y, x = divmod(pixel_index, width)
    return x, y, channel


def _position_to_index(position: Position, width: int, height: int) -> int:
    """Validasi koordinat dan ubah x, y, kanal menjadi indeks datar RGB."""
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
    """Pastikan lebar dan tinggi berupa bilangan bulat positif, bukan boolean."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _validate_count(count: int) -> None:
    """Pastikan jumlah posisi berupa bilangan bulat tidak negatif."""
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if count < 0:
        raise ValueError("count must not be negative")


def _require_bytes(name: str, value: bytes) -> None:
    """Pastikan kunci, seed, atau salt berupa bytes sebelum dipakai oleh HMAC."""
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
