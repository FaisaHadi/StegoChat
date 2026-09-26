"""LSB bit-plane extraction and cover/stego comparison for StegoChat V1.

The least significant bit plane of an 8-bit channel is a binary image whose
pixels are the channel's LSB. StegoChat writes payload bits into randomly
selected channel LSBs, so comparing cover and stego planes shows exactly which
channel LSBs were overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from analysis.image_utils import (
    require_matching_rgb_images,
    require_rgb_image,
    to_rgb_array,
)

LSB_MASK = 0b0000_0001
PLANE_OFF = 0
PLANE_ON = 255
CHANNEL_NAMES: tuple[str, str, str] = ("R", "G", "B")


@dataclass(frozen=True)
class LsbBitPlane:
    """One black/white LSB bit plane per RGB channel."""

    red: np.ndarray
    green: np.ndarray
    blue: np.ndarray

    def for_channel(self, name: str) -> np.ndarray:
        """Return the 2-D bit plane for channel ``"R"``, ``"G"``, or ``"B"``."""
        if name == "R":
            return self.red
        if name == "G":
            return self.green
        if name == "B":
            return self.blue
        raise ValueError(f"unknown RGB channel name: {name!r}")

    def stacked(self) -> np.ndarray:
        """Return an ``(height, width, 3)`` array of the three planes."""
        return np.stack([self.red, self.green, self.blue], axis=-1).astype(np.uint8)


@dataclass(frozen=True)
class LsbBitPlaneComparison:
    """Cover/stego bit planes plus the map of changed channel LSBs."""

    cover: LsbBitPlane
    stego: LsbBitPlane
    channel_change_mask: np.ndarray
    changed_channel_count: int

    def changed_pixel_count(self) -> int:
        """Return how many pixels had at least one channel LSB overwritten."""
        return int(np.count_nonzero(self.channel_change_mask))


def extract_lsb_bit_plane(image_rgb: Image.Image) -> LsbBitPlane:
    """Return the actual per-channel LSB bit plane of an RGB image."""
    require_rgb_image(image_rgb, "image_rgb")
    array = to_rgb_array(image_rgb)
    return LsbBitPlane(
        red=_lsb_plane(array, 0),
        green=_lsb_plane(array, 1),
        blue=_lsb_plane(array, 2),
    )


def compare_lsb_bit_planes(
    cover_rgb: Image.Image, stego_rgb: Image.Image
) -> LsbBitPlaneComparison:
    """Compare cover and stego LSB bit planes channel by channel."""
    require_matching_rgb_images(cover_rgb, stego_rgb, "cover_rgb", "stego_rgb")

    cover_planes = extract_lsb_bit_plane(cover_rgb)
    stego_planes = extract_lsb_bit_plane(stego_rgb)

    change_mask = np.zeros(cover_planes.red.shape, dtype=np.uint8)
    changed_channels = 0
    for name in CHANNEL_NAMES:
        differing = cover_planes.for_channel(name) != stego_planes.for_channel(name)
        changed_channels += int(np.count_nonzero(differing))
        change_mask[differing] = PLANE_ON

    return LsbBitPlaneComparison(
        cover=cover_planes,
        stego=stego_planes,
        channel_change_mask=change_mask,
        changed_channel_count=changed_channels,
    )


def plane_to_image(plane: np.ndarray) -> Image.Image:
    """Convert a bit plane or change mask into a displayable grayscale image."""
    _validate_plane_array(plane)
    return Image.fromarray(plane, mode="L")


def planes_to_rgb_image(planes: LsbBitPlane) -> Image.Image:
    """Combine three channel bit planes into a displayable RGB image."""
    return Image.fromarray(planes.stacked(), mode="RGB")


def _lsb_plane(array: np.ndarray, channel: int) -> np.ndarray:
    bits = array[:, :, channel] & LSB_MASK
    return np.where(bits == 1, PLANE_ON, PLANE_OFF).astype(np.uint8)


def _validate_plane_array(plane: np.ndarray) -> None:
    if not isinstance(plane, np.ndarray):
        raise TypeError("plane must be a numpy array")
    if plane.ndim != 2:
        raise ValueError("plane must be a 2-D array")
    if plane.dtype != np.uint8:
        raise TypeError("plane must use the uint8 dtype")
