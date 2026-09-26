"""StegoChat Streamlit Application.

A Secret Photo Messenger that encrypts messages with AES-256-GCM and hides
the authenticated payload in the least significant bits of an RGB image.
"""

from __future__ import annotations

import io
import tempfile
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

from analysis.bitplane import compare_lsb_bit_planes, extract_lsb_bit_plane, plane_to_image
from analysis.histogram import compare_rgb_histograms, compute_rgb_histogram
from analysis.jpeg_fragility import run_jpeg_fragility_test
from analysis.metrics import calculate_mse, calculate_psnr
from stegochat.core import embed_plaintext, extract_plaintext

st.set_page_config(
    page_title="StegoChat - Secret Photo Messenger",
    page_icon="🔒",
    layout="wide",
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Convert a PIL Image to bytes for download."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def download_button(
    image: Image.Image, filename: str, format: str = "PNG"
) -> str:
    """Generate a Streamlit download button for an image."""
    data = image_to_bytes(image, format)
    st.download_button(
        label=f"Download {filename}",
        data=data,
        file_name=filename,
        mime=f"image/{format.lower()}",
    )
    return data


def run_laboratory_experiment(
    cover_image: Image.Image,
    message: str,
    stego_key: bytes,
) -> dict[str, Any]:
    """Run a single laboratory experiment case."""
    result: dict[str, Any] = {}

    try:
        # Embed
        stego_image = embed_plaintext(cover_image, message, stego_key)

        # Extract
        recovered = extract_plaintext(stego_image, stego_key)
        extraction_success = recovered == message

        # Metrics
        mse = calculate_mse(cover_image, stego_image)
        psnr = calculate_psnr(cover_image, stego_image)

        # JPEG attack
        jpeg_result = run_jpeg_fragility_test(
            cover_image, message, stego_key, quality=85
        )

        result.update(
            {
                "embed_success": True,
                "extract_success": extraction_success,
                "recovered_message": recovered if extraction_success else None,
                "mse": mse,
                "psnr": psnr,
                "jpeg_destroyed_payload": jpeg_result.attack_destroyed_payload,
                "jpeg_error_stage": jpeg_result.error_stage,
                "error": None,
            }
        )
    except Exception as e:
        result.update(
            {
                "embed_success": False,
                "extract_success": False,
                "recovered_message": None,
                "mse": None,
                "psnr": None,
                "jpeg_destroyed_payload": None,
                "jpeg_error_stage": None,
                "error": str(e),
            }
        )

    return result


# ============================================================================
# TAB 1: EMBED & SEND
# ============================================================================


def tab_embed_send() -> None:
    """Tab 1: Embed a message into an image."""
    st.header("🔒 Embed & Send")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Input")
        cover_upload = st.file_uploader(
            "Upload Cover Image (PNG/BMP)",
            type=["png", "bmp"],
            help="Upload a PNG or BMP image in RGB mode",
        )

        message = st.text_area(
            "Message to Hide",
            height=100,
            placeholder="Enter your secret message here...",
        )

        stego_key = st.text_input(
            "Stego Key (Password)",
            type="password",
            placeholder="Enter a shared secret key",
        )

        if cover_upload and message and stego_key:
            try:
                cover_image = Image.open(cover_upload).convert("RGB")
                stego_key_bytes = stego_key.encode("utf-8")

                # Capacity check
                width, height = cover_image.size
                capacity = width * height * 3
                payload_bits = (34 + len(message.encode("utf-8")) + 16) * 8

                st.info(
                    f"**Image Size:** {width}x{height} | "
                    f"**Capacity:** {capacity} bits | "
                    f"**Required:** {payload_bits} bits"
                )

                if payload_bits > capacity:
                    st.error(
                        f"Message too large! Maximum capacity: {(capacity - 272) // 8} bytes"
                    )
                else:
                    if st.button("Embed Message", type="primary"):
                        with st.spinner("Embedding message..."):
                            stego_image = embed_plaintext(
                                cover_image, message, stego_key_bytes
                            )

                            # Calculate metrics
                            mse = calculate_mse(cover_image, stego_image)
                            psnr = calculate_psnr(cover_image, stego_image)

                            st.success("Message embedded successfully!")

                            # Display results
                            st.subheader("Results")
                            st.metric("MSE", f"{mse:.4f}")
                            st.metric("PSNR", f"{psnr:.2f} dB")

                            # Side-by-side comparison
                            st.subheader("Comparison")
                            comp_col1, comp_col2 = st.columns(2)
                            with comp_col1:
                                st.image(
                                    cover_image,
                                    caption="Cover Image",
                                    use_container_width=True,
                                )
                            with comp_col2:
                                st.image(
                                    stego_image,
                                    caption="Stego Image",
                                    use_container_width=True,
                                )

                            # Download
                            st.subheader("Download")
                            stego_bytes = image_to_bytes(stego_image, "PNG")
                            st.download_button(
                                label="Download Stego Image (PNG)",
                                data=stego_bytes,
                                file_name="stego_image.png",
                                mime="image/png",
                            )

            except Exception as e:
                st.error(f"Error: {str(e)}")
        else:
            st.warning("Please provide cover image, message, and stego key")


