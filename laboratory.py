"""Laboratory experiment runner for StegoChat V1.

This module provides automated testing capabilities for evaluating
the StegoChat system across multiple images and message sizes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import pandas as pd
from PIL import Image

from analysis.jpeg_fragility import run_jpeg_fragility_test
from analysis.metrics import calculate_mse, calculate_psnr
from stegochat.core import embed_plaintext, extract_plaintext


@dataclass(frozen=True)
class ExperimentResult:
    """Result of one laboratory experiment case."""

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
    """Run a single experiment case.

    Args:
        cover_image: The cover RGB image.
        message: The plaintext message to embed.
        stego_key_bytes: The stego key as bytes.

    Returns:
        ExperimentResult with all metrics and outcomes.
    """
    width, height = cover_image.size
    capacity = width * height * 3
    msg_bytes = len(message.encode("utf-8"))
    payload_bits = (34 + msg_bytes + 16) * 8
    capacity_utilization = (payload_bits / capacity) * 100 if capacity > 0 else 0

    try:
        # Embed
        stego_image = embed_plaintext(cover_image, message, stego_key_bytes)

        # Extract
        recovered = extract_plaintext(stego_image, stego_key_bytes)
        extract_success = recovered == message

        # Metrics
        mse = calculate_mse(cover_image, stego_image)
        psnr = calculate_psnr(cover_image, stego_image)

        # JPEG attack
        jpeg_result = run_jpeg_fragility_test(
            cover_image, message, stego_key_bytes, quality=85
        )
        jpeg_attack_result = (
            "destroyed" if jpeg_result.attack_destroyed_payload else "survived"
        )

        return ExperimentResult(
            image_name="",
            width=width,
            height=height,
            capacity_bits=capacity,
            capacity_bytes=capacity // 8,
            message_size_bytes=msg_bytes,
            payload_size_bytes=payload_bits // 8,
            capacity_utilization_percent=round(capacity_utilization, 2),
            mse=round(mse, 4),
            psnr=round(psnr, 2),
            embed_success=True,
            extract_success=extract_success,
            jpeg_attack_result=jpeg_attack_result,
            error=None,
        )

    except ValueError as e:
        if "insufficient" in str(e).lower():
            return ExperimentResult(
                image_name="",
                width=width,
                height=height,
                capacity_bits=capacity,
                capacity_bytes=capacity // 8,
                message_size_bytes=msg_bytes,
                payload_size_bytes=payload_bits // 8,
                capacity_utilization_percent=round(capacity_utilization, 2),
                mse=None,
                psnr=None,
                embed_success=False,
                extract_success=False,
                jpeg_attack_result=None,
                error="capacity_exceeded",
            )
        return ExperimentResult(
            image_name="",
            width=width,
            height=height,
            capacity_bits=capacity,
            capacity_bytes=capacity // 8,
            message_size_bytes=msg_bytes,
            payload_size_bytes=payload_bits // 8,
            capacity_utilization_percent=round(capacity_utilization, 2),
            mse=None,
            psnr=None,
            embed_success=False,
            extract_success=False,
            jpeg_attack_result=None,
            error=str(e),
        )

    except Exception as e:
        return ExperimentResult(
            image_name="",
            width=width,
            height=height,
            capacity_bits=capacity,
            capacity_bytes=capacity // 8,
            message_size_bytes=msg_bytes,
            payload_size_bytes=payload_bits // 8,
            capacity_utilization_percent=round(capacity_utilization, 2),
            mse=None,
            psnr=None,
            embed_success=False,
            extract_success=False,
            jpeg_attack_result=None,
            error=str(e),
        )


def run_laboratory(
    image_paths: list[str],
    message_sizes: list[int],
    stego_key: str,
    output_xlsx: str | None = None,
) -> list[ExperimentResult]:
    """Run laboratory experiments across multiple images and message sizes.

    Args:
        image_paths: List of paths to test images.
        message_sizes: List of message sizes in bytes to test.
        stego_key: The stego key (password) as a string.
        output_xlsx: Optional path to save results as XLSX.

    Returns:
        List of ExperimentResult objects.
    """
    stego_key_bytes = stego_key.encode("utf-8")
    results: list[ExperimentResult] = []

    for image_path in image_paths:
        try:
            cover_image = Image.open(image_path).convert("RGB")
            image_name = os.path.basename(image_path)

            for msg_size in message_sizes:
                # Generate message of specified size
                message = "X" * msg_size

                result = run_experiment_case(cover_image, message, stego_key_bytes)

                # Update image name in result
                result_dict = result.__dict__.copy()
                result_dict["image_name"] = image_name
                updated_result = ExperimentResult(**result_dict)

                results.append(updated_result)

        except FileNotFoundError:
            print(f"Warning: Image not found: {image_path}")
        except Exception as e:
            print(f"Error processing {image_path}: {str(e)}")

    # Export to XLSX if requested
    if output_xlsx:
        export_results_to_xlsx(results, output_xlsx)

    return results


def export_results_to_xlsx(
    results: list[ExperimentResult], output_path: str
) -> None:
    """Export experiment results to an XLSX file.

    Args:
        results: List of ExperimentResult objects.
        output_path: Path to save the XLSX file.
    """
    data: list[dict[str, Any]] = []

    for result in results:
        data.append(
            {
                "image_name": result.image_name,
                "width": result.width,
                "height": result.height,
                "capacity_bits": result.capacity_bits,
                "capacity_bytes": result.capacity_bytes,
                "message_size_bytes": result.message_size_bytes,
                "payload_size_bytes": result.payload_size_bytes,
                "capacity_utilization_percent": result.capacity_utilization_percent,
                "mse": result.mse,
                "psnr": result.psnr,
                "embed_success": result.embed_success,
                "extract_success": result.extract_success,
                "jpeg_attack_result": result.jpeg_attack_result,
                "error": result.error,
            }
        )

    df = pd.DataFrame(data)
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
    """Generate test images if they don't exist.

    Args:
        output_dir: Directory to save test images.
        sizes: Tuple of (width, height, prefix) for each image.

    Returns:
        List of paths to generated images.
    """
    os.makedirs(output_dir, exist_ok=True)
    image_paths: list[str] = []

    for width, height, prefix in sizes:
        filename = f"{prefix}_{width}x{height}.png"
        filepath = os.path.join(output_dir, filename)

        if not os.path.exists(filepath):
            # Create a simple gradient image
            import numpy as np

            img_array = np.zeros((height, width, 3), dtype=np.uint8)

            # Create a gradient pattern
            for y in range(height):
                for x in range(width):
                    img_array[y, x, 0] = (x * 255) // width  # Red gradient
                    img_array[y, x, 1] = (y * 255) // height  # Green gradient
                    img_array[y, x, 2] = 128  # Blue constant

            img = Image.fromarray(img_array, "RGB")
            img.save(filepath, "PNG")

        image_paths.append(filepath)

    return image_paths


def run_default_laboratory(
    output_xlsx: str = "results/laboratory_results.xlsx",
    stego_key: str = "test-secret-key",
) -> list[ExperimentResult]:
    """Run the default laboratory experiment with standard test images.

    Args:
        output_xlsx: Path to save XLSX results.
        stego_key: The stego key to use.

    Returns:
        List of ExperimentResult objects.
    """
    # Generate or use existing test images
    image_paths = generate_test_dataset()

    # Use 3 message sizes
    message_sizes = [10, 50, 100]

    # Run experiments
    results = run_laboratory(
        image_paths=image_paths,
        message_sizes=message_sizes,
        stego_key=stego_key,
        output_xlsx=output_xlsx,
    )

    return results
