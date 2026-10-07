"""Pengujian widget Streamlit, perubahan input, dan ketahanan hasil selama rerun."""

import io
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

import laboratory
from analysis.metrics import psnr_from_mse
from stegochat.core import embed_plaintext, extract_plaintext

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def uploaded_cover(size=(64, 64), color=(100, 101, 102)):
    """Buat bytes PNG beserta nama dan MIME untuk menyimulasikan unggahan cover."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return ("cover.png", buffer.getvalue(), "image/png")


def new_app():
    """Buka aplikasi dalam AppTest langsung di halaman utama dan pastikan tidak ada exception."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=20)
    app.session_state["started"] = True
    app.run()
    assert not app.exception
    return app


def test_main_navigation_keeps_native_tabs_and_full_width_content():
    # Identitas khusus membatasi penataan navigasi utama tanpa menyentuh subtab.
    app = new_app()
    main_tabs, laboratory_tabs = app.get("tab_container")
    assert main_tabs.proto.id.endswith("-main_navigation")
    assert not laboratory_tabs.proto.id
    assert main_tabs.proto.width_config.use_stretch
    assert [tab.label for tab in app.tabs[:3]] == [
        "Embed & Send",
        "Extract & Read",
        "Laboratory & Security Testing",
    ]
    assert len(app.tabs) == 8


def button(app, label):
    """Cari widget tombol dari label agar pengujian menekan kontrol yang tepat."""
    return next(widget for widget in app.button if widget.label == label)


def ready_to_embed(app, cover=None, message="hello"):
    """Isi cover, pesan, dan kunci pada widget lalu jalankan ulang sebelum pengujian embedding."""
    app.file_uploader(key="embed_cover").set_value(cover or uploaded_cover())
    app.text_area(key="embed_message").set_value(message)
    app.text_input(key="embed_key").set_value("test-key")
    app.run()
    assert not app.exception


@pytest.mark.parametrize("changed", ["message", "key", "cover", "remove_cover"])
def test_changed_embed_input_clears_result_and_download(changed):
    """Pastikan perubahan input menghapus hasil embed dan unduhan lama."""
    app = new_app()
    ready_to_embed(app)
    button(app, "Embed Message").click().run()
    assert not app.exception
    assert "embed_result" in app.session_state
    if changed == "message":
        app.text_area(key="embed_message").set_value("new message")
    elif changed == "key":
        app.text_input(key="embed_key").set_value("new key")
    elif changed == "cover":
        app.file_uploader(key="embed_cover").set_value(uploaded_cover(color=(10, 20, 30)))
    else:
        app.file_uploader(key="embed_cover").clear()
    app.run()
    assert not app.exception
    assert "embed_result" not in app.session_state
    assert not any(w.label == "Download Stego Image (PNG)" for w in app.download_button)
    assert not any(s.value == "Message embedded successfully!" for s in app.success)


def test_download_and_unrelated_rerun_keep_same_embedded_payload():
    """Pastikan unduhan dan rerun biasa mempertahankan bytes stego yang sama."""
    app = new_app()
    cover = uploaded_cover()
    ready_to_embed(app, cover=cover)
    button(app, "Embed Message").click().run()
    assert not app.exception
    payload = app.session_state["embed_result"]["image_bytes"]
    assert any("Cover · Citra asli" in item.value for item in app.markdown)
    assert any(
        "Hasil penyisipan pesan ditampilkan pada gambar stego di atas."
        in item.value
        for item in app.markdown
    )
    download = next(w for w in app.download_button if w.label == "Download Stego Image (PNG)")
    download.click().run()
    assert not app.exception
    assert app.session_state["embed_result"]["image_bytes"] == payload
    app.text_input(key="lab_key").set_value("another lab key").run()
    assert not app.exception
    assert app.session_state["embed_result"]["image_bytes"] == payload
    with Image.open(io.BytesIO(payload)) as stego:
        assert extract_plaintext(stego.convert("RGB"), b"test-key") == "hello"


def test_cover_upload_shows_preview_in_input():
    """Pastikan unggahan cover memunculkan pratinjau pada bagian input."""
    app = new_app()
    app.file_uploader(key="embed_cover").set_value(uploaded_cover())
    app.run()

    assert not app.exception
    assert any("Cover · Citra asli" in item.value for item in app.markdown)


def test_ui_reports_utf8_capacity_and_accepts_exact_boundary():
    """Pastikan UI memakai ukuran byte UTF-8 dan menerima pesan tepat pada batas kapasitas."""
    app = new_app()
    # 408 bit = 51 byte: header dan tag memakai 50 byte, menyisakan satu byte pesan.
    ready_to_embed(app, uploaded_cover((8, 17)), message="é")
    assert any("Maximum message size: 1 UTF-8 bytes" in e.value for e in app.error)
    assert not any(w.label == "Embed Message" for w in app.button)
    app.text_area(key="embed_message").set_value("X").run()
    assert not app.exception
    button(app, "Embed Message").click().run()
    assert not app.exception
    assert "embed_result" in app.session_state


