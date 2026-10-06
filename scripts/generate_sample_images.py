"""Membuat lima citra uji sintetis dengan pola dan seed tetap.

Gambar dapat dibuat ulang tanpa mengambil aset pihak ketiga. Jalankan dari
folder proyek: python scripts/generate_sample_images.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "test_images"
RANDOM_SEED = 20250926
NOISE_AMPLITUDE = 14
MAX_PIXEL_VALUE = 255.0


def main() -> int:
    """Buat folder citra uji dan simpan lima pola RGB sebagai PNG sesuai ukuran bawaan."""
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    generators = (
        ("tiny_48x48.png", _diagonal_gradient(48, 48)),
        ("small_128x128.png", _checkerboard(128, 128)),
        ("medium_256x256.png", _sine_pattern(256, 256)),
        ("large_512x512.png", _smooth_blobs(512, 512)),
        ("photo_640x427.png", _synthetic_landscape(640, 427)),
    )

    for filename, array in generators:
        destination = OUTPUT_DIRECTORY / filename
        Image.fromarray(array, mode="RGB").save(destination, format="PNG", optimize=True)
        print(f"wrote {destination.relative_to(PROJECT_ROOT)} ({array.shape[1]}x{array.shape[0]})")

    return 0


def _diagonal_gradient(width: int, height: int) -> np.ndarray:
    """Buat gradasi merah horizontal, hijau vertikal, dan biru dari gabungan keduanya."""
    x = np.linspace(0.0, MAX_PIXEL_VALUE, width)
    y = np.linspace(0.0, MAX_PIXEL_VALUE, height)
    grid_x, grid_y = np.meshgrid(x, y)
    red = grid_x
    green = grid_y
    blue = (grid_x + grid_y) / 2.0
    return np.stack([red, green, blue], axis=-1).astype(np.uint8)


def _checkerboard(width: int, height: int, square: int = 16) -> np.ndarray:
    """Buat pola papan catur dua warna berdasarkan paritas koordinat petak."""
    y, x = np.indices((height, width))
    parity = ((x // square) + (y // square)) % 2
    palette = np.array(
        [
            [220, 60, 45],
            [35, 90, 190],
        ],
        dtype=np.uint8,
    )
    return palette[parity]


def _sine_pattern(width: int, height: int) -> np.ndarray:
    """Buat variasi warna periodik menggunakan sinus dan kosinus pada koordinat gambar."""
    x = np.linspace(0.0, 4.0 * np.pi, width)
    y = np.linspace(0.0, 4.0 * np.pi, height)
    grid_x, grid_y = np.meshgrid(x, y)
    red = 128.0 + 110.0 * np.sin(grid_x)
    green = 128.0 + 110.0 * np.cos(grid_y)
    blue = 128.0 + 110.0 * np.sin((grid_x + grid_y) / 2.0)
    return _clamp_rgb(red, green, blue)


def _smooth_blobs(
    width: int, height: int, blob_count: int = 6
) -> np.ndarray:
    """Gabungkan gumpalan warna berbobot Gaussian dari pusat acak dengan seed tetap."""
    rng = np.random.default_rng(RANDOM_SEED)
    centers = rng.uniform(0.0, 1.0, size=(blob_count, 2))
    colors = rng.uniform(40.0, 230.0, size=(blob_count, 3))
    y, x = np.mgrid[0:height, 0:width]
    grid_x = x / max(width - 1, 1)
    grid_y = y / max(height - 1, 1)

    red = np.zeros((height, width))
    green = np.zeros((height, width))
    blue = np.zeros((height, width))
    for (center_x, center_y), (color_r, color_g, color_b) in zip(
        centers, colors, strict=True
    ):
        distance = (grid_x - center_x) ** 2 + (grid_y - center_y) ** 2
        weight = np.exp(-distance / 0.05)
        red += weight * color_r
        green += weight * color_g
        blue += weight * color_b

    return _clamp_rgb(red, green, blue)


def _synthetic_landscape(width: int, height: int) -> np.ndarray:
    """Buat pemandangan sintetis dari gradasi langit, cahaya matahari, bukit, dan noise tetap."""
    rng = np.random.default_rng(RANDOM_SEED + 1)
    y, x = np.mgrid[0:height, 0:width]
    grid_y = y / max(height - 1, 1)

    sky_top = np.array([70.0, 130.0, 210.0])
    sky_bottom = np.array([200.0, 220.0, 235.0])
    sky = sky_top[None, None, :] + (sky_bottom - sky_top)[None, None, :] * grid_y[..., None]

    sun_radius = 0.16
    sun_center_x, sun_center_y = 0.74, 0.22
    distance = np.sqrt(
        ((x / width) - sun_center_x) ** 2 + ((y / height) - sun_center_y) ** 2
    )
    sun_glow = np.clip(1.0 - distance / sun_radius, 0.0, 1.0) ** 2
    sun = sun_glow[..., None] * np.array([255.0, 236.0, 170.0])

    hill_line = 0.58 + 0.10 * np.sin(np.linspace(0.0, 3.0 * np.pi, width))[None, :]
    hill_mask = (grid_y > hill_line).astype(float)
    hill = hill_mask[..., None] * np.array([60.0, 110.0, 70.0])

    texture = rng.normal(0.0, NOISE_AMPLITUDE / 3.0, size=(height, width, 3))
    return _clamp_rgb(
        sky[..., 0] + sun[..., 0] + hill[..., 0] + texture[..., 0],
        sky[..., 1] + sun[..., 1] + hill[..., 1] + texture[..., 1],
        sky[..., 2] + sun[..., 2] + hill[..., 2] + texture[..., 2],
    )


def _clamp_rgb(red: np.ndarray, green: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """Batasi nilai tiap kanal ke 0 sampai 255 lalu gabungkan sebagai array RGB uint8."""
    red = np.clip(_broadcast(red), 0.0, MAX_PIXEL_VALUE)
    green = np.clip(_broadcast(green), 0.0, MAX_PIXEL_VALUE)
    blue = np.clip(_broadcast(blue), 0.0, MAX_PIXEL_VALUE)
    return np.stack([red, green, blue], axis=-1).astype(np.uint8)


def _broadcast(channel: np.ndarray) -> np.ndarray:
    """Pastikan kanal berupa array dua dimensi sebelum digabung ke gambar RGB."""
    if channel.ndim == 2:
        return channel
    raise ValueError("each channel must be a 2-D array")


if __name__ == "__main__":
    sys.exit(main())
