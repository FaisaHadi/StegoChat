"""Shared RGB image helpers for the StegoChat analysis layer."""

from __future__ import annotations

import numpy as np
from PIL import Image

RGB_MODE = "RGB"
RGB_CHANNELS = 3


def require_rgb_image(image: Image.Image, name: str) -> None:
    """Raise if ``image`` is not a Pillow image in RGB mode."""
    if not isinstance(image, Image.Image):
        raise TypeError(f"{name} must be a Pillow Image")
    if image.mode != RGB_MODE:
        raise ValueError(f"{name} must use RGB mode")


def require_matching_rgb_images(
    first: Image.Image, second: Image.Image, first_name: str, second_name: str
) -> None:
    """Raise unless both images are RGB and share identical dimensions."""
    require_rgb_image(first, first_name)
    require_rgb_image(second, second_name)
    if first.size != second.size:
        raise ValueError(
            f"{first_name} and {second_name} must have identical dimensions"
        )


def to_rgb_array(image: Image.Image) -> np.ndarray:
    """Return an ``(height, width, 3)`` ``uint8`` array of actual pixels."""
    return np.asarray(image, dtype=np.uint8)


def to_grayscale_array(image: Image.Image) -> np.ndarray:
    """Return a 2-D ``uint8`` luminance array without modifying ``image``."""
    converted = image.convert("L")
    return np.asarray(converted, dtype=np.uint8)


def assert_uint8_array(array: np.ndarray, name: str) -> None:
    """Guard helper for data that must stay inside the 8-bit pixel range."""
    if array.dtype != np.uint8:
        raise TypeError(f"{name} must use the uint8 dtype")
    if array.size and (array.min() < 0 or array.max() > 255):
        raise ValueError(f"{name} values must be within 0..255")
