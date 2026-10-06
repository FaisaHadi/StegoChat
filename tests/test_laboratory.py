"""Pengujian runner laboratorium, pembuatan dataset, dan ekspor Excel."""

from __future__ import annotations

import os
import secrets
import tempfile

import pytest

import laboratory

from laboratory import (
    ExperimentResult,
    export_results_to_xlsx,
    generate_test_dataset,
    run_experiment_case,
    run_laboratory,
)


def test_experiment_result_dataclass() -> None:
    """Pastikan seluruh field hasil eksperimen menyimpan nilai yang diberikan."""
    result = ExperimentResult(
        image_name="test.png",
        width=100,
        height=100,
        capacity_bits=30000,
        capacity_bytes=3750,
        message_size_bytes=10,
        payload_size_bytes=40,
        capacity_utilization_percent=0.13,
        mse=1.2345,
        psnr=35.67,
        embed_success=True,
        extract_success=True,
        jpeg_attack_result="survived",
        error=None,
    )

    assert result.image_name == "test.png"
    assert result.width == 100
    assert result.height == 100
    assert result.capacity_bits == 30000
    assert result.capacity_bytes == 3750
    assert result.message_size_bytes == 10
    assert result.payload_size_bytes == 40
    assert result.capacity_utilization_percent == 0.13
    assert result.mse == 1.2345
    assert result.psnr == 35.67
    assert result.embed_success is True
    assert result.extract_success is True
    assert result.jpeg_attack_result == "survived"
    assert result.error is None


def test_run_experiment_case_success() -> None:
    """Pastikan satu kasus uji mencatat embedding, ekstraksi, metrik, dan hasil JPEG."""
    from PIL import Image

    # Pakai cover sederhana untuk menguji alur tanpa bergantung pada berkas luar.
    cover = Image.new("RGB", (100, 100), color=(100, 101, 102))
    message = "Test message"
    stego_key = b"test-key"

    result = run_experiment_case(cover, message, stego_key)

    assert result.image_name == ""
    assert result.width == 100
    assert result.height == 100
    assert result.embed_success is True
    assert result.extract_success is True
    assert result.mse is not None
    assert result.psnr is not None
    assert result.jpeg_attack_result in ("survived", "destroyed")
    assert result.error is None


def test_run_experiment_case_capacity_exceeded() -> None:
    """Pastikan pesan melebihi kapasitas dicatat sebagai gagal tanpa metrik."""
    from PIL import Image

    # Gunakan gambar kecil agar batas kapasitas mudah dilampaui.
    cover = Image.new("RGB", (10, 10), color=(100, 101, 102))
    # Pesan ini sengaja melebihi kapasitas gambar 10x10.
    message = "X" * 1000
    stego_key = b"test-key"

    result = run_experiment_case(cover, message, stego_key)

    assert result.embed_success is False
    assert result.extract_success is False
    assert result.error == "capacity_exceeded"
    assert result.mse is None
    assert result.psnr is None


def test_run_laboratory() -> None:
    """Pastikan runner menghasilkan satu hasil untuk setiap kombinasi gambar dan pesan."""
    # Siapkan citra uji di folder sementara.
    image_paths = generate_test_dataset()

    # Dua ukuran pesan cukup untuk menguji kombinasi runner dengan cepat.
    message_sizes = [10, 50]
    stego_key = "test-key"

    results = run_laboratory(
        image_paths=image_paths[:2],
        message_sizes=message_sizes,
        stego_key=stego_key,
    )

    assert len(results) == 4  # Dua citra dikalikan dua ukuran pesan menghasilkan empat kasus.

    for result in results:
        assert isinstance(result, ExperimentResult)
        assert result.image_name != ""
        assert result.width > 0
        assert result.height > 0


def test_export_results_to_xlsx() -> None:
    """Pastikan hasil dapat diekspor dan dibaca kembali sebagai tabel Excel."""
    results = [
        ExperimentResult(
            image_name="test1.png",
            width=100,
            height=100,
            capacity_bits=30000,
            capacity_bytes=3750,
            message_size_bytes=10,
            payload_size_bytes=40,
            capacity_utilization_percent=0.13,
            mse=1.2345,
            psnr=35.67,
            embed_success=True,
            extract_success=True,
            jpeg_attack_result="survived",
            error=None,
        ),
        ExperimentResult(
            image_name="test2.png",
            width=200,
            height=200,
            capacity_bits=120000,
            capacity_bytes=15000,
            message_size_bytes=50,
            payload_size_bytes=70,
            capacity_utilization_percent=0.06,
            mse=2.3456,
            psnr=33.45,
            embed_success=True,
            extract_success=True,
            jpeg_attack_result="destroyed",
            error=None,
        ),
    ]

    with tempfile.NamedTemporaryFile(
        suffix=".xlsx", delete=False
    ) as tmp_file:
        output_path = tmp_file.name

    try:
        export_results_to_xlsx(results, output_path)

        # Pastikan berkas Excel benar-benar terbentuk.
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


def test_generate_test_dataset() -> None:
    """Pastikan dataset yang dibuat tersedia dan dapat dibuka sebagai gambar RGB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        image_paths = generate_test_dataset(output_dir=tmpdir)

        assert len(image_paths) == 5

        for path in image_paths:
            assert os.path.exists(path)
            assert path.endswith(".png")

            # Pastikan setiap berkas dataset dapat dibuka sebagai gambar.
            from PIL import Image

            with Image.open(path) as img:
                assert img.mode == "RGB"


def test_laboratory_with_nonexistent_image() -> None:
    """Pastikan berkas gambar yang tidak ditemukan ditangani tanpa menghentikan runner."""
    image_paths = ["nonexistent.png"]
    message_sizes = [10]
    stego_key = "test-key"

    results = run_laboratory(
        image_paths=image_paths,
        message_sizes=message_sizes,
        stego_key=stego_key,
    )

    # Berkas yang hilang harus ditangani tanpa menghasilkan kasus uji palsu.
    assert len(results) == 0


def test_default_laboratory_generates_temporary_keys(monkeypatch):
    """Pastikan setiap batch tanpa kunci memakai kunci acak, bukan nilai bawaan tetap."""
    captured = []
    monkeypatch.setattr(laboratory, "generate_test_dataset", lambda: [])

    def capture_batch(**kwargs):
        captured.append(kwargs["stego_key"])
        return []

    monkeypatch.setattr(laboratory, "run_laboratory", capture_batch)
    laboratory.run_default_laboratory()
    laboratory.run_default_laboratory()
    assert all(len(key) == 64 for key in captured)
    assert captured[0] != captured[1]


def test_default_laboratory_preserves_provided_key(monkeypatch):
    """Pastikan kunci masukan tetap dipakai dan tidak diganti dengan kunci otomatis."""
    provided_key = secrets.token_hex(32)
    captured = []
    monkeypatch.setattr(laboratory, "generate_test_dataset", lambda: [])

    def capture_batch(**kwargs):
        captured.append(kwargs["stego_key"])
        return []

    monkeypatch.setattr(laboratory, "run_laboratory", capture_batch)
    laboratory.run_default_laboratory(stego_key=provided_key)
    assert captured == [provided_key]
