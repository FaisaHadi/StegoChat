"""Pengujian presisi p-value dan format tampilannya pada tabel Chi-Square."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from analysis.chi_square import (
    ChiSquareChannelResult,
    ChiSquareReport,
    chi_square_report_to_rows,
    compute_chi_square_test,
    format_p_value_for_display,
)


def test_report_rows_preserve_unrounded_p_value() -> None:
    """Pastikan baris hasil mempertahankan p-value asli tanpa pembulatan."""
    p_value = 1.23456789e-12
    channel = ChiSquareChannelResult("R", 12.5, 127, p_value)
    report = ChiSquareReport(channel, channel, channel)

    rows = chi_square_report_to_rows(report)

    assert rows[0]["p_value"] == p_value


def test_tiny_p_values_are_shown_as_an_upper_bound() -> None:
    """Pastikan p-value sangat kecil tampil sebagai batas atas, bukan nol mutlak."""
    assert format_p_value_for_display(0.0) == "< 0,000001"
    assert format_p_value_for_display(9.99e-7) == "< 0,000001"


def test_p_values_at_or_above_display_threshold_remain_numeric_text() -> None:
    """Pastikan nilai pada atau di atas ambang tampil sebagai teks angka dengan koma desimal."""
    assert format_p_value_for_display(1e-6) == "1e-06"
    assert format_p_value_for_display(0.123456) == "0,123456"


def _image_with_known_pairs() -> Image.Image:
    """Create RGB channels with balanced and skewed pairs-of-values."""
    channel_values = (
        [20] * 128 + [21] * 128,
        [40] * 255 + [41],
        [80] * 128 + [81] * 128,
    )
    pixels = np.column_stack(
        [np.asarray(values, dtype=np.uint8) for values in channel_values]
    )
    return Image.fromarray(pixels.reshape(16, 16, 3))


def test_compute_chi_square_detects_balanced_pairs_per_rgb_channel() -> None:
    """Check the statistical result for channels with known pair frequencies."""
    report = compute_chi_square_test(_image_with_known_pairs())

    assert [report.for_channel(name).channel for name in ("R", "G", "B")] == [
        "R",
        "G",
        "B",
    ]
    assert report.red.p_value == pytest.approx(1.0)
    assert report.green.p_value < 0.5
    assert report.blue.p_value == pytest.approx(1.0)
    assert report.suspected_channel_count() == 2


def test_compute_chi_square_rejects_non_rgb_image() -> None:
    """Chi-square RGB analysis must reject grayscale input."""
    with pytest.raises(ValueError):
        compute_chi_square_test(Image.new("L", (16, 16), color=20))