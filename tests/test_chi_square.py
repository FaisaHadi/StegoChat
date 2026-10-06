"""Pengujian presisi p-value dan format tampilannya pada tabel Chi-Square."""

from __future__ import annotations

from analysis.chi_square import (
    ChiSquareChannelResult,
    ChiSquareReport,
    chi_square_report_to_rows,
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
