"""Pengujian beberapa citra dan ukuran pesan dengan pencatatan status per tahap."""

from __future__ import annotations

import os
import secrets
from dataclasses import asdict, dataclass, replace

import pandas as pd
from PIL import Image

from analysis.jpeg_fragility import run_jpeg_attack
from analysis.metrics import calculate_mse, psnr_from_mse
from stego.capacity import capacity_bits, required_bits
from stego.payload import AUTH_TAG_LENGTH
from stegochat.core import embed_plaintext, extract_plaintext


@dataclass(frozen=True)
class ExperimentResult:
    """Wadah satu kasus uji: kapasitas, kualitas citra, status proses, dan catatan error."""

    image_name: str
    width: int
    height: int
    capacity_bits: int
    capacity_bytes: int
    message_size_bytes: int
    payload_size_bytes: int
    capacity_utilization_percent: float
    mse: float | None
    psnr: float | None
    embed_success: bool
    extract_success: bool
    jpeg_attack_result: str | None
    error: str | None


def run_experiment_case(
    cover_image: Image.Image,
    message: str,
    stego_key_bytes: bytes,
) -> ExperimentResult:
    """Uji satu cover dan pesan: kapasitas, embedding, ekstraksi, metrik, lalu JPEG.

    Satu stego dipakai untuk semua tahap. Status dicatat secara terpisah agar
    kegagalan tahap berikutnya tidak menghapus keberhasilan tahap sebelumnya.
    """
    width, height = cover_image.size
    capacity = capacity_bits(width, height)
    # Kapasitas dihitung dari byte UTF-8; karakter non-ASCII dapat memakai beberapa byte.
    msg_bytes = len(message.encode("utf-8"))
    payload_bits = required_bits(msg_bytes + AUTH_TAG_LENGTH)
    result = ExperimentResult(
        image_name="",
        width=width,
        height=height,
        capacity_bits=capacity,
        capacity_bytes=capacity // 8,
        message_size_bytes=msg_bytes,
        payload_size_bytes=payload_bits // 8,
        capacity_utilization_percent=payload_bits / capacity * 100,
        mse=None,
        psnr=None,
        embed_success=False,
        extract_success=False,
        jpeg_attack_result=None,
        error=None,
    )
    if payload_bits > capacity:
        return replace(result, error="capacity_exceeded")

    # Catat setiap tahap terpisah agar error berikutnya tidak menghapus sukses sebelumnya.
    try:
        stego_image = embed_plaintext(cover_image, message, stego_key_bytes)
    except Exception as error:
        return replace(result, error=_stage_error("embed", error))
    result = replace(result, embed_success=True)
    errors: list[str] = []

    try:
        recovered = extract_plaintext(stego_image, stego_key_bytes)
        result = replace(result, extract_success=recovered == message)
        if not result.extract_success:
            errors.append("extract: plaintext_mismatch")
    except Exception as error:
        errors.append(_stage_error("extract", error))

    try:
        mse = calculate_mse(cover_image, stego_image)
        # Simpan MSE asli; pembulatan hanya diperlukan pada tampilan.
        result = replace(result, mse=mse)
        result = replace(result, psnr=psnr_from_mse(mse))
    except Exception as error:
        errors.append(_stage_error("metrics", error))

    try:
        # Uji JPEG memakai stego yang sama dengan ekstraksi dan perhitungan metrik.
        jpeg_result = run_jpeg_attack(
            stego_image, message, stego_key_bytes
        )
        if not jpeg_result.jpeg_created:
            result = replace(result, jpeg_attack_result="error")
            errors.append(
                f"jpeg: {jpeg_result.error_type}: {jpeg_result.error_reason}"
            )
        else:
            result = replace(
                result,
                jpeg_attack_result=(
                    "destroyed" if jpeg_result.attack_destroyed_payload else "survived"
                ),
            )
    except Exception as error:
        result = replace(result, jpeg_attack_result="error")
        errors.append(_stage_error("jpeg", error))

    return replace(result, error="; ".join(errors) or None)


def _stage_error(stage: str, error: Exception) -> str:
    """Gabungkan nama tahap, jenis exception, dan pesannya agar sumber gagal mudah ditelusuri."""
    return f"{stage}: {type(error).__name__}: {error}"