def test_extract_read_round_trip_and_result_survives_unrelated_rerun():
    """Pastikan pesan pulih melalui UI dan hasilnya tetap tampil setelah rerun biasa."""
    app = new_app()
    message = "Pesan rahasia kelompok 11"
    ready_to_embed(app, message=message)
    button(app, "Embed Message").click().run()
    assert not app.exception
    payload = app.session_state["embed_result"]["image_bytes"]
    next(w for w in app.file_uploader if w.label == "Upload Stego Image").set_value(
        ("stego.png", payload, "image/png")
    )
    next(w for w in app.text_input if w.placeholder == "Enter the shared secret key").set_value("test-key")
    app.run()
    button(app, "Extract & Decrypt").click().run()
    assert not app.exception
    assert any("<strong>Plaintext</strong>" in w.value and message in w.value for w in app.markdown)
    assert any("Stego · Gambar yang diekstrak" in item.value for item in app.markdown)
    app.text_input(key="lab_key").set_value("different lab key").run()
    assert not app.exception
    assert any("<strong>Plaintext</strong>" in w.value and message in w.value for w in app.markdown)


@pytest.mark.parametrize("image_format", ["PNG", "BMP"])
def test_extract_wrong_key_then_correct_key_and_changed_file(image_format):
    """Pastikan kunci salah gagal, kunci benar memulihkan pesan, dan perubahan berkas menghapus hasil."""
    stego = embed_plaintext(Image.new("RGB", (64, 64)), "pesan uji", b"correct-key")
    buffer = io.BytesIO()
    stego.save(buffer, format=image_format)
    app = new_app()
    app.file_uploader(key="extract_image").set_value(
        (f"stego.{image_format.lower()}", buffer.getvalue(), f"image/{image_format.lower()}")
    )
    app.text_input(key="extract_key").set_value("wrong-key")
    app.run()
    button(app, "Extract & Decrypt").click().run()
    assert not app.exception
    assert app.session_state["extract_result"]["plaintext"] is None
    assert app.session_state["extract_result"]["error"]
    assert any("Stego · Gambar yang diekstrak" in item.value for item in app.markdown)
    app.text_input(key="extract_key").set_value("correct-key").run()
    assert "extract_result" not in app.session_state
    button(app, "Extract & Decrypt").click().run()
    assert not app.exception
    assert app.session_state["extract_result"]["plaintext"] == "pesan uji"
    app.file_uploader(key="extract_image").set_value(uploaded_cover()).run()
    assert "extract_result" not in app.session_state
    button(app, "Extract & Decrypt").click().run()
    assert not app.exception
    assert app.session_state["extract_result"]["plaintext"] is None
    assert "Payload StegoChat" in app.session_state["extract_result"]["error"]


def test_extract_rejects_corrupt_file_without_calling_it_wrong_password():
    """Pastikan berkas rusak diberi pesan error gambar, bukan kesimpulan password salah."""
    app = new_app()
    app.file_uploader(key="extract_image").set_value(("broken.png", b"broken", "image/png"))
    app.text_input(key="extract_key").set_value("correct-key")
    app.run()
    button(app, "Extract & Decrypt").click().run()
    assert not app.exception
    assert "File gambar tidak dapat dibaca" in app.session_state["extract_result"]["error"]


def test_runner_keeps_small_metrics_and_success_when_jpeg_raises(monkeypatch):
    """Pastikan UI runner mempertahankan presisi metrik dan status sukses saat JPEG error."""
    cover = Image.new("RGB", (128, 128), (100, 101, 102))
    stego = cover.copy()
    stego.putpixel((0, 0), (101, 101, 102))
    monkeypatch.setattr(laboratory, "embed_plaintext", Mock(return_value=stego))
    monkeypatch.setattr(laboratory, "extract_plaintext", Mock(return_value="X" * 10))
    monkeypatch.setattr(laboratory, "run_jpeg_attack", Mock(side_effect=RuntimeError("codec")))
    app = new_app()
    next(w for w in app.multiselect if w.label == "Gambar uji bawaan").set_value([])
    next(w for w in app.multiselect if w.label == "Ukuran pesan (byte)").set_value([10])
    app.file_uploader(key="lab_uploaded_images").set_value([uploaded_cover((128, 128))])
    app.text_input(key="lab_key").set_value("test-key")
    button(app, "Jalankan eksperimen").click().run()
    assert not app.exception
    row = app.session_state["lab_results"][0]
    expected = 1 / (128 * 128 * 3)
    assert row["mse"] == expected
    assert row["psnr"] == psnr_from_mse(expected)
    assert row["embed_success"] and row["extract_success"]
    assert row["jpeg_attack_result"] == "error"
    table = next(frame.value for frame in app.dataframe if "MSE" in frame.value.columns)
    assert table.iloc[0]["MSE"] == expected
    assert table.iloc[0]["Hasil JPEG"] == "Uji JPEG gagal dijalankan"
    app.selectbox(key="lab_filter_status").set_value("Berhasil").run()
    assert not app.exception
    assert app.session_state["lab_results"][0]["mse"] == expected
