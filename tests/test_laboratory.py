"""Tests for the StegoChat laboratory experiment runner."""

from __future__ import annotations

import os
import tempfile

import pytest

from laboratory import (
    ExperimentResult,
    export_results_to_xlsx,
    generate_test_dataset,
    run_experiment_case,
    run_laboratory,
)


def test_experiment_result_dataclass() -> None:
    """Test ExperimentResult dataclass structure."""
    result = ExperimentResult(
        image_name="test.png",
        width=100,
        height=100,
        capacity_bits=30000,
        capacity_bytes=3750,
        message_size_bytes=10,
        payload_size_bytes=40,
        capacity_utilization_percent=0.13,
        mse=1.2345,
        psnr=35.67,
        embed_success=True,
        extract_success=True,
        jpeg_attack_result="survived",
        error=None,
    )

    assert result.image_name == "test.png"
    assert result.width == 100
    assert result.height == 100
    assert result.capacity_bits == 30000
    assert result.capacity_bytes == 3750
    assert result.message_size_bytes == 10
    assert result.payload_size_bytes == 40
    assert result.capacity_utilization_percent == 0.13
    assert result.mse == 1.2345
    assert result.psnr == 35.67
    assert result.embed_success is True
    assert result.extract_success is True
    assert result.jpeg_attack_result == "survived"
    assert result.error is None


def test_run_experiment_case_success() -> None:
    """Test successful experiment case."""
    from PIL import Image

    # Create a simple test image
    cover = Image.new("RGB", (100, 100), color=(100, 101, 102))
    message = "Test message"
    stego_key = b"test-key"

    result = run_experiment_case(cover, message, stego_key)

    assert result.image_name == ""
    assert result.width == 100
    assert result.height == 100
    assert result.embed_success is True
    assert result.extract_success is True
    assert result.mse is not None
    assert result.psnr is not None
    assert result.jpeg_attack_result in ("survived", "destroyed")
    assert result.error is None


def test_run_experiment_case_capacity_exceeded() -> None:
    """Test experiment case with message too large for image."""
    from PIL import Image

    # Create a small image
    cover = Image.new("RGB", (10, 10), color=(100, 101, 102))
    # Message too large for 10x10 image
    message = "X" * 1000
    stego_key = b"test-key"

    result = run_experiment_case(cover, message, stego_key)

    assert result.embed_success is False
    assert result.extract_success is False
    assert result.error == "capacity_exceeded"
    assert result.mse is None
    assert result.psnr is None


def test_run_laboratory() -> None:
    """Test laboratory experiment runner."""
    # Generate test images
    image_paths = generate_test_dataset()

    # Use 2 message sizes for faster test
    message_sizes = [10, 50]
    stego_key = "test-key"

    results = run_laboratory(
        image_paths=image_paths[:2],
        message_sizes=message_sizes,
        stego_key=stego_key,
    )

    assert len(results) == 4  # 2 images x 2 message sizes

    for result in results:
        assert isinstance(result, ExperimentResult)
        assert result.image_name != ""
        assert result.width > 0
        assert result.height > 0


def test_export_results_to_xlsx() -> None:
    """Test XLSX export functionality."""
    results = [
        ExperimentResult(
            image_name="test1.png",
            width=100,
            height=100,
            capacity_bits=30000,
            capacity_bytes=3750,
            message_size_bytes=10,
            payload_size_bytes=40,
            capacity_utilization_percent=0.13,
            mse=1.2345,
            psnr=35.67,
            embed_success=True,
            extract_success=True,
            jpeg_attack_result="survived",
            error=None,
        ),
        ExperimentResult(
            image_name="test2.png",
            width=200,
            height=200,
            capacity_bits=120000,
            capacity_bytes=15000,
            message_size_bytes=50,
            payload_size_bytes=70,
            capacity_utilization_percent=0.06,
            mse=2.3456,
            psnr=33.45,
            embed_success=True,
            extract_success=True,
            jpeg_attack_result="destroyed",
            error=None,
        ),
    ]

    with tempfile.NamedTemporaryFile(
        suffix=".xlsx", delete=False
    ) as tmp_file:
        output_path = tmp_file.name

    try:
        export_results_to_xlsx(results, output_path)

        # Verify file was created
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

    finally:
        if os.path.exists(output_path):
            os.remove(output_path)


def test_generate_test_dataset() -> None:
    """Test test image generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        image_paths = generate_test_dataset(output_dir=tmpdir)

        assert len(image_paths) == 5

        for path in image_paths:
            assert os.path.exists(path)
            assert path.endswith(".png")

            # Verify image can be opened
            from PIL import Image

            with Image.open(path) as img:
                assert img.mode == "RGB"


def test_laboratory_with_nonexistent_image() -> None:
    """Test laboratory runner with nonexistent image."""
    image_paths = ["nonexistent.png"]
    message_sizes = [10]
    stego_key = "test-key"

    results = run_laboratory(
        image_paths=image_paths,
        message_sizes=message_sizes,
        stego_key=stego_key,
    )

    # Should return empty list or handle gracefully
    assert len(results) == 0
