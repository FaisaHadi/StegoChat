"""Pengukuran perubahan cover menjadi stego melalui MSE dan PSNR.

Nilai ini mengukur kualitas citra, bukan membuktikan pesan tidak dapat dideteksi.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from analysis.image_utils import require_matching_rgb_images, to_rgb_array

MAX_PIXEL_VALUE = 255.0


def calculate_mse(cover_rgb: Image.Image, stego_rgb: Image.Image) -> float:
    """Hitung rata-rata kuadrat selisih seluruh kanal piksel cover dan stego.

    Kedua citra harus RGB dengan ukuran sama. MSE lebih kecil menunjukkan
    perubahan nilai piksel yang lebih kecil.
    """
    cover_array, stego_array = _as_matching_rgb_arrays(cover_rgb, stego_rgb)

    # Konversi sebelum pengurangan agar uint8 tidak melingkar saat selisih negatif.
    difference = cover_array.astype(np.float64) - stego_array.astype(np.float64)
    return float(np.mean(np.square(difference)))


def calculate_psnr(cover_rgb: Image.Image, stego_rgb: Image.Image) -> float:
    """Hitung PSNR dalam dB dari MSE kedua gambar RGB.

    PSNR lebih tinggi berarti selisih relatif lebih kecil; jika MSE nol,
    kedua gambar identik dan PSNR dikembalikan sebagai tak hingga.
    """
    return psnr_from_mse(calculate_mse(cover_rgb, stego_rgb))


def psnr_from_mse(mse_value: float) -> float:
    """Terapkan rumus PSNR 8-bit: 10 log10(255 kuadrat / MSE).

    Tangani MSE nol sebelum pembagian agar hasilnya tak hingga tanpa error.
    """
    _validate_mse(mse_value)

    if mse_value == 0.0:
        return float("inf")

    return 10.0 * math.log10((MAX_PIXEL_VALUE**2) / mse_value)


def _as_matching_rgb_arrays(
    cover_rgb: Image.Image, stego_rgb: Image.Image
) -> tuple[np.ndarray, np.ndarray]:
    """Validasi dimensi dan mode kedua gambar, lalu ambil array piksel untuk perhitungan."""
    require_matching_rgb_images(cover_rgb, stego_rgb, "cover_rgb", "stego_rgb")
    return to_rgb_array(cover_rgb), to_rgb_array(stego_rgb)


def _validate_mse(mse_value: float) -> None:
    """Tolak MSE bukan angka atau bernilai negatif sebelum menghitung PSNR."""
    if isinstance(mse_value, bool) or not isinstance(mse_value, (int, float)):
        raise TypeError("mse_value must be a number")
    if mse_value < 0:
        raise ValueError("mse_value must not be negative")
