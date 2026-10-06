"""Penyisipan dan pembacaan satu bit LSB pada posisi kanal RGB yang dipilih dari kunci."""

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
    """Validasi kapasitas dan sisipkan header serta body ke salinan cover RGB.

    Posisi header berasal dari kunci; posisi body memakai kunci dan salt.
    Kedua kelompok posisi tidak boleh tumpang tindih agar bit tidak tertimpa.
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

    # Kerjakan salinan agar cover tetap tersedia untuk perbandingan kualitas.
    stego_rgb = cover_rgb.copy()
    _embed_bits(stego_rgb, header_positions, header)
    _embed_bits(stego_rgb, body_positions, body)
    return stego_rgb


def extract_header(stego_rgb: Image.Image, stego_key_bytes: bytes) -> bytes:
    """Baca 272 bit header dari posisi yang dibentuk ulang dengan stego-key.

    Header berukuran tetap 34 byte, sehingga dapat dibaca sebelum panjang
    body dan salt diketahui.
    """
    _validate_rgb_image(stego_rgb, "stego_rgb")
    width, height = stego_rgb.size
    if capacity_bits(width, height) < HEADER_BITS:
        raise ValueError("insufficient RGB capacity for the V1 header")

    header_positions = select_header_positions(stego_key_bytes, width, height)
    return _extract_bits(stego_rgb, header_positions)


def extract_body(
    stego_rgb: Image.Image, header: bytes, stego_key_bytes: bytes
) -> bytes:
    """Baca tepat sejumlah bit body yang dinyatakan header.

    Kunci dan salt membentuk kembali urutan posisi; posisi header dikecualikan
    agar data isi dibaca dari lokasi yang sama seperti saat penyisipan.
    """
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
    """Gabungkan hasil pembacaan header dan body menjadi payload lengkap.

    Lapisan ini membaca dan memvalidasi format LSB; autentikasi serta dekripsi
    AES-GCM dilakukan oleh lapisan crypto melalui stegochat.core.
    """
    header = extract_header(stego_rgb, stego_key_bytes)
    body = extract_body(stego_rgb, header, stego_key_bytes)
    return header + body


def _embed_bits(
    image: Image.Image, positions: list[tuple[int, int, int]], data: bytes
) -> None:
    """Ganti hanya bit terakhir kanal terpilih dengan bit data; tujuh bit lain tetap."""
    expected_count = len(data) * 8
    if len(positions) != expected_count:
        raise RuntimeError("position count does not match data bit count")

    pixels = image.load()
    for (x, y, channel), bit in zip(positions, _bytes_to_bits(data), strict=True):
        pixel = list(pixels[x, y])
        # 0xFE mengosongkan LSB; OR mengisinya dengan bit pesan tanpa mengubah bit lain.
        pixel[channel] = (pixel[channel] & 0xFE) | bit
        pixels[x, y] = tuple(pixel)


def _extract_bits(
    image: Image.Image, positions: list[tuple[int, int, int]]
) -> bytes:
    """Ambil bit terakhir tiap kanal terpilih, lalu gabungkan kembali menjadi bytes."""
    pixels = image.load()
    # AND 1 membuang tujuh bit atas dan mengambil hanya bit terakhir.
    bits = [pixels[x, y][channel] & 1 for x, y, channel in positions]
    return _bits_to_bytes(bits)


def _bytes_to_bits(data: bytes) -> list[int]:
    """Uraikan tiap byte dari bit paling kiri ke kanan agar urutan data konsisten."""
    return [
        (value >> shift) & 1
        for value in data
        for shift in range(7, -1, -1)
    ]


def _bits_to_bytes(bits: list[int]) -> bytes:
    """Gabungkan setiap delapan bit menjadi satu byte; tolak kelompok yang tidak lengkap."""
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
    """Pastikan posisi header dan body terpisah agar tidak ada bit yang saling menimpa."""
    if not set(header_positions).isdisjoint(body_positions):
        raise RuntimeError("header and body positions overlap")


def _validate_rgb_image(image: Image.Image, name: str) -> None:
    """Pastikan gambar Pillow bermode RGB agar setiap piksel memiliki tiga kanal."""
    if not isinstance(image, Image.Image):
        raise TypeError(f"{name} must be a Pillow Image")
    if image.mode != "RGB":
        raise ValueError(f"{name} must use RGB mode")


def _require_bytes(name: str, value: bytes) -> None:
    """Tolak masukan bukan bytes sebelum dikonversi ke bit LSB."""
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
