"""StegoChat Streamlit Application.

A Secret Photo Messenger that encrypts messages with AES-256-GCM and hides
the authenticated payload in the least significant bits of an RGB image.
"""

from __future__ import annotations

import io
import tempfile
import html
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
from analysis.chi_square import compute_chi_square_test, chi_square_report_to_rows

st.set_page_config(
    page_title="StegoChat - Secret Photo Messenger",
    page_icon="🔒",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'JetBrains Mono', monospace;
    }

    /* ============ STREAMLIT HEADER (Deploy bar) transparan ============ */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* ============ FULL WIDTH PAGE ============ */
    [data-testid="stAppViewContainer"] > .main {
        width: 100%;
    }

    [data-testid="BlockContainer"] {
        max-width: none !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 3.5rem 0.8rem 3.5rem !important;
    }

    [data-testid="stHorizontalBlock"] {
        width: 100%;
    }

    /* ============ BACKGROUND: grid blueprint halus + glow blob ============ */
    .stApp {
        background:
            repeating-linear-gradient(
                0deg,
                rgba(56, 189, 248, 0.035) 0px,
                rgba(56, 189, 248, 0.035) 1px,
                transparent 1px,
                transparent 48px
            ),
            repeating-linear-gradient(
                90deg,
                rgba(56, 189, 248, 0.035) 0px,
                rgba(56, 189, 248, 0.035) 1px,
                transparent 1px,
                transparent 48px
            ),
            radial-gradient(
                circle at 15% 8%,
                rgba(56, 189, 248, 0.10) 0%,
                transparent 35%
            ),
            radial-gradient(
                circle at 88% 78%,
                rgba(56, 189, 248, 0.07) 0%,
                transparent 35%
            ),
            #0A0E17;
    }

    /* ============ HERO SECTION ============ */

    .hero-section {
        width: 100%;
        display: grid;
        grid-template-columns: 1fr 2fr 1fr;
        align-items: center;
        gap: 2rem;
        min-height: 210px;
        margin-bottom: 0.5rem;
    }

    .hero-left {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: center;
    }

    .hero-center {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
    }

    .hero-right {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        justify-content: center;
        text-align: right;
    }

    .hero-badge {
        display: inline-block;
        width: fit-content;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #7DD3FC;
        background: rgba(56, 189, 248, 0.08);
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 999px;
        padding: 0.35rem 1rem;
        margin-bottom: 0.65rem;
    }

    .hero-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2.8rem;
        line-height: 1.15;
        font-weight: 700;
        color: #F1F5F9;
        margin: 0;
        text-align: center;
    }

    .hero-title .accent {
        color: #38BDF8;
    }

    .hero-subtitle {
        color: #94A3B8;
        font-size: 0.92rem;
        max-width: 480px;
        line-height: 1.65;
        margin: 0;
        text-align: right;
    }

    .hero-divider {
        height: 1px;
        width: 100%;
        background: linear-gradient(
            90deg,
            #38BDF8 0%,
            rgba(56, 189, 248, 0.25) 50%,
            transparent 100%
        );
        margin: 0.55rem 0 0.75rem 0;
    }

    .hero-illustration {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        width: 100%;
        padding: 0.5rem;
    }

    .hero-illustration svg {
        width: 180px;
        max-width: 100%;
        opacity: 0.9;
    }

    /* ============ SECTION TITLES ============ */

    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif;
        color: #E2E8F0 !important;
        letter-spacing: -0.3px;
    }

    .stCaption, [data-testid="stCaptionContainer"] {
        color: #7DD3FC !important;
    }

    /* ============ TAB jadi nav pill ============ */

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid #1F2937;
    }

    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        color: #94A3B8;
        border-radius: 8px 8px 0 0;
        padding: 10px 18px;
    }

    .stTabs [aria-selected="true"] {
        color: #38BDF8 !important;
        background-color: rgba(56, 189, 248, 0.08);
        border-bottom: 2px solid #38BDF8 !important;
    }

    /* ============ TOMBOL: pill shape ============ */

    .stButton > button {
        background-color: transparent;
        color: #38BDF8;
        border: 1px solid #38BDF8;
        border-radius: 999px;
        font-weight: 600;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background-color: #38BDF8;
        color: #0A0E17;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.5);
    }

    /* ============ INPUT & UPLOADER ============ */

    .stTextInput input,
    .stTextArea textarea {
        background-color: #111827 !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
        color: #E5E7EB !important;
    }

    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: #38BDF8 !important;
        box-shadow: 0 0 0 1px #38BDF8 !important;
    }

    [data-testid="stFileUploader"] {
        border: 1px dashed #1F2937;
        border-radius: 12px;
        padding: 1rem;
        background-color: rgba(17, 24, 39, 0.4);
    }

    /* ============ OUTPUT BOX ============ */

    .output-image-box {
        width: 100%;
        min-height: 380px;
        background: rgba(17, 24, 39, 0.65);
        border: 1px solid #1F2937;
        border-radius: 14px;
        padding: 1.25rem;
        display: flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
        margin-bottom: 1rem;
    }

    .output-image-box img {
        max-width: 100%;
        max-height: 520px;
        object-fit: contain;
        border-radius: 10px;
    }

    .output-placeholder {
        width: 100%;
        min-height: 380px;
        background: rgba(17, 24, 39, 0.45);
        border: 1px dashed #334155;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 2rem;
        box-sizing: border-box;
        color: #64748B;
    }

    .extract-output-box {
        width: 100%;
        min-height: 380px;
        background: rgba(17, 24, 39, 0.45);
        border: 1px dashed #334155;
        border-radius: 14px;
        padding: 1.25rem;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        color: #64748B;
    }

    .extract-output-content {
        width: 100%;
        color: #7DD3FC;
        line-height: 1.6;
        word-break: break-word;
    }

    .output-result-text {
        color: #7DD3FC;
        font-size: 0.9rem;
        line-height: 1.6;
        margin: 0.5rem 0 1.25rem 0;
        text-align: left;
    }

    /* ============ DATAFRAME & METRIC ============ */

    .stDataFrame {
        border: 1px solid #1F2937;
        border-radius: 10px;
        overflow: hidden;
    }

    [data-testid="stMetric"] {
        background-color: #111827;
        border: 1px solid #1F2937;
        border-radius: 10px;
        padding: 1rem;
    }

    .stAlert {
        border-radius: 10px;
        border: 1px solid #1F2937;
    }

    /* ============ WELCOME SCREEN ============ */

    .welcome-wrap {
        position: relative;
        width: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        overflow: visible;
        padding: 0;
        box-sizing: border-box;
    }

    /* Welcome screen: centered vertically, below Streamlit's header. */
    div.st-key-welcome_screen {
        margin-top: 3.75rem !important;              /* tinggi header Streamlit */
        min-height: calc(100vh - 5rem) !important;
        height: auto !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;          /* bikin di tengah vertikal */
        padding: 1rem 0 !important;
        box-sizing: border-box !important;
    }

    /* Tiap child (card, tombol, fitur) full width & tetap rapi di tengah */
    div.st-key-welcome_screen > [data-testid="stElementContainer"],
    div.st-key-welcome_screen > [data-testid="stHorizontalBlock"] {
        width: 100% !important;
    }

    .welcome-card {
        position: relative;
        z-index: 2;
        width: min(540px, 100%);
        margin: 0 auto;
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(56, 189, 248, 0.18);
        border-radius: 20px;
        box-shadow:
            0 24px 80px rgba(0, 0, 0, 0.35),
            inset 0 1px 0 rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(14px);
        overflow: hidden;
        flex-shrink: 0;
    }

    .welcome-illustration {
        width: 100%;
        padding: 0.35rem 0 0;
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: visible;
        box-sizing: border-box;
    }

    .welcome-illustration svg {
        display: block;
        width: min(170px, 40%);
        height: auto;
    }

    .welcome-content {
        text-align: center;
        padding: 0 1.25rem 0.8rem;
    }

    .welcome-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(1.85rem, 3.5vw, 2.65rem);
        line-height: 1.05;
        font-weight: 700;
        color: #F1F5F9;
        margin: 0.05rem 0 0.25rem;
        letter-spacing: -1.5px;
    }

    .welcome-title span {
        color: #38BDF8;
    }

    .welcome-tagline {
        color: #CBD5E1;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.9rem;
        margin: 0 0 0.25rem;
    }

    .welcome-description {
        display: block;
        width: min(560px, 100%);
        max-width: 560px;
        margin: 0 auto !important;
        color: #94A3B8;
        font-size: 0.76rem;
        line-height: 1.45;
        text-align: center !important;
    }

    .hero-description {
        display: block;
        width: 100%;
        max-width: none;
        margin: 4px auto 0 !important;
        padding: 0;
        box-sizing: border-box;
        color: #94A3B8;
        font-size: 0.78rem;
        line-height: 1.35;
        text-align: center !important;
        white-space: nowrap;
    }

    .welcome-glow {
        position: absolute;
        z-index: 0;
        width: 320px;
        height: 320px;
        border-radius: 50%;
        filter: blur(70px);
        pointer-events: none;
        opacity: 0.18;
        background: #38BDF8;
    }

    .welcome-glow-one {
        top: 8%;
        left: 5%;
    }

    .welcome-glow-two {
        right: 5%;
        bottom: 5%;
        opacity: 0.10;
    }

    .welcome-features {
        position: relative;
        z-index: 2;
        display: flex;
        justify-content: center;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-top: 0.4rem;
        color: #64748B;
        font-size: 0.68rem;
        letter-spacing: 0.04em;
    }

    .welcome-features span {
        padding: 0.4rem 0.75rem;
        border: 1px solid #1E293B;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.55);
    }

    /* Keep the welcome controls close to the card instead of pushing them to
       the bottom of a full-height wrapper. */
    .welcome-wrap + div[data-testid="stHorizontalBlock"] {
        margin-top: 1rem !important;
        margin-bottom: 0 !important;
        position: relative;
        z-index: 5;
    }

    .welcome-wrap + div[data-testid="stHorizontalBlock"] button {
        height: 42px !important;
        min-height: 42px !important;
    }

    .welcome-features {
        margin-top: 0.7rem;
    }

    /* Main screen: compact, clearly visible back button. */
    div.st-key-back_to_welcome {
        margin-top: 0 !important;
        margin-bottom: 0.15rem !important;
        padding-top: 0 !important;
    }

    div.st-key-back_to_welcome button {
        width: 34px !important;
        min-width: 34px !important;
        max-width: 34px !important;
        height: 34px !important;
        min-height: 34px !important;
        padding: 0 !important;
        margin: 0 !important;
        border-radius: 8px !important;
        border: 1px solid #334155 !important;
        background: rgba(15, 23, 42, 0.75) !important;
        color: #E2E8F0 !important;
        font-size: 17px !important;
        line-height: 1 !important;
    }

    div.st-key-back_to_welcome button:hover {
        border-color: #38BDF8 !important;
        background: rgba(56, 189, 248, 0.10) !important;
        color: #38BDF8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.18) !important;
    }

    div.st-key-welcome_screen .stButton {
        width: min(440px, 82vw) !important;
        margin: 1rem auto 0 !important;
    }

    div.st-key-welcome_screen .stButton > button {
        width: 100% !important;
        height: 42px !important;
        min-height: 42px !important;
    }

    div.st-key-welcome_screen .welcome-features {
        margin-top: 0.8rem;
    }

    /* ============ MAIN HEADER / BACK ARROW ============ */
    .main-header-badge {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 36px;
    }

    div.st-key-back_to_welcome {
        margin: 0 !important;
        padding: 0 !important;
    }

    div.st-key-back_to_welcome .stButton {
        width: 36px !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    div.st-key-back_to_welcome button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 36px !important;
        min-width: 36px !important;
        max-width: 36px !important;
        height: 36px !important;
        min-height: 36px !important;
        padding: 0 !important;
        margin: 0 !important;
        border-radius: 8px !important;
        border: 1px solid #475569 !important;
        background: #111827 !important;
        color: #E2E8F0 !important;
        font-size: 19px !important;
        line-height: 1 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,.25) !important;
        opacity: 1 !important;
        visibility: visible !important;
    }

    div.st-key-back_to_welcome button:hover {
        background: #1E293B !important;
        color: #38BDF8 !important;
        border-color: #38BDF8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.25) !important;
    }

    /* Main hero sits immediately below the header row. */
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        padding-top: 0 !important;
    }

    /* ============ RESPONSIVE ============ */

    @media (max-width: 900px) {
        [data-testid="BlockContainer"] {
            padding: 0.5rem 1.25rem 2rem 1.25rem !important;
        }

        div.st-key-welcome_screen {
            min-height: calc(100vh - 5rem) !important;
            padding-top: 0.5rem !important;
        }

        .welcome-wrap {
            min-height: auto;
        }

        .hero-section {
            grid-template-columns: 1fr;
            gap: 1.5rem;
            min-height: auto;
        }

        .hero-left,
        .hero-center,
        .hero-right {
            align-items: center;
            text-align: center;
        }

        .hero-title {
            font-size: 2.2rem;
        }

        .hero-subtitle {
            text-align: center;
        }

        .hero-illustration {
            justify-content: center;
        }

        .welcome-card {
            width: min(540px, 100%);
        }

        .welcome-illustration svg {
            width: min(160px, 42%);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
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
        stego_image = embed_plaintext(cover_image, message, stego_key)
        recovered = extract_plaintext(stego_image, stego_key)
        extraction_success = recovered == message

        mse = calculate_mse(cover_image, stego_image)
        psnr = calculate_psnr(cover_image, stego_image)

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
    st.header("Embed & Send")

    col1, col2 = st.columns([1, 1], gap="large")

    stego_image = None
    cover_image = None
    mse = psnr = None

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
                elif st.button("Embed Message", type="primary"):
                    with st.spinner("Embedding message..."):
                        stego_image = embed_plaintext(
                            cover_image, message, stego_key_bytes
                        )
                        mse = calculate_mse(cover_image, stego_image)
                        psnr = calculate_psnr(cover_image, stego_image)

            except Exception as e:
                st.error(f"Error: {str(e)}")
        else:
            st.warning("Please provide cover image, message, and stego key")

    with col2:
        st.subheader("Output")

        if stego_image is not None:
            st.success("Message embedded successfully!")

            metric_col1, metric_col2 = st.columns(2)

            with metric_col1:
                st.metric("MSE", f"{mse:.4f}")

            with metric_col2:
                st.metric("PSNR", f"{psnr:.2f} dB")

            # ================================================================
            # KOTAK OUTPUT STEGO IMAGE
            # ================================================================

            st.markdown(
                '<div class="output-image-box">',
                unsafe_allow_html=True,
            )

            st.image(
                stego_image,
                use_container_width=True,
            )

            st.markdown(
                "</div>",
                unsafe_allow_html=True,
            )

            # Teks hasil penyisipan berada di bawah kotak
            st.markdown(
                """
                <p class="output-result-text">
                    Hasil penyisipan pesan ditampilkan pada gambar stego di atas.
                    Pesan telah disisipkan ke dalam citra menggunakan LSB
                    setelah dienkripsi dengan AES-256-GCM.
                </p>
                """,
                unsafe_allow_html=True,
            )

            stego_bytes = image_to_bytes(stego_image, "PNG")

            st.download_button(
                label="Download Stego Image (PNG)",
                data=stego_bytes,
                file_name="stego_image.png",
                mime="image/png",
            )

        else:
            st.markdown(
                """
                <div class="output-placeholder">
                    <div>
                        <strong>Output</strong><br><br>
                        Hasil penyisipan bakal muncul di sini setelah kamu klik
                        <b>Embed Message</b>.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================================
# TAB 2: EXTRACT & READ
# ============================================================================


def tab_extract_read() -> None:
    """Tab 2: Extract and decrypt a message."""
    st.header("Extract & Read")

    col1, col2 = st.columns([1, 1], gap="large")

    plaintext = None
    extraction_error = None

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
                        except Exception as e:
                            extraction_error = e

            except Exception as e:
                st.error(f"Error: {str(e)}")
        else:
            st.warning("Please provide stego image and stego key")

    with col2:
        st.subheader("Output")

        if plaintext is not None:
            safe_plaintext = html.escape(plaintext).replace("\n", "<br>")
            st.markdown(
                '<div class="extract-output-box">'
                '<div class="extract-output-content">'
                '<strong>Plaintext</strong><br><br>'
                f'{safe_plaintext}'
                '</div></div>',
                unsafe_allow_html=True,
            )

        elif extraction_error is not None:
            st.markdown(
                '<div class="extract-output-box">'
                '<div class="extract-output-content">'
                '<strong>Output</strong><br><br>'
                'Authentication failed. The stego-key may be incorrect or the payload may have been modified.'
                '</div></div>',
                unsafe_allow_html=True,
            )

        else:
            st.markdown(
                '<div class="extract-output-box">'
                '<div class="extract-output-content">'
                '<strong>Output</strong><br><br>'
                'Pesan hasil ekstraksi bakal muncul di sini.'
                '</div></div>',
                unsafe_allow_html=True,
            )


# ============================================================================
# TAB 3: LABORATORY & SECURITY TESTING
# ============================================================================


def tab_laboratory() -> None:
    """Tab 3: Laboratory experiments and security testing."""
    st.header("Laboratory & Security Testing")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "Histogram Analysis",
            "LSB Bit-Plane",
            "JPEG Attack",
            "Experiment Runner",
            "Chi-Square Test",
        ]
    )

    with tab1:
        st.subheader("RGB Histogram Analysis")

        cover_upload = st.file_uploader(
            "Upload Cover Image",
            type=["png", "bmp"],
            key="hist_cover",
        )

        stego_upload = st.file_uploader(
            "Upload Stego Image",
            type=["png", "bmp"],
            key="hist_stego",
        )

        if cover_upload and stego_upload:
            try:
                cover_image = Image.open(cover_upload).convert("RGB")
                stego_image = Image.open(stego_upload).convert("RGB")

                comparison = compare_rgb_histograms(
                    cover_image,
                    stego_image,
                )

                fig, axes = plt.subplots(
                    2,
                    3,
                    figsize=(15, 8),
                )

                channels = ["R", "G", "B"]
                colors = ["red", "green", "blue"]

                for i, (channel, color) in enumerate(
                    zip(channels, colors)
                ):
                    axes[0, i].bar(
                        range(256),
                        comparison.cover.for_channel(channel),
                        color=color,
                        alpha=0.7,
                        label="Cover",
                    )

                    axes[0, i].set_title(
                        f"Cover {channel} Channel"
                    )
                    axes[0, i].set_xlabel("Intensity")
                    axes[0, i].set_ylabel("Count")

                    axes[1, i].bar(
                        range(256),
                        comparison.stego.for_channel(channel),
                        color=color,
                        alpha=0.7,
                        label="Stego",
                    )

                    axes[1, i].set_title(
                        f"Stego {channel} Channel"
                    )
                    axes[1, i].set_xlabel("Intensity")
                    axes[1, i].set_ylabel("Count")

                plt.tight_layout()
                st.pyplot(fig)

                st.info(
                    f"**Total changed bins:** "
                    f"{comparison.changed_bin_count()} of 768"
                )

            except Exception as e:
                st.error(f"Error: {str(e)}")

    with tab2:
        st.subheader("LSB Bit-Plane Analysis")

        cover_upload = st.file_uploader(
            "Upload Cover Image",
            type=["png", "bmp"],
            key="plane_cover",
        )

        stego_upload = st.file_uploader(
            "Upload Stego Image",
            type=["png", "bmp"],
            key="plane_stego",
        )

        if cover_upload and stego_upload:
            try:
                cover_image = Image.open(
                    cover_upload
                ).convert("RGB")

                stego_image = Image.open(
                    stego_upload
                ).convert("RGB")

                comparison = compare_lsb_bit_planes(
                    cover_image,
                    stego_image,
                )

                st.subheader("Cover LSB Planes")

                col1, col2, col3 = st.columns(3)

                for i, (channel, name) in enumerate(
                    [
                        (0, "Red"),
                        (1, "Green"),
                        (2, "Blue"),
                    ]
                ):
                    with (
                        col1
                        if i == 0
                        else col2
                        if i == 1
                        else col3
                    ):
                        st.image(
                            plane_to_image(
                                comparison.cover.for_channel(
                                    "RGB"[i]
                                )
                            ),
                            caption=f"{name} Channel",
                            use_container_width=True,
                        )

                st.subheader("Stego LSB Planes")

                col1, col2, col3 = st.columns(3)

                for i, (channel, name) in enumerate(
                    [
                        (0, "Red"),
                        (1, "Green"),
                        (2, "Blue"),
                    ]
                ):
                    with (
                        col1
                        if i == 0
                        else col2
                        if i == 1
                        else col3
                    ):
                        st.image(
                            plane_to_image(
                                comparison.stego.for_channel(
                                    "RGB"[i]
                                )
                            ),
                            caption=f"{name} Channel",
                            use_container_width=True,
                        )

                st.subheader("Changed LSB Pixels")

                st.image(
                    plane_to_image(
                        comparison.channel_change_mask
                    ),
                    caption=(
                        "Pixels with LSB modifications "
                        "(white = changed)"
                    ),
                    use_container_width=True,
                )

                st.info(
                    f"**Changed pixels:** "
                    f"{comparison.changed_pixel_count()} | "
                    f"**Changed channels:** "
                    f"{comparison.changed_channel_count}"
                )

            except Exception as e:
                st.error(f"Error: {str(e)}")

    with tab3:
        st.subheader("JPEG Fragility Attack")

        cover_upload = st.file_uploader(
            "Upload Cover Image",
            type=["png", "bmp"],
            key="jpeg_cover",
        )

        message = st.text_area(
            "Message to Test",
            height=50,
            key="jpeg_message",
        )

        stego_key = st.text_input(
            "Stego Key",
            type="password",
            key="jpeg_key",
        )

        if cover_upload and message and stego_key:
            try:
                cover_image = Image.open(
                    cover_upload
                ).convert("RGB")

                stego_key_bytes = stego_key.encode("utf-8")

                if st.button(
                    "Run JPEG Attack Test",
                    type="primary",
                ):
                    with st.spinner(
                        "Running JPEG attack test..."
                    ):
                        result = run_jpeg_fragility_test(
                            cover_image,
                            message,
                            stego_key_bytes,
                            quality=85,
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
                            st.warning(
                                "⚠️ JPEG attack successfully destroyed the payload!"
                            )
                        else:
                            st.success(
                                "✅ Payload survived JPEG compression!"
                            )

            except Exception as e:
                st.error(f"Error: {str(e)}")

    with tab4:
        st.subheader("Laboratory Experiment Runner")

        image_dir = "data/test_images"

        try:
            import os

            image_files = [
                f
                for f in os.listdir(image_dir)
                if f.lower().endswith(
                    (".png", ".bmp")
                )
            ]

        except FileNotFoundError:
            st.error(
                f"Test images directory not found: {image_dir}"
            )
            image_files = []

        if image_files:
            selected_images = st.multiselect(
                "Select Test Images",
                image_files,
                default=image_files[
                    : min(5, len(image_files))
                ],
            )

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

            if st.button(
                "Run Laboratory Experiments",
                type="primary",
            ):
                if (
                    not selected_images
                    or not message_sizes
                ):
                    st.warning(
                        "Please select at least one image "
                        "and one message size"
                    )

                else:
                    stego_key_bytes = (
                        stego_key.encode("utf-8")
                    )

                    results: list[dict[str, Any]] = []

                    progress_bar = st.progress(0)

                    total_cases = (
                        len(selected_images)
                        * len(message_sizes)
                    )

                    current_case = 0

                    for image_file in selected_images:
                        try:
                            cover_path = (
                                f"{image_dir}/{image_file}"
                            )

                            cover_image = Image.open(
                                cover_path
                            ).convert("RGB")

                            width, height = (
                                cover_image.size
                            )

                            capacity = (
                                width * height * 3
                            )

                            for msg_size in message_sizes:
                                current_case += 1

                                progress = (
                                    current_case
                                    / total_cases
                                )

                                progress_bar.progress(
                                    progress
                                )

                                message = (
                                    "X" * msg_size
                                )

                                result = (
                                    run_laboratory_experiment(
                                        cover_image,
                                        message,
                                        stego_key_bytes,
                                    )
                                )

                                payload_bits = (
                                    34
                                    + msg_size
                                    + 16
                                ) * 8

                                capacity_utilization = (
                                    (
                                        payload_bits
                                        / capacity
                                    ) * 100
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
                                            capacity_utilization,
                                            2,
                                        ),
                                        "mse": (
                                            round(
                                                result["mse"],
                                                4,
                                            )
                                            if result["mse"]
                                            is not None
                                            else None
                                        ),
                                        "psnr": (
                                            round(
                                                result["psnr"],
                                                2,
                                            )
                                            if result["psnr"]
                                            is not None
                                            else None
                                        ),
                                        "embed_success": result[
                                            "embed_success"
                                        ],
                                        "extract_success": result[
                                            "extract_success"
                                        ],
                                        "jpeg_attack_result": (
                                            "destroyed"
                                            if result[
                                                "jpeg_destroyed_payload"
                                            ]
                                            else "survived"
                                        ),
                                        "error": result[
                                            "error"
                                        ],
                                    }
                                )

                        except Exception as e:
                            st.error(
                                f"Error processing "
                                f"{image_file}: {str(e)}"
                            )

                    progress_bar.empty()

                    st.subheader(
                        "Experiment Results"
                    )

                    df = pd.DataFrame(results)

                    st.dataframe(
                        df,
                        use_container_width=True,
                    )

                    if st.button(
                        "Download Results as XLSX"
                    ):
                        output = io.BytesIO()

                        with pd.ExcelWriter(
                            output,
                            engine="openpyxl",
                        ) as writer:
                            df.to_excel(
                                writer,
                                index=False,
                                sheet_name="Results",
                            )

                        output.seek(0)

                        st.download_button(
                            label="Download XLSX",
                            data=output.getvalue(),
                            file_name=(
                                "laboratory_results.xlsx"
                            ),
                            mime=(
                                "application/"
                                "vnd.openxmlformats-officedocument."
                                "spreadsheetml.sheet"
                            ),
                        )

    with tab5:
        st.subheader(
            "Chi-Square Steganalysis (Pairs of Values)"
        )

        st.caption(
            "Test ini cuma butuh SATU citra (nggak perlu cover) — persis "
            "seperti attacker yang cuma punya citra hasil unduhan dan curiga "
            "ada pesan tersembunyi di dalamnya."
        )

        test_upload = st.file_uploader(
            "Upload Citra untuk Dianalisis",
            type=["png", "bmp"],
            key="chi_image",
        )

        if test_upload:
            try:
                test_image = Image.open(
                    test_upload
                ).convert("RGB")

                report = compute_chi_square_test(
                    test_image
                )

                rows = chi_square_report_to_rows(
                    report
                )

                st.subheader(
                    "Hasil per Channel"
                )

                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                )

                suspected = (
                    report.suspected_channel_count()
                )

                if suspected >= 2:
                    st.warning(
                        f"⚠️ {suspected} dari 3 channel menunjukkan "
                        f"p-value tinggi — citra ini KEMUNGKINAN BESAR "
                        "mengandung pesan tersembunyi."
                    )
                else:
                    st.success(
                        "✅ Distribusi Pairs-of-Values terlihat natural — "
                        "citra ini kemungkinan besar TIDAK mengandung pesan."
                    )

            except Exception as e:
                st.error(
                    f"Error: {str(e)}"
                )

        else:
            st.warning(
                "Silakan upload citra untuk dianalisis"
            )


# ============================================================================
# MAIN APP
# ============================================================================


def show_welcome() -> None:
    """Display the StegoChat welcome screen before entering the main app."""
    with st.container(key="welcome_screen"):
        st.markdown(
            '<div class="welcome-wrap">'
            '<div class="welcome-glow welcome-glow-one"></div>'
            '<div class="welcome-glow welcome-glow-two"></div>'
            '<div class="welcome-card">'
            '<div class="welcome-illustration">'
            '<svg viewBox="0 0 520 300" xmlns="http://www.w3.org/2000/svg" aria-label="StegoChat illustration">'
            '<defs>'
            '<linearGradient id="screenGlow" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0%" stop-color="#38BDF8" stop-opacity="0.28"/>'
            '<stop offset="100%" stop-color="#0EA5E9" stop-opacity="0.03"/>'
            '</linearGradient>'
            '<filter id="softGlow">'
            '<feGaussianBlur stdDeviation="7" result="blur"/>'
            '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
            '</filter>'
            '</defs>'
            '<circle cx="260" cy="150" r="110" fill="#38BDF8" fill-opacity="0.06" filter="url(#softGlow)"/>'
            '<rect x="110" y="48" width="300" height="204" rx="20" fill="#0F172A" stroke="#334155" stroke-width="2"/>'
            '<rect x="126" y="64" width="268" height="172" rx="13" fill="url(#screenGlow)" stroke="#1E293B"/>'
            '<circle cx="146" cy="82" r="4" fill="#38BDF8"/>'
            '<circle cx="160" cy="82" r="4" fill="#334155"/>'
            '<circle cx="174" cy="82" r="4" fill="#334155"/>'
            '<rect x="154" y="110" width="86" height="74" rx="12" fill="none" stroke="#38BDF8" stroke-width="4"/>'
            '<path d="M174 110V95C174 76 220 76 220 95V110" fill="none" stroke="#7DD3FC" stroke-width="4" stroke-linecap="round"/>'
            '<circle cx="197" cy="143" r="7" fill="#38BDF8"/>'
            '<path d="M197 150V166" stroke="#38BDF8" stroke-width="4" stroke-linecap="round"/>'
            '<rect x="270" y="112" width="86" height="9" rx="4.5" fill="#38BDF8" fill-opacity="0.75"/>'
            '<rect x="270" y="132" width="66" height="9" rx="4.5" fill="#475569"/>'
            '<rect x="270" y="152" width="76" height="9" rx="4.5" fill="#475569"/>'
            '<rect x="270" y="172" width="48" height="9" rx="4.5" fill="#475569"/>'
            '<path d="M84 98h22M414 98h22M84 202h22M414 202h22" stroke="#38BDF8" stroke-opacity="0.45" stroke-width="2" stroke-linecap="round"/>'
            '<circle cx="74" cy="98" r="3" fill="#38BDF8"/>'
            '<circle cx="446" cy="98" r="3" fill="#38BDF8"/>'
            '<circle cx="74" cy="202" r="3" fill="#38BDF8"/>'
            '<circle cx="446" cy="202" r="3" fill="#38BDF8"/>'
            '<path d="M240 268h40" stroke="#38BDF8" stroke-opacity="0.7" stroke-width="3" stroke-linecap="round"/>'
            '</svg>'
            '</div>'
            '<div class="welcome-content">'
            '<div class="hero-badge">AES-256-GCM · LSB STEGANOGRAPHY</div>'
            '<h1 class="welcome-title">Welcome to <span>StegoChat</span></h1>'
            '<p class="welcome-tagline">Secret messages, hidden in plain sight.</p>'
            '<p class="welcome-description">'
            'Encrypt your message with AES-256-GCM, then hide it inside an ordinary RGB image. '
            'Your message stays invisible to the eye and unreadable without the key.'
            '</p>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        start_col_left, start_col, start_col_right = st.columns([1, 1.8, 1])
        with start_col:
            if st.button(
                "START STEGOCHAT  →",
                type="primary",
                use_container_width=True,
                key="start_stegochat",
            ):
                st.session_state["started"] = True
                st.rerun()

        st.markdown(
            '<div class="welcome-features">'
            '<span>🔐 AES-256-GCM</span>'
            '<span>🖼️ LSB STEGANOGRAPHY</span>'
            '<span>🛡️ AUTHENTICATED PAYLOAD</span>'
            '</div>',
            unsafe_allow_html=True,
        )


def main() -> None:
    """Main application entry point."""

    if "started" not in st.session_state:
        st.session_state["started"] = False

    if not st.session_state["started"]:
        show_welcome()
        return

    # Main header: arrow and AES badge share one horizontal line.
    header_left, header_center, header_right = st.columns(
        [0.35, 2, 0.35],
        gap="small",
    )

    with header_left:
        if st.button(
            "←",
            key="back_to_welcome",
            help="Kembali ke halaman awal",
        ):
            st.session_state["started"] = False
            st.rerun()

    with header_center:
        st.markdown(
            '<div class="main-header-badge">'
            '<div class="hero-badge">AES-256-GCM · LSB STEGANOGRAPHY</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with header_right:
        st.empty()

    st.markdown(
        '<div class="main-header-center">'
        '<h1 class="hero-title">Secret messages,<br>'
        '<span class="accent">hidden in plain sight.</span></h1>'
        '<div class="hero-description">'
        'Encrypt a message with AES-256-GCM and hide it inside an ordinary RGB image — invisible to the eye, unreadable without the key.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="hero-divider"></div>',
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(
        [
            "Embed & Send",
            "Extract & Read",
            "Laboratory & Security Testing",
        ]
    )

    with tab1:
        tab_embed_send()

    with tab2:
        tab_extract_read()

    with tab3:
        tab_laboratory()


if __name__ == "__main__":
    main()