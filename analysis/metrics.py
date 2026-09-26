"""MSE and PSNR image-quality metrics for StegoChat V1.

These metrics quantify how much an LSB embedding changed the cover image.
They do not prove that embedding is undetectable or resistant to steganalysis.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from analysis.image_utils import require_matching_rgb_images, to_rgb_array

MAX_PIXEL_VALUE = 255.0


def calculate_mse(cover_rgb: Image.Image, stego_rgb: Image.Image) -> float:
    """Return the mean squared error between two same-size RGB images.

    ``MSE = (1 / (W * H * C)) * sum((cover - stego) ** 2)`` over all pixel
    channels, evaluated on the actual 8-bit pixel data.
    """
    cover_array, stego_array = _as_matching_rgb_arrays(cover_rgb, stego_rgb)

    difference = cover_array.astype(np.float64) - stego_array.astype(np.float64)
    return float(np.mean(np.square(difference)))


def calculate_psnr(cover_rgb: Image.Image, stego_rgb: Image.Image) -> float:
    """Return the peak signal-to-noise ratio of two RGB images in decibels.

    A zero MSE means the images are identical; PSNR is then mathematically
    infinite, which is reported as ``float("inf")`` rather than raising.
    """
    return psnr_from_mse(calculate_mse(cover_rgb, stego_rgb))


def psnr_from_mse(mse_value: float) -> float:
    """Apply the 8-bit PSNR formula to an already-computed MSE value."""
    _validate_mse(mse_value)

    if mse_value == 0.0:
        return float("inf")

    return 10.0 * math.log10((MAX_PIXEL_VALUE**2) / mse_value)


def _as_matching_rgb_arrays(
    cover_rgb: Image.Image, stego_rgb: Image.Image
) -> tuple[np.ndarray, np.ndarray]:
    require_matching_rgb_images(cover_rgb, stego_rgb, "cover_rgb", "stego_rgb")
    return to_rgb_array(cover_rgb), to_rgb_array(stego_rgb)


def _validate_mse(mse_value: float) -> None:
    if isinstance(mse_value, bool) or not isinstance(mse_value, (int, float)):
        raise TypeError("mse_value must be a number")
    if mse_value < 0:
        raise ValueError("mse_value must not be negative")
