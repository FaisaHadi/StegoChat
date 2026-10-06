"""Steganalisis Pairs-of-Values pada satu gambar melalui statistik Chi-Square per kanal."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy import stats

from analysis.image_utils import require_rgb_image, to_rgb_array

CHANNEL_NAMES: tuple[str, str, str] = ("R", "G", "B")
PAIR_COUNT = 128  # 256 intensitas dikelompokkan menjadi pasangan (2i, 2i+1).
DEFAULT_SUSPICION_THRESHOLD = 0.5
P_VALUE_DISPLAY_THRESHOLD = 1e-6


@dataclass(frozen=True)
class ChiSquareChannelResult:
    """Wadah statistik Chi-Square, derajat kebebasan, dan p-value satu kanal."""

    channel: str
    chi_square_statistic: float
    degrees_of_freedom: int
    p_value: float

    def likely_contains_hidden_data(
        self, threshold: float = DEFAULT_SUSPICION_THRESHOLD
    ) -> bool:
        """Tandai kanal sebagai mencurigakan ketika p-value melewati ambang.

        Nilai tinggi menunjukkan frekuensi pasangan genap-ganjil mendekati sama,
        sesuai pola yang dapat muncul pada LSB replacement. Ini indikasi
        statistik, bukan bukti pasti keberadaan atau ketiadaan pesan.
        """
        return self.p_value > threshold


@dataclass(frozen=True)
class ChiSquareReport:
    """Wadah hasil uji terpisah untuk kanal merah, hijau, dan biru."""

    red: ChiSquareChannelResult
    green: ChiSquareChannelResult
    blue: ChiSquareChannelResult

    def for_channel(self, name: str) -> ChiSquareChannelResult:
        """Ambil hasil Chi-Square kanal R, G, atau B; tolak nama kanal lain."""
        if name == "R":
            return self.red
        if name == "G":
            return self.green
        if name == "B":
            return self.blue
        raise ValueError(f"unknown RGB channel name: {name!r}")

    def suspected_channel_count(
        self, threshold: float = DEFAULT_SUSPICION_THRESHOLD
    ) -> int:
        """Hitung kanal dengan p-value di atas ambang untuk membantu interpretasi aplikasi."""
        return sum(
            1
            for name in CHANNEL_NAMES
            if self.for_channel(name).likely_contains_hidden_data(threshold)
        )


def compute_chi_square_test(image: Image.Image) -> ChiSquareReport:
    """Uji keseimbangan pasangan intensitas genap-ganjil pada tiap kanal RGB.

    Hanya satu citra diperlukan, sehingga pengujian dapat dilakukan tanpa
    cover asli. Hasil yang tidak mencurigakan tetap tidak menjamin bebas pesan.
    """
    require_rgb_image(image, "image")
    array = to_rgb_array(image)
    return ChiSquareReport(
        red=_channel_chi_square(array, 0, "R"),
        green=_channel_chi_square(array, 1, "G"),
        blue=_channel_chi_square(array, 2, "B"),
    )


def chi_square_report_to_rows(
    report: ChiSquareReport,
) -> list[dict[str, float | str | int | bool]]:
    """Susun hasil tiap kanal menjadi baris tabel; pertahankan p-value asli untuk analisis."""
    return [
        {
            "channel": name,
            "chi_square_statistic": round(result.chi_square_statistic, 4),
            "degrees_of_freedom": result.degrees_of_freedom,
            "p_value": result.p_value,
            "likely_contains_hidden_data": result.likely_contains_hidden_data(),
        }
        for name in CHANNEL_NAMES
        for result in [report.for_channel(name)]
    ]


def format_p_value_for_display(p_value: float) -> str:
    """Tampilkan p-value sangat kecil sebagai batas atas, agar tidak tampak sebagai nol mutlak."""
    if p_value < P_VALUE_DISPLAY_THRESHOLD:
        return "< 0,000001"
    return f"{p_value:.6g}".replace(".", ",")


def _channel_chi_square(
    array: np.ndarray, channel: int, name: str
) -> ChiSquareChannelResult:
    """Hitung Chi-Square dari 128 pasangan (0,1), (2,3), sampai (254,255).

    Harapan tiap anggota pasangan adalah setengah total frekuensinya.
    Pasangan kosong dilewati; p-value dihitung dengan survival function
    distribusi Chi-Square sesuai derajat kebebasan yang dipakai proyek.
    """
    counts = np.bincount(array[:, :, channel].ravel(), minlength=256)[:256].astype(
        np.float64
    )

    chi_square_sum = 0.0
    degrees_of_freedom = 0
    for pair_index in range(PAIR_COUNT):
        even_count = counts[2 * pair_index]
        odd_count = counts[2 * pair_index + 1]
        # Uji membandingkan frekuensi genap dengan harapan pasangan yang seimbang.
        expected = (even_count + odd_count) / 2.0
        if expected == 0:
            continue
        chi_square_sum += ((even_count - expected) ** 2) / expected
        degrees_of_freedom += 1

    degrees_of_freedom = max(degrees_of_freedom - 1, 1)
    # Survival function menghitung ekor kanan langsung, tanpa pengurangan 1 - CDF.
    p_value = float(stats.chi2.sf(chi_square_sum, degrees_of_freedom))

    return ChiSquareChannelResult(
        channel=name,
        chi_square_statistic=float(chi_square_sum),
        degrees_of_freedom=degrees_of_freedom,
        p_value=p_value,
    )
