"""Tab Streamlit untuk menyisipkan dan membaca pesan StegoChat."""

from __future__ import annotations

import html
import io

import streamlit as st
from cryptography.exceptions import InvalidTag
from PIL import Image

from analysis.metrics import calculate_mse, calculate_psnr
from stego.capacity import capacity_bits, max_plaintext_bytes, required_bits
from stego.payload import AUTH_TAG_LENGTH
from stegochat.core import embed_plaintext, extract_plaintext

# FUNGSI BANTUAN
# ============================================================================


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Simpan gambar Pillow ke buffer memori agar dapat ditampilkan dan diunduh."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def clear_embed_result() -> None:
    """Hapus hasil embed lama saat cover, pesan, atau kunci berubah agar output tetap sesuai input."""
    st.session_state.pop("embed_result", None)


# ============================================================================
# TAB 1: PENYISIPAN PESAN
# ============================================================================


def tab_embed_send() -> None:
    """Tampilkan input cover dan pesan, validasi kapasitas, lalu jalankan embedding.

    Hasil PNG serta MSE dan PSNR disimpan di session_state supaya unduhan
    atau rerun biasa tidak menghilangkan output.
    """
    st.header("Embed & Send")

    col1, col2 = st.columns([1, 1], gap="large")

    cover_image = None

    with col1:
        st.subheader("Input")

        cover_upload = st.file_uploader(
            "Upload Cover Image (PNG/BMP)",
            type=["png", "bmp"],
            help="Upload a PNG or BMP image in RGB mode",
            key="embed_cover",
            on_change=clear_embed_result,
        )

        if cover_upload is not None:
            try:
                cover_image = Image.open(
                    io.BytesIO(cover_upload.getvalue())
                ).convert("RGB")
                st.markdown("**Cover · Citra asli**")
                st.image(cover_image, width="stretch")
            except Exception as error:
                st.error(f"Unable to read cover image: {error}")

        message = st.text_area(
            "Message to Hide",
            height=100,
            placeholder="Enter your secret message here...",
            key="embed_message",
            on_change=clear_embed_result,
        )

        stego_key = st.text_input(
            "Stego Key (Password)",
            type="password",
            placeholder="Enter a shared secret key",
            key="embed_key",
            on_change=clear_embed_result,
        )

        if cover_upload and cover_image is not None and message and stego_key:
            try:
                stego_key_bytes = stego_key.encode("utf-8")

                width, height = cover_image.size
                capacity = capacity_bits(width, height)
                # Hitung semua byte: teks UTF-8, tag GCM, dan header dari modul kapasitas.
                payload_bits = required_bits(
                    len(message.encode("utf-8")) + AUTH_TAG_LENGTH
                )

                st.info(
                    f"**Image Size:** {width}x{height} | "
                    f"**Capacity:** {capacity} bits | "
                    f"**Required:** {payload_bits} bits"
                )

                if payload_bits > capacity:
                    st.error(
                        f"Message too large! Maximum message size: "
                        f"{max_plaintext_bytes(width, height)} UTF-8 bytes"
                    )
                elif st.button("Embed Message", type="primary"):
                    clear_embed_result()
                    with st.spinner("Embedding message..."):
                        stego_image = embed_plaintext(
                            cover_image, message, stego_key_bytes
                        )
                        mse = calculate_mse(cover_image, stego_image)
                        psnr = calculate_psnr(cover_image, stego_image)
                        # Simpan PNG dan metrik sekali agar rerun unduhan memakai hasil yang sama.
                        st.session_state["embed_result"] = {
                            "image_bytes": image_to_bytes(stego_image, "PNG"),
                            "mse": mse,
                            "psnr": psnr,
                        }

            except Exception as e:
                st.error(f"Error: {str(e)}")
        else:
            clear_embed_result()
            st.warning("Please provide cover image, message, and stego key")

    # Streamlit menjalankan ulang skrip saat unduhan atau widget memicu rerun.
    # Ambil hasil sesi agar stego tidak hilang atau dienkripsi ulang.
    embed_result = st.session_state.get("embed_result")

    with col2:
        st.subheader("Output")

        if embed_result is not None:
            st.markdown(
                f"""
                <div class="embed-output-summary">
                    <div class="embed-success-banner">Message embedded successfully!</div>
                    <div class="embed-metrics">
                        <div class="embed-metric-card">
                            <div class="embed-metric-label">MSE</div>
                            <div class="embed-metric-value">{embed_result['mse']:.6g}</div>
                        </div>
                        <div class="embed-metric-card">
                            <div class="embed-metric-label">PSNR</div>
                            <div class="embed-metric-value">{embed_result['psnr']:.2f} dB</div>
                        </div>
                    </div>
                    <div class="embed-image-label">Stego · Hasil penyisipan</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.image(embed_result["image_bytes"], width="stretch")

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

            st.download_button(
                label="Download Stego Image (PNG)",
                data=embed_result["image_bytes"],
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
# TAB 2: EKSTRAKSI DAN PEMBACAAN PESAN
# ============================================================================


def clear_extract_result() -> None:
    """Hapus plaintext atau error lama ketika gambar stego atau kunci diganti."""
    st.session_state.pop("extract_result", None)


def tab_extract_read() -> None:
    """Tampilkan stego, jalankan ekstraksi dan dekripsi, lalu tampilkan pesan atau error.

    Kegagalan gambar, format payload, dan autentikasi ditangani terpisah.
    Teks hasil di-escape sebelum dimasukkan ke HTML.
    """
    st.header("Extract & Read")

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Input")

        stego_upload = st.file_uploader(
            "Upload Stego Image",
            type=["png", "bmp"],
            help="Upload the stego image containing the hidden message",
            key="extract_image",
            on_change=clear_extract_result,
        )

        if stego_upload is not None:
            st.markdown("**Stego · Gambar yang diekstrak**")
            try:
                with Image.open(io.BytesIO(stego_upload.getvalue())) as source:
                    st.image(source.convert("RGB"), width="stretch")
            except OSError:
                st.caption("Pratinjau tidak tersedia untuk file gambar ini.")

        stego_key = st.text_input(
            "Stego Key (Password)",
            type="password",
            placeholder="Enter the shared secret key",
            key="extract_key",
            on_change=clear_extract_result,
        )

        ready = bool(stego_upload and stego_key)
        if not ready:
            clear_extract_result()
            st.warning("Please provide stego image and stego key")

        if st.button("Extract & Decrypt", type="primary", disabled=not ready):
            clear_extract_result()
            plaintext = None
            extraction_error = None
            with st.spinner("Extracting message..."):
                try:
                    with Image.open(io.BytesIO(stego_upload.getvalue())) as source:
                        stego_image = source.convert("RGB")
                    plaintext = extract_plaintext(
                        stego_image, stego_key.encode("utf-8")
                    )
                # Bedakan data gagal autentikasi, gambar tidak terbaca, dan payload tidak valid.
                except InvalidTag:
                    extraction_error = (
                        "Autentikasi pesan gagal. Kunci tidak cocok atau payload "
                        "telah berubah. Pesan tidak dapat ditampilkan."
                    )
                except OSError:
                    extraction_error = (
                        "File gambar tidak dapat dibaca. Unggah kembali file PNG/BMP "
                        "hasil unduhan Embed & Send."
                    )
                except ValueError:
                    extraction_error = (
                        "Payload StegoChat tidak dapat dibaca dengan kunci ini. "
                        "Pastikan gambar adalah hasil unduhan Embed & Send, "
                        "bukan cover asli, dan kunci sama persis termasuk spasi "
                        "serta huruf besar/kecil. Pengubahan ukuran atau kompresi "
                        "gambar juga dapat merusak payload."
                    )
                except Exception:
                    extraction_error = (
                        "Terjadi kesalahan internal saat ekstraksi. "
                        "Coba muat ulang aplikasi dan ulangi proses."
                    )
            st.session_state["extract_result"] = {
                "plaintext": plaintext,
                "error": extraction_error,
            }

    result = st.session_state.get("extract_result", {})
    plaintext = result.get("plaintext")
    extraction_error = result.get("error")

    with col2:
        st.subheader("Output")

        if plaintext is not None:
            # Escape teks pengguna agar isi pesan tidak dijalankan sebagai markup HTML.
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
                f'{html.escape(extraction_error)}'
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
