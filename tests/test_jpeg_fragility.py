"""Pengujian sumber stego tunggal, ukuran bytes JPEG, dan penanganan error kompresi."""

import io
from unittest.mock import Mock

import pytest
from PIL import Image

import analysis.jpeg_fragility as jpeg
from stegochat.core import embed_plaintext


def test_sweep_embeds_once_and_encodes_each_quality_from_same_pixels(monkeypatch):
    """Pastikan sweep mengompres piksel stego yang sama dan melaporkan ukuran JPEG nyata."""
    cover = Image.new("RGB", (64, 64), (100, 101, 102))
    embed = Mock(wraps=embed_plaintext)
    monkeypatch.setattr(jpeg, "embed_plaintext", embed)
    serialize = jpeg.serialize_image
    encodings = []

    def record(image, image_format, quality):
        """Catat piksel asal, kualitas, dan bytes keluaran setiap enkode JPEG untuk dibandingkan."""
        encoded = serialize(image, image_format, quality)
        if image_format == "JPEG":
            encodings.append((image.tobytes(), quality, encoded))
        return encoded

    monkeypatch.setattr(jpeg, "serialize_image", record)
    results = jpeg.run_jpeg_quality_sweep(cover, "hello", b"test-key", (95, 85, 50))
    embed.assert_called_once()
    assert len(encodings) == 3
    assert len({pixels for pixels, _, _ in encodings}) == 1
    assert [result.quality for result in results] == [95, 85, 50]
    for result, (_, _, encoded) in zip(results, encodings):
        assert result.jpeg_size_bytes == len(encoded)
        with Image.open(io.BytesIO(encoded)) as image:
            assert image.format == "JPEG"


def test_attack_accepts_existing_stego_without_modifying_or_reembedding(monkeypatch):
    """Pastikan serangan menerima stego yang sudah ada tanpa mengubah atau menyisipkan ulang."""
    stego = embed_plaintext(Image.new("RGB", (64, 64), (100, 101, 102)),
                            "hello", b"test-key")
    original = stego.tobytes()
    embed = Mock(side_effect=AssertionError("must not embed"))
    monkeypatch.setattr(jpeg, "embed_plaintext", embed)
    result = jpeg.run_jpeg_attack(stego, "hello", b"test-key")
    assert result.jpeg_created
    assert result.jpeg_size_bytes == len(jpeg.serialize_image(stego, "JPEG", 85))
    assert stego.tobytes() == original
    embed.assert_not_called()


def test_recompression_failure_is_recorded(monkeypatch):
    """Pastikan kegagalan kompresi dicatat sebagai JPEG tidak terbentuk."""
    monkeypatch.setattr(jpeg, "serialize_image", Mock(side_effect=OSError("codec failed")))
    result = jpeg.run_jpeg_attack(Image.new("RGB", (64, 64)), "hello", b"key")
    assert not result.jpeg_created
    assert result.jpeg_size_bytes == 0
    assert result.error_stage == "jpeg_recompression"


def test_unexpected_extraction_error_is_not_treated_as_a_successful_attack(monkeypatch):
    """Pastikan error internal ekstraksi diteruskan dan tidak dianggap payload rusak."""
    monkeypatch.setattr(jpeg, "extract_plaintext", Mock(side_effect=RuntimeError("bug")))
    with pytest.raises(RuntimeError, match="bug"):
        jpeg.run_jpeg_attack(Image.new("RGB", (64, 64)), "hello", b"key")


@pytest.mark.parametrize("qualities", [(), (85, 100)])
def test_empty_or_invalid_sweep_does_not_embed(monkeypatch, qualities):
    """Pastikan kualitas kosong atau tidak valid tidak memulai embedding."""
    embed = Mock()
    monkeypatch.setattr(jpeg, "embed_plaintext", embed)
    cover = Image.new("RGB", (64, 64))
    if qualities:
        with pytest.raises(ValueError):
            jpeg.run_jpeg_quality_sweep(cover, "hello", b"key", qualities)
    else:
        assert jpeg.run_jpeg_quality_sweep(cover, "hello", b"key", qualities) == []
    embed.assert_not_called()
