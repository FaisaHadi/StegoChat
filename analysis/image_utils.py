"""Validasi dan konversi gambar yang dipakai bersama oleh modul analisis."""

from __future__ import annotations

import numpy as np
from PIL import Image

RGB_MODE = "RGB"
RGB_CHANNELS = 3


def require_rgb_image(image: Image.Image, name: str) -> None:
    """Pastikan masukan berupa gambar Pillow bermode RGB sebelum kanal dianalisis."""
    if not isinstance(image, Image.Image):
        raise TypeError(f"{name} must be a Pillow Image")
    if image.mode != RGB_MODE:
        raise ValueError(f"{name} must use RGB mode")


def require_matching_rgb_images(
    first: Image.Image, second: Image.Image, first_name: str, second_name: str
) -> None:
    """Pastikan kedua gambar RGB memiliki dimensi sama agar piksel sepadan dapat dibandingkan."""
    require_rgb_image(first, first_name)
    require_rgb_image(second, second_name)
    if first.size != second.size:
        raise ValueError(
            f"{first_name} and {second_name} must have identical dimensions"
        )


def to_rgb_array(image: Image.Image) -> np.ndarray:
    """Ubah piksel gambar menjadi array uint8 berbentuk tinggi x lebar x 3."""
    return np.asarray(image, dtype=np.uint8)


def to_grayscale_array(image: Image.Image) -> np.ndarray:
    """Konversi gambar menjadi array luminans dua dimensi tanpa mengubah gambar asal."""
    converted = image.convert("L")
    return np.asarray(converted, dtype=np.uint8)


def assert_uint8_array(array: np.ndarray, name: str) -> None:
    """Pastikan array memakai uint8 dan nilai piksel berada pada rentang 0 sampai 255."""
    if array.dtype != np.uint8:
        raise TypeError(f"{name} must use the uint8 dtype")
    if array.size and (array.min() < 0 or array.max() > 255):
        raise ValueError(f"{name} values must be within 0..255")