# ============================================================================
# TAB 2: EXTRACT & READ
# ============================================================================


def tab_extract_read() -> None:
    """Tab 2: Extract and decrypt a message."""
    st.header("🔓 Extract & Read")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Input")
        stego_upload = st.file_uploader(
            "Upload Stego Image",
            type=["png", "bmp"],
            help="Upload the stego image containing the hidden message",
        )

        stego_key = st.text_input(
            "Stego Key (Password)",
            type="password",
            placeholder="Enter the shared secret key",
        )

        if stego_upload and stego_key:
            try:
                stego_image = Image.open(stego_upload).convert("RGB")
                stego_key_bytes = stego_key.encode("utf-8")

                if st.button("Extract & Decrypt", type="primary"):
                    with st.spinner("Extracting message..."):
                        try:
                            plaintext = extract_plaintext(
                                stego_image, stego_key_bytes
                            )
                            st.success("Message extracted successfully!")
                            st.subheader("Decrypted Message")
                            st.text_area(
                                "Plaintext",
                                value=plaintext,
                                height=150,
                                disabled=True,
                            )
                        except Exception as e:
                            st.error(
                                "Authentication failed. The stego-key may be incorrect or the payload may have been modified."
                            )
                            st.exception(e)

            except Exception as e:
                st.error(f"Error: {str(e)}")
        else:
            st.warning("Please provide stego image and stego key")


# ============================================================================
# TAB 3: LABORATORY & SECURITY TESTING
# ============================================================================


