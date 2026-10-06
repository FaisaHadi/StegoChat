"""Histogram intensitas RGB dan perbandingan distribusi cover dengan stego."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from analysis.image_utils import (
    require_matching_rgb_images,
    require_rgb_image,
    to_rgb_array,
)

HISTOGRAM_BINS = 256
CHANNEL_NAMES: tuple[str, str, str] = ("R", "G", "B")


@dataclass(frozen=True)
class RgbHistogram:
    """Wadah frekuensi 256 tingkat intensitas untuk masing-masing kanal RGB."""

    red: np.ndarray
    green: np.ndarray
    blue: np.ndarray

    def for_channel(self, name: str) -> np.ndarray:
        """Ambil array histogram kanal R, G, atau B; tolak nama kanal lain."""
        if name == "R":
            return self.red
        if name == "G":
            return self.green
        if name == "B":
            return self.blue
        raise ValueError(f"unknown RGB channel name: {name!r}")

    def total(self) -> int:
        """Jumlahkan seluruh frekuensi kanal; totalnya sama dengan lebar x tinggi x 3."""
        return int(self.red.sum() + self.green.sum() + self.blue.sum())


@dataclass(frozen=True)
class HistogramComparison:
    """Wadah histogram cover, stego, dan selisih absolut frekuensi tiap bin."""

    cover: RgbHistogram
    stego: RgbHistogram
    difference: RgbHistogram

    def changed_bin_count(self) -> int:
        """Hitung bin yang frekuensinya berubah dari total 768 bin RGB.

        Satu bin mewakili satu nilai intensitas pada satu kanal, bukan satu piksel.
        """
        return sum(
            int(np.count_nonzero(self.difference.for_channel(name)))
            for name in CHANNEL_NAMES
        )


def compute_rgb_histogram(image: Image.Image) -> RgbHistogram:
    """Hitung frekuensi intensitas 0 sampai 255 pada setiap kanal gambar RGB."""
    require_rgb_image(image, "image")
    array = to_rgb_array(image)
    return RgbHistogram(
        red=_channel_histogram(array, 0),
        green=_channel_histogram(array, 1),
        blue=_channel_histogram(array, 2),
    )


def compare_rgb_histograms(
    cover_rgb: Image.Image, stego_rgb: Image.Image
) -> HistogramComparison:
    """Hitung histogram kedua citra dan selisih absolutnya untuk mengukur perubahan distribusi."""
    require_matching_rgb_images(cover_rgb, stego_rgb, "cover_rgb", "stego_rgb")

    cover_histogram = compute_rgb_histogram(cover_rgb)
    stego_histogram = compute_rgb_histogram(stego_rgb)
    difference = RgbHistogram(
        red=_abs_difference(cover_histogram.red, stego_histogram.red),
        green=_abs_difference(cover_histogram.green, stego_histogram.green),
        blue=_abs_difference(cover_histogram.blue, stego_histogram.blue),
    )
    return HistogramComparison(
        cover=cover_histogram,
        stego=stego_histogram,
        difference=difference,
    )


def histogram_to_rows(histogram: RgbHistogram) -> list[dict[str, int]]:
    """Susun intensitas dan frekuensi RGB menjadi baris tabel untuk DataFrame atau ekspor."""
    return [
        {
            "intensity": intensity,
            "R": int(histogram.red[intensity]),
            "G": int(histogram.green[intensity]),
            "B": int(histogram.blue[intensity]),
        }
        for intensity in range(HISTOGRAM_BINS)
    ]


def _channel_histogram(array: np.ndarray, channel: int) -> np.ndarray:
    """Ratakan satu kanal lalu hitung frekuensi setiap intensitas dengan bincount."""
    counts = np.bincount(array[:, :, channel].ravel(), minlength=HISTOGRAM_BINS)
    return counts[:HISTOGRAM_BINS].astype(np.uint64)


def _abs_difference(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Hitung selisih absolut histogram memakai int64 agar pengurangan tidak melingkar."""
    return np.abs(first.astype(np.int64) - second.astype(np.int64)).astype(np.uint64)
