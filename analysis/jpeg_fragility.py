"""Pengujian pemulihan pesan setelah stego dikompresi ulang menjadi JPEG.

JPEG bersifat lossy dan dapat mengubah bit LSB. Status diambil dari
percobaan ekstraksi nyata pada piksel hasil dekode JPEG.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from PIL import Image

from analysis.image_utils import require_rgb_image
from stegochat.core import embed_plaintext, extract_plaintext

DEFAULT_JPEG_QUALITY = 85
JPEG_FORMAT = "JPEG"
PNG_FORMAT = "PNG"


@dataclass(frozen=True)
class JpegFragilityResult:
    """Wadah kualitas JPEG, ukuran berkas, status pemulihan, dan informasi kegagalan."""

    quality: int
    jpeg_created: bool
    jpeg_size_bytes: int
    extraction_succeeded: bool
    decryption_succeeded: bool
    recovered_plaintext: str | None
    plaintext_matches: bool
    error_stage: str | None
    error_type: str | None
    error_reason: str | None

    @property
    def attack_destroyed_payload(self) -> bool:
        """Nyatakan payload tidak pulih jika ekstraksi gagal atau pesan berbeda dari asalnya."""
        return not (self.extraction_succeeded and self.plaintext_matches)


def run_jpeg_fragility_test(
    cover_rgb: Image.Image,
    plaintext: str,
    stego_key_bytes: bytes,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> JpegFragilityResult:
    """Buat stego dari cover, simpan-baca sebagai PNG, lalu uji satu kualitas JPEG.

    PNG mempertahankan piksel sebelum JPEG diuji; hasil dicatat berdasarkan
    percobaan pemulihan pesan setelah kompresi.
    """
    require_rgb_image(cover_rgb, "cover_rgb")
    _validate_quality(quality)

    stego_rgb = embed_plaintext(cover_rgb, plaintext, stego_key_bytes)
    png_round_trip = _round_trip(stego_rgb, PNG_FORMAT, quality=None)
    return run_jpeg_attack(png_round_trip, plaintext, stego_key_bytes, quality)


def run_jpeg_attack(
    stego_rgb: Image.Image,
    plaintext: str,
    stego_key_bytes: bytes,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> JpegFragilityResult:
    """Kompres stego yang sudah ada menjadi JPEG lalu coba pulihkan pesan.

    Ukuran berkas dihitung dari bytes JPEG sebenarnya. Error pembuatan JPEG
    dicatat terpisah dari kegagalan membaca payload setelah JPEG terbentuk.
    """
    require_rgb_image(stego_rgb, "stego_rgb")
    _validate_quality(quality)

    try:
        jpeg_bytes = serialize_image(stego_rgb, JPEG_FORMAT, quality=quality)
        jpeg_round_trip = _decode_image(jpeg_bytes)
    except OSError as error:
        return JpegFragilityResult(
            quality=quality,
            jpeg_created=False,
            jpeg_size_bytes=0,
            extraction_succeeded=False,
            decryption_succeeded=False,
            recovered_plaintext=None,
            plaintext_matches=False,
            error_stage="jpeg_recompression",
            error_type=type(error).__name__,
            error_reason=str(error),
        )

    return _extraction_outcome(
        jpeg_round_trip,
        plaintext,
        stego_key_bytes,
        quality,
        # Ukuran diambil dari JPEG terenkode, bukan PNG dari gambar hasil dekode.
        jpeg_size_bytes=len(jpeg_bytes),
    )


def run_jpeg_quality_sweep(
    cover_rgb: Image.Image,
    plaintext: str,
    stego_key_bytes: bytes,
    qualities: tuple[int, ...] = (95, 85, 75, 50),
) -> list[JpegFragilityResult]:
    """Bandingkan beberapa kualitas JPEG dari satu stego yang dibuat sekali.

    Setiap kualitas dimulai dari piksel stego yang sama, sehingga hasilnya
    tidak dipengaruhi embedding ulang atau kompresi JPEG bertingkat.
    """
    require_rgb_image(cover_rgb, "cover_rgb")
    for quality in qualities:
        _validate_quality(quality)
    if not qualities:
        return []

    stego_rgb = embed_plaintext(cover_rgb, plaintext, stego_key_bytes)
    png_round_trip = _round_trip(stego_rgb, PNG_FORMAT, quality=None)
    return [
        run_jpeg_attack(png_round_trip, plaintext, stego_key_bytes, quality)
        for quality in qualities
    ]


def serialize_image(image_rgb: Image.Image, image_format: str, quality: int | None) -> bytes:
    """Simpan gambar ke buffer memori sesuai format dan kualitas yang diminta.

    Untuk pengujian JPEG, subsampling dinonaktifkan agar kanal warna tidak
    diperkecil oleh proses chroma subsampling.
    """
    buffer = io.BytesIO()
    save_options: dict[str, object] = {"format": image_format}
    if quality is not None:
        save_options["quality"] = quality
        save_options["subsampling"] = 0
    image_rgb.save(buffer, **save_options)
    return buffer.getvalue()


def _round_trip(
    image_rgb: Image.Image, image_format: str, quality: int | None
) -> Image.Image:
    """Simulasikan simpan dan buka kembali gambar melalui serialisasi serta dekode bytes."""
    encoded = serialize_image(image_rgb, image_format, quality)
    return _decode_image(encoded)


def _decode_image(encoded: bytes) -> Image.Image:
    """Buka bytes gambar, muat pikselnya, lalu kembalikan gambar RGB mandiri."""
    with Image.open(io.BytesIO(encoded)) as reopened:
        reopened.load()
        return reopened.convert("RGB")


def _extraction_outcome(
    jpeg_rgb: Image.Image,
    plaintext: str,
    stego_key_bytes: bytes,
    quality: int,
    jpeg_size_bytes: int,
) -> JpegFragilityResult:
    """Coba ekstraksi dari hasil JPEG dan catat apakah pesan cocok dengan pesan asal.

    ValueError dan InvalidTag dicatat sebagai kegagalan pemulihan; error lain
    diteruskan agar tidak disalahartikan sebagai keberhasilan serangan JPEG.
    """
    try:
        recovered = extract_plaintext(jpeg_rgb, stego_key_bytes)
    except (ValueError, InvalidTag) as error:
        return JpegFragilityResult(
            quality=quality,
            jpeg_created=True,
            jpeg_size_bytes=jpeg_size_bytes,
            extraction_succeeded=False,
            decryption_succeeded=False,
            recovered_plaintext=None,
            plaintext_matches=False,
            error_stage=_classify_failure(error),
            error_type=type(error).__name__,
            error_reason=str(error) or type(error).__name__,
        )

    return JpegFragilityResult(
        quality=quality,
        jpeg_created=True,
        jpeg_size_bytes=jpeg_size_bytes,
        extraction_succeeded=True,
        decryption_succeeded=True,
        recovered_plaintext=recovered,
        plaintext_matches=recovered == plaintext,
        error_stage=None,
        error_type=None,
        error_reason=None,
    )


def _classify_failure(error: Exception) -> str:
    """Bedakan kegagalan autentikasi GCM, penguraian payload, dan tahap ekstraksi lain."""
    error_name = type(error).__name__
    if error_name == "InvalidTag":
        return "aes_gcm_authentication"
    if isinstance(error, ValueError):
        return "payload_parse"
    return "extraction"


def _validate_quality(quality: int) -> None:
    """Pastikan kualitas JPEG berupa bilangan bulat 1 sampai 95 untuk pengujian lossy."""
    if isinstance(quality, bool) or not isinstance(quality, int):
        raise TypeError("quality must be an integer")
    if not 1 <= quality <= 95:
        raise ValueError("quality must be within 1..95 for a lossy JPEG attack")
