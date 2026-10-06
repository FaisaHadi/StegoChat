"""Pengujian regresi status per tahap, pemakaian stego yang sama, dan presisi metrik."""

from unittest.mock import Mock

import pandas as pd
import pytest
from cryptography.exceptions import InvalidTag
from PIL import Image

import laboratory
from analysis.jpeg_fragility import JpegFragilityResult
from analysis.metrics import calculate_mse, psnr_from_mse


@pytest.fixture
def experiment(monkeypatch):
    """Siapkan cover, stego, dan mock tahap untuk menyimulasikan berbagai hasil eksperimen."""
    cover = Image.new("RGB", (128, 128), (100, 101, 102))
    stego = cover.copy()
    stego.putpixel((0, 0), (101, 101, 102))
    embed = Mock(return_value=stego)
    extract = Mock(return_value="hello")
    jpeg = Mock(return_value=JpegFragilityResult(
        quality=85, jpeg_created=True, jpeg_size_bytes=123,
        extraction_succeeded=False, decryption_succeeded=False,
        recovered_plaintext=None, plaintext_matches=False,
        error_stage="payload_parse", error_type="ValueError",
        error_reason="invalid magic",
    ))
    monkeypatch.setattr(laboratory, "embed_plaintext", embed)
    monkeypatch.setattr(laboratory, "extract_plaintext", extract)
    monkeypatch.setattr(laboratory, "run_jpeg_attack", jpeg)
    return cover, stego, embed, extract, jpeg


def test_same_stego_is_used_for_extraction_metrics_and_jpeg(experiment):
    """Pastikan ekstraksi, metrik, dan JPEG memakai stego yang dibuat sekali."""
    cover, stego, embed, extract, jpeg = experiment
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    embed.assert_called_once_with(cover, "hello", b"test-key")
    extract.assert_called_once_with(stego, b"test-key")
    jpeg.assert_called_once_with(stego, "hello", b"test-key")
    assert result.mse == calculate_mse(cover, stego)
    assert result.embed_success and result.extract_success
    assert result.jpeg_attack_result == "destroyed"
    assert result.error is None


def test_embed_failure_skips_dependent_stages(experiment):
    """Pastikan embedding gagal menghentikan tahap yang memerlukan stego."""
    cover, _, embed, extract, jpeg = experiment
    embed.side_effect = RuntimeError("embed failed")
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    assert not result.embed_success and not result.extract_success
    assert result.mse is None and result.jpeg_attack_result is None
    assert result.error.startswith("embed:")
    extract.assert_not_called()
    jpeg.assert_not_called()


@pytest.mark.parametrize("failure", [InvalidTag(), ValueError("invalid header")])
def test_extraction_failure_keeps_embedding_and_independent_results(experiment, failure):
    """Pastikan ekstraksi gagal tidak menghapus sukses embedding atau hasil tahap mandiri."""
    cover, _, _, extract, jpeg = experiment
    extract.side_effect = failure
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    assert result.embed_success and not result.extract_success
    assert result.mse is not None and result.psnr is not None
    assert result.jpeg_attack_result == "destroyed"
    assert "extract:" in result.error and type(failure).__name__ in result.error
    jpeg.assert_called_once()


def test_plaintext_mismatch_is_recorded(experiment):
    """Pastikan pesan berbeda dari asalnya dicatat sebagai ketidakcocokan."""
    cover, _, _, extract, _ = experiment
    extract.return_value = "different message"
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    assert result.embed_success and not result.extract_success
    assert result.error == "extract: plaintext_mismatch"


@pytest.mark.parametrize("stage", ["calculate_mse", "psnr_from_mse"])
def test_metric_failure_preserves_recovery_and_runs_jpeg(experiment, monkeypatch, stage):
    """Pastikan metrik gagal tidak menghapus hasil pemulihan atau melewati pengujian JPEG."""
    cover, _, _, _, jpeg = experiment
    monkeypatch.setattr(laboratory, stage, Mock(side_effect=RuntimeError("metric failed")))
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    assert result.embed_success and result.extract_success
    assert result.psnr is None
    assert (result.mse is None) == (stage == "calculate_mse")
    assert result.error.startswith("metrics:")
    jpeg.assert_called_once()


def test_jpeg_exception_preserves_recovery_and_metrics(experiment):
    """Pastikan error JPEG tidak mengubah keberhasilan ekstraksi dan nilai metrik."""
    cover, stego, _, _, jpeg = experiment
    jpeg.side_effect = RuntimeError("codec failed")
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    assert result.embed_success and result.extract_success
    assert result.mse == calculate_mse(cover, stego)
    assert result.psnr == psnr_from_mse(result.mse)
    assert result.jpeg_attack_result == "error"
    assert result.error.startswith("jpeg:")


def test_failed_jpeg_creation_is_not_reported_as_payload_destruction(experiment):
    """Pastikan JPEG yang gagal dibuat dicatat sebagai error, bukan payload rusak."""
    from dataclasses import replace

    cover, _, _, _, jpeg = experiment
    jpeg.return_value = replace(jpeg.return_value, jpeg_created=False,
                                error_stage="jpeg_recompression")
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    assert result.embed_success and result.extract_success
    assert result.jpeg_attack_result == "error"
    assert result.error.startswith("jpeg:")


def test_multiple_stage_errors_are_preserved(experiment, monkeypatch):
    """Pastikan catatan memuat semua tahap yang gagal, bukan hanya error terakhir."""
    cover, _, _, extract, jpeg = experiment
    extract.side_effect = InvalidTag()
    monkeypatch.setattr(laboratory, "calculate_mse", Mock(side_effect=RuntimeError("metric")))
    jpeg.side_effect = RuntimeError("jpeg")
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    assert result.embed_success
    assert all(stage in result.error for stage in ("extract:", "metrics:", "jpeg:"))


def test_small_mse_retains_precision_in_result_and_xlsx(experiment, tmp_path):
    """Pastikan MSE kecil tetap presisi dalam hasil dan berkas Excel."""
    cover, stego, _, _, _ = experiment
    result = laboratory.run_experiment_case(cover, "hello", b"test-key")
    expected = calculate_mse(cover, stego)
    assert 0 < expected < 0.00005
    assert result.mse == expected
    assert result.psnr == psnr_from_mse(expected)
    destination = tmp_path / "results.xlsx"
    laboratory.export_results_to_xlsx([result], str(destination))
    restored = pd.read_excel(destination).iloc[0]
    assert restored["mse"] == pytest.approx(expected, rel=1e-12, abs=0)
    assert restored["psnr"] == pytest.approx(result.psnr, rel=1e-12)