def run_laboratory(
    image_paths: list[str],
    message_sizes: list[int],
    stego_key: str,
    output_xlsx: str | None = None,
) -> list[ExperimentResult]:
    """Jalankan seluruh kombinasi berkas gambar dan ukuran pesan lalu kumpulkan hasil.

    Pesan dibuat dari huruf X agar panjang karakter sama dengan byte UTF-8.
    Jika output_xlsx diberikan, hasil sekaligus disimpan sebagai Excel.
    """
    stego_key_bytes = stego_key.encode("utf-8")
    results: list[ExperimentResult] = []

    for image_path in image_paths:
        try:
            cover_image = Image.open(image_path).convert("RGB")
            image_name = os.path.basename(image_path)

            for msg_size in message_sizes:
                # Karakter ASCII X memakai satu byte, sehingga ukuran pesan tepat sesuai pilihan.
                message = "X" * msg_size

                result = run_experiment_case(cover_image, message, stego_key_bytes)

                results.append(replace(result, image_name=image_name))

        except FileNotFoundError:
            print(f"Warning: Image not found: {image_path}")
        except Exception as e:
            print(f"Error processing {image_path}: {str(e)}")

    # Simpan tabel Excel bila lokasi keluaran diberikan.
    if output_xlsx:
        export_results_to_xlsx(results, output_xlsx)

    return results


def export_results_to_xlsx(
    results: list[ExperimentResult], output_path: str
) -> None:
    """Ubah dataclass hasil menjadi tabel lalu simpan ke lembar Excel tanpa kolom indeks."""
    df = pd.DataFrame([asdict(result) for result in results])
    df.to_excel(output_path, index=False, sheet_name="Experiment Results")


def generate_test_dataset(
    output_dir: str = "data/test_images",
    sizes: tuple[tuple[int, int, str], ...] = (
        (48, 48, "tiny"),
        (128, 128, "small"),
        (256, 256, "medium"),
        (512, 512, "large"),
        (640, 427, "photo"),
    ),
) -> list[str]:
    """Sediakan gambar uji; buat gradasi RGB hanya untuk berkas yang belum ada.

    Gambar yang sudah tersedia dipakai kembali sehingga tidak ditimpa.
    """
    os.makedirs(output_dir, exist_ok=True)
    image_paths: list[str] = []

    for width, height, prefix in sizes:
        filename = f"{prefix}_{width}x{height}.png"
        filepath = os.path.join(output_dir, filename)

        if not os.path.exists(filepath):
            # Buat gradasi sebagai gambar cadangan jika berkas belum tersedia.
            import numpy as np

            img_array = np.zeros((height, width, 3), dtype=np.uint8)

            # Koordinat menentukan gradasi merah dan hijau, sementara biru dibuat tetap.
            for y in range(height):
                for x in range(width):
                    img_array[y, x, 0] = (x * 255) // width  # Gradasi merah horizontal
                    img_array[y, x, 1] = (y * 255) // height  # Gradasi hijau vertikal
                    img_array[y, x, 2] = 128  # Kanal biru tetap

            img = Image.fromarray(img_array, "RGB")
            img.save(filepath, "PNG")

        image_paths.append(filepath)

    return image_paths


def run_default_laboratory(
    output_xlsx: str = "results/laboratory_results.xlsx",
    stego_key: str | None = None,
) -> list[ExperimentResult]:
    """Jalankan lima citra dengan tiga ukuran pesan lalu ekspor hasil tanpa menyimpan kunci.

    Jika kunci tidak diberikan, buat kunci acak yang hanya dipakai selama batch.
    """
    if stego_key is None:
        stego_key = secrets.token_hex(32)

    # Pakai citra yang tersedia atau buat gambar cadangan.
    image_paths = generate_test_dataset()

    # Tiga ukuran pesan pada lima citra menghasilkan 15 kombinasi uji.
    message_sizes = [10, 50, 100]

    # Jalankan semua kombinasi dan simpan hasil ke Excel.
    results = run_laboratory(
        image_paths=image_paths,
        message_sizes=message_sizes,
        stego_key=stego_key,
        output_xlsx=output_xlsx,
    )

    return results