def tab_laboratory() -> None:
    """Tab 3: Laboratory experiments and security testing."""
    st.header("🧪 Laboratory & Security Testing")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Histogram Analysis", "LSB Bit-Plane", "JPEG Attack", "Experiment Runner"]
    )

    with tab1:
        st.subheader("RGB Histogram Analysis")

        cover_upload = st.file_uploader(
            "Upload Cover Image", type=["png", "bmp"], key="hist_cover"
        )
        stego_upload = st.file_uploader(
            "Upload Stego Image", type=["png", "bmp"], key="hist_stego"
        )

        if cover_upload and stego_upload:
            try:
                cover_image = Image.open(cover_upload).convert("RGB")
                stego_image = Image.open(stego_upload).convert("RGB")

                comparison = compare_rgb_histograms(cover_image, stego_image)

                # Display histograms
                fig, axes = plt.subplots(2, 3, figsize=(15, 8))

                channels = ["R", "G", "B"]
                colors = ["red", "green", "blue"]

                for i, (channel, color) in enumerate(zip(channels, colors)):
                    # Cover histogram
                    axes[0, i].bar(
                        range(256),
                        comparison.cover.for_channel(channel),
                        color=color,
                        alpha=0.7,
                        label="Cover",
                    )
                    axes[0, i].set_title(f"Cover {channel} Channel")
                    axes[0, i].set_xlabel("Intensity")
                    axes[0, i].set_ylabel("Count")

                    # Stego histogram
                    axes[1, i].bar(
                        range(256),
                        comparison.stego.for_channel(channel),
                        color=color,
                        alpha=0.7,
                        label="Stego",
                    )
                    axes[1, i].set_title(f"Stego {channel} Channel")
                    axes[1, i].set_xlabel("Intensity")
                    axes[1, i].set_ylabel("Count")

                plt.tight_layout()
                st.pyplot(fig)

                # Changed bin count
                st.info(
                    f"**Total changed bins:** {comparison.changed_bin_count()} of 768"
                )

            except Exception as e:
                st.error(f"Error: {str(e)}")

    with tab2:
        st.subheader("LSB Bit-Plane Analysis")

        cover_upload = st.file_uploader(
            "Upload Cover Image", type=["png", "bmp"], key="plane_cover"
        )
        stego_upload = st.file_uploader(
            "Upload Stego Image", type=["png", "bmp"], key="plane_stego"
        )

        if cover_upload and stego_upload:
            try:
                cover_image = Image.open(cover_upload).convert("RGB")
                stego_image = Image.open(stego_upload).convert("RGB")

                comparison = compare_lsb_bit_planes(cover_image, stego_image)

                # Display bit planes
                st.subheader("Cover LSB Planes")
                col1, col2, col3 = st.columns(3)
                for i, (channel, name) in enumerate(
                    [(0, "Red"), (1, "Green"), (2, "Blue")]
                ):
                    with col1 if i == 0 else col2 if i == 1 else col3:
                        st.image(
                            plane_to_image(
                                comparison.cover.for_channel("RGB"[i])
                            ),
                            caption=f"{name} Channel",
                            use_container_width=True,
                        )

                st.subheader("Stego LSB Planes")
                col1, col2, col3 = st.columns(3)
                for i, (channel, name) in enumerate(
                    [(0, "Red"), (1, "Green"), (2, "Blue")]
                ):
                    with col1 if i == 0 else col2 if i == 1 else col3:
                        st.image(
                            plane_to_image(
                                comparison.stego.for_channel("RGB"[i])
                            ),
                            caption=f"{name} Channel",
                            use_container_width=True,
                        )

                # Change mask
                st.subheader("Changed LSB Pixels")
                st.image(
                    plane_to_image(comparison.channel_change_mask),
                    caption="Pixels with LSB modifications (white = changed)",
                    use_container_width=True,
                )

                st.info(
                    f"**Changed pixels:** {comparison.changed_pixel_count()} | "
                    f"**Changed channels:** {comparison.changed_channel_count}"
                )

            except Exception as e:
                st.error(f"Error: {str(e)}")

    with tab3:
        st.subheader("JPEG Fragility Attack")

        cover_upload = st.file_uploader(
            "Upload Cover Image", type=["png", "bmp"], key="jpeg_cover"
        )
        message = st.text_area(
            "Message to Test", height=50, key="jpeg_message"
        )
        stego_key = st.text_input(
            "Stego Key", type="password", key="jpeg_key"
        )

        if cover_upload and message and stego_key:
            try:
                cover_image = Image.open(cover_upload).convert("RGB")
                stego_key_bytes = stego_key.encode("utf-8")

                if st.button("Run JPEG Attack Test", type="primary"):
                    with st.spinner("Running JPEG attack test..."):
                        result = run_jpeg_fragility_test(
                            cover_image, message, stego_key_bytes, quality=85
                        )

                        st.subheader("Results")
                        st.json(
                            {
                                "quality": result.quality,
                                "jpeg_created": result.jpeg_created,
                                "jpeg_size_bytes": result.jpeg_size_bytes,
                                "extraction_succeeded": result.extraction_succeeded,
                                "decryption_succeeded": result.decryption_succeeded,
                                "recovered_plaintext": result.recovered_plaintext,
                                "plaintext_matches": result.plaintext_matches,
                                "attack_destroyed_payload": result.attack_destroyed_payload,
                                "error_stage": result.error_stage,
                                "error_type": result.error_type,
                                "error_reason": result.error_reason,
                            }
                        )

                        if result.attack_destroyed_payload:
                            st.warning("⚠️ JPEG attack successfully destroyed the payload!")
                        else:
                            st.success("✅ Payload survived JPEG compression!")

            except Exception as e:
                st.error(f"Error: {str(e)}")

    with tab4:
        st.subheader("Laboratory Experiment Runner")

        # Image selection
        image_dir = "data/test_images"
        try:
            import os

            image_files = [
                f
                for f in os.listdir(image_dir)
                if f.lower().endswith((".png", ".bmp"))
            ]
        except FileNotFoundError:
            st.error(f"Test images directory not found: {image_dir}")
            image_files = []

        if image_files:
            selected_images = st.multiselect(
                "Select Test Images",
                image_files,
                default=image_files[: min(5, len(image_files))],
            )

            # Message size selection
            message_sizes = st.multiselect(
                "Select Message Sizes (bytes)",
                [10, 50, 100, 200, 500],
                default=[10, 50, 100],
            )

            stego_key = st.text_input(
                "Stego Key for Testing",
                value="test-secret-key",
                key="lab_key",
            )

            if st.button("Run Laboratory Experiments", type="primary"):
                if not selected_images or not message_sizes:
                    st.warning("Please select at least one image and one message size")
                else:
                    stego_key_bytes = stego_key.encode("utf-8")
                    results: list[dict[str, Any]] = []

                    progress_bar = st.progress(0)
                    total_cases = len(selected_images) * len(message_sizes)
                    current_case = 0

                    for image_file in selected_images:
                        try:
                            cover_path = f"{image_dir}/{image_file}"
                            cover_image = Image.open(cover_path).convert("RGB")
                            width, height = cover_image.size
                            capacity = width * height * 3

                            for msg_size in message_sizes:
                                current_case += 1
                                progress = current_case / total_cases
                                progress_bar.progress(progress)

                                # Generate message of specified size
                                message = "X" * msg_size

                                result = run_laboratory_experiment(
                                    cover_image, message, stego_key_bytes
                                )

                                payload_bits = (34 + msg_size + 16) * 8
                                capacity_utilization = (
                                    (payload_bits / capacity) * 100
                                    if capacity > 0
                                    else 0
                                )

                                results.append(
                                    {
                                        "image_name": image_file,
                                        "width": width,
                                        "height": height,
                                        "capacity_bits": capacity,
                                        "capacity_bytes": capacity // 8,
                                        "message_size_bytes": msg_size,
                                        "payload_size_bytes": payload_bits // 8,
                                        "capacity_utilization_percent": round(
                                            capacity_utilization, 2
                                        ),
                                        "mse": (
                                            round(result["mse"], 4)
                                            if result["mse"] is not None
                                            else None
                                        ),
                                        "psnr": (
                                            round(result["psnr"], 2)
                                            if result["psnr"] is not None
                                            else None
                                        ),
                                        "embed_success": result["embed_success"],
                                        "extract_success": result["extract_success"],
                                        "jpeg_attack_result": (
                                            "destroyed"
                                            if result["jpeg_destroyed_payload"]
                                            else "survived"
                                        ),
                                        "error": result["error"],
                                    }
                                )
                        except Exception as e:
                            st.error(f"Error processing {image_file}: {str(e)}")

                    progress_bar.empty()

                    # Display results table
                    st.subheader("Experiment Results")
                    df = pd.DataFrame(results)
                    st.dataframe(df, use_container_width=True)

                    # Download XLSX
                    if st.button("Download Results as XLSX"):
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine="openpyxl") as writer:
                            df.to_excel(writer, index=False, sheet_name="Results")
                        output.seek(0)
                        st.download_button(
                            label="Download XLSX",
                            data=output.getvalue(),
                            file_name="laboratory_results.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )


# ============================================================================
# MAIN APP
# ============================================================================


def main() -> None:
    """Main application entry point."""
    st.title("🔒 StegoChat - Secret Photo Messenger")
    st.markdown(
        """
    Encrypt messages with AES-256-GCM and hide them in RGB images using LSB steganography.
    """
    )

    tab1, tab2, tab3 = st.tabs(
        ["Embed & Send", "Extract & Read", "Laboratory & Security Testing"]
    )

    with tab1:
        tab_embed_send()

    with tab2:
        tab_extract_read()

    with tab3:
        tab_laboratory()


if __name__ == "__main__":
    main()
