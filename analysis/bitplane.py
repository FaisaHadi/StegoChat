"""Visualisasi bit terakhir kanal RGB dan lokasi perubahan LSB setelah penyisipan.

Bit 0 ditampilkan hitam dan bit 1 putih agar perubahan kecil dapat diamati.
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
    """Wadah bidang LSB hitam-putih untuk kanal merah, hijau, dan biru."""

    red: np.ndarray
    green: np.ndarray
    blue: np.ndarray

    def for_channel(self, name: str) -> np.ndarray:
        """Ambil bidang LSB dua dimensi untuk kanal R, G, atau B."""
        if name == "R":
            return self.red
        if name == "G":
            return self.green
        if name == "B":
            return self.blue
        raise ValueError(f"unknown RGB channel name: {name!r}")

    def stacked(self) -> np.ndarray:
        """Gabungkan tiga bidang LSB menjadi array tinggi x lebar x 3 untuk gambar RGB."""
        return np.stack([self.red, self.green, self.blue], axis=-1).astype(np.uint8)


@dataclass(frozen=True)
class LsbBitPlaneComparison:
    """Wadah bidang cover dan stego beserta peta piksel serta jumlah kanal yang berubah."""

    cover: LsbBitPlane
    stego: LsbBitPlane
    channel_change_mask: np.ndarray
    changed_channel_count: int

    def changed_pixel_count(self) -> int:
        """Hitung piksel yang setidaknya satu kanal LSB-nya berbeda antara cover dan stego."""
        return int(np.count_nonzero(self.channel_change_mask))


def extract_lsb_bit_plane(image_rgb: Image.Image) -> LsbBitPlane:
    """Ambil bit terakhir tiap kanal gambar RGB dan ubah menjadi bidang hitam-putih."""
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
    """Bandingkan LSB cover dan stego per kanal lalu tandai piksel berbeda dengan putih.

    Jumlah kanal berubah dihitung terpisah karena satu piksel dapat memiliki
    lebih dari satu kanal yang berubah.
    """
    require_matching_rgb_images(cover_rgb, stego_rgb, "cover_rgb", "stego_rgb")

    cover_planes = extract_lsb_bit_plane(cover_rgb)
    stego_planes = extract_lsb_bit_plane(stego_rgb)

    change_mask = np.zeros(cover_planes.red.shape, dtype=np.uint8)
    changed_channels = 0
    for name in CHANNEL_NAMES:
        differing = cover_planes.for_channel(name) != stego_planes.for_channel(name)
        changed_channels += int(np.count_nonzero(differing))
        # Peta gabungan menandai satu piksel sekali walau beberapa kanalnya berubah.
        change_mask[differing] = PLANE_ON

    return LsbBitPlaneComparison(
        cover=cover_planes,
        stego=stego_planes,
        channel_change_mask=change_mask,
        changed_channel_count=changed_channels,
    )


def plane_to_image(plane: np.ndarray) -> Image.Image:
    """Validasi array bidang LSB lalu ubah menjadi gambar grayscale untuk ditampilkan."""
    _validate_plane_array(plane)
    return Image.fromarray(plane, mode="L")


def planes_to_rgb_image(planes: LsbBitPlane) -> Image.Image:
    """Gabungkan bidang LSB merah, hijau, dan biru menjadi satu gambar RGB."""
    return Image.fromarray(planes.stacked(), mode="RGB")


def _lsb_plane(array: np.ndarray, channel: int) -> np.ndarray:
    """Ambil bit terakhir dengan mask 1, lalu petakan 0 ke hitam dan 1 ke putih."""
    bits = array[:, :, channel] & LSB_MASK
    return np.where(bits == 1, PLANE_ON, PLANE_OFF).astype(np.uint8)


def _validate_plane_array(plane: np.ndarray) -> None:
    """Pastikan bidang LSB berupa array dua dimensi dengan tipe uint8."""
    if not isinstance(plane, np.ndarray):
        raise TypeError("plane must be a numpy array")
    if plane.ndim != 2:
        raise ValueError("plane must be a 2-D array")
    if plane.dtype != np.uint8:
        raise TypeError("plane must use the uint8 dtype")
