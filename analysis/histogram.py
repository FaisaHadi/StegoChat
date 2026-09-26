"""RGB histogram computation and cover/stego comparison for StegoChat V1."""

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
    """Per-channel 256-bin histograms of an RGB image."""

    red: np.ndarray
    green: np.ndarray
    blue: np.ndarray

    def for_channel(self, name: str) -> np.ndarray:
        """Return the histogram array for channel ``"R"``, ``"G"``, or ``"B"``."""
        if name == "R":
            return self.red
        if name == "G":
            return self.green
        if name == "B":
            return self.blue
        raise ValueError(f"unknown RGB channel name: {name!r}")

    def total(self) -> int:
        """Return the number of sampled channel values (width * height * 3)."""
        return int(self.red.sum() + self.green.sum() + self.blue.sum())


@dataclass(frozen=True)
class HistogramComparison:
    """Cover, stego, and per-bin absolute difference histograms."""

    cover: RgbHistogram
    stego: RgbHistogram
    difference: RgbHistogram

    def changed_bin_count(self) -> int:
        """Return how many of the 768 channel bins moved after embedding."""
        return sum(
            int(np.count_nonzero(self.difference.for_channel(name)))
            for name in CHANNEL_NAMES
        )


def compute_rgb_histogram(image: Image.Image) -> RgbHistogram:
    """Compute the actual per-channel histogram of an RGB image."""
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
    """Compare cover and stego RGB histograms for the laboratory report."""
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
    """Flatten a histogram into rows usable by an XLSX sheet or DataFrame."""
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
    counts = np.bincount(array[:, :, channel].ravel(), minlength=HISTOGRAM_BINS)
    return counts[:HISTOGRAM_BINS].astype(np.uint64)


def _abs_difference(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    return np.abs(first.astype(np.int64) - second.astype(np.int64)).astype(np.uint64)
