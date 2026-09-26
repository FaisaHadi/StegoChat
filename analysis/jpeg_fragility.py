"""JPEG recompression fragility experiment for StegoChat V1.

LSB steganography stores payload bits in the least significant bit of each
selected channel byte. JPEG is lossy, so a JPEG-compressed copy of a stego
image rewrites those low-order bits and the payload is expected to be
destroyed. This module measures that effect on real image data instead of
asserting it.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

from analysis.image_utils import require_rgb_image
from stegochat.core import embed_plaintext, extract_plaintext

DEFAULT_JPEG_QUALITY = 85
JPEG_FORMAT = "JPEG"
PNG_FORMAT = "PNG"


@dataclass(frozen=True)
class JpegFragilityResult:
    """Observed outcome of one JPEG recompression attack on a stego image."""

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
        """True when the attack prevented recovery of the original message."""
        return not (self.extraction_succeeded and self.plaintext_matches)


def run_jpeg_fragility_test(
    cover_rgb: Image.Image,
    plaintext: str,
    stego_key_bytes: bytes,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> JpegFragilityResult:
    """Embed, recompress through JPEG, and attempt to extract the message.

    The experiment never fabricates an outcome: every field describes what the
    real embed/extract pipeline reported for this cover image.
    """
    require_rgb_image(cover_rgb, "cover_rgb")
    _validate_quality(quality)

    stego_rgb = embed_plaintext(cover_rgb, plaintext, stego_key_bytes)
    png_round_trip = _round_trip(stego_rgb, PNG_FORMAT, quality=None)

    try:
        jpeg_round_trip = _round_trip(png_round_trip, JPEG_FORMAT, quality=quality)
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

    return _extraction_outcome(jpeg_round_trip, plaintext, stego_key_bytes, quality)


def run_jpeg_quality_sweep(
    cover_rgb: Image.Image,
    plaintext: str,
    stego_key_bytes: bytes,
    qualities: tuple[int, ...] = (95, 85, 75, 50),
) -> list[JpegFragilityResult]:
    """Repeat the fragility test across several JPEG quality levels."""
    return [
        run_jpeg_fragility_test(cover_rgb, plaintext, stego_key_bytes, quality)
        for quality in qualities
    ]


def serialize_image(image_rgb: Image.Image, image_format: str, quality: int | None) -> bytes:
    """Encode an RGB image into bytes using the given Pillow format."""
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
    encoded = serialize_image(image_rgb, image_format, quality)
    with Image.open(io.BytesIO(encoded)) as reopened:
        reopened.load()
        return reopened.convert("RGB")


def _extraction_outcome(
    jpeg_rgb: Image.Image,
    plaintext: str,
    stego_key_bytes: bytes,
    quality: int,
) -> JpegFragilityResult:
    jpeg_size = len(
        serialize_image(jpeg_rgb, PNG_FORMAT, quality=None)
    )
    try:
        recovered = extract_plaintext(jpeg_rgb, stego_key_bytes)
    except Exception as error:  # noqa: BLE001 - outcome is recorded, not hidden
        return JpegFragilityResult(
            quality=quality,
            jpeg_created=True,
            jpeg_size_bytes=jpeg_size,
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
        jpeg_size_bytes=jpeg_size,
        extraction_succeeded=True,
        decryption_succeeded=True,
        recovered_plaintext=recovered,
        plaintext_matches=recovered == plaintext,
        error_stage=None,
        error_type=None,
        error_reason=None,
    )


def _classify_failure(error: Exception) -> str:
    error_name = type(error).__name__
    if error_name == "InvalidTag":
        return "aes_gcm_authentication"
    if isinstance(error, ValueError):
        return "payload_parse"
    return "extraction"


def _validate_quality(quality: int) -> None:
    if isinstance(quality, bool) or not isinstance(quality, int):
        raise TypeError("quality must be an integer")
    if not 1 <= quality <= 95:
        raise ValueError("quality must be within 1..95 for a lossy JPEG attack")
