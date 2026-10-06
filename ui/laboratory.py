"""Tab laboratorium Streamlit untuk analisis dan pengujian StegoChat."""

from __future__ import annotations

import io
from dataclasses import asdict
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from PIL import Image

from analysis.bitplane import compare_lsb_bit_planes, plane_to_image
from analysis.chi_square import (
    chi_square_report_to_rows,
    compute_chi_square_test,
    format_p_value_for_display,
)
from analysis.histogram import compare_rgb_histograms
from analysis.jpeg_fragility import run_jpeg_quality_sweep
from laboratory import run_experiment_case

# TAB 3: LABORATORIUM DAN PENGUJIAN KEAMANAN
# ============================================================================


def _render_uploaded_image_preview(uploaded_file: Any, label: str) -> None:
    """Tampilkan pratinjau RGB dari salinan bytes unggahan agar posisi buffer asli tetap."""
    if uploaded_file is None:
        return

    st.markdown(f"**{label}**")
    try:
        with Image.open(io.BytesIO(uploaded_file.getvalue())) as source:
            st.image(source.convert("RGB"), width="stretch")
    except OSError:
        st.caption("Pratinjau tidak tersedia untuk file gambar ini.")


def _render_jpeg_attack_panel() -> None:
    """Jalankan sweep kualitas JPEG lalu tampilkan ringkasan, grafik, dan tabel terfilter.

    Hasil batch disimpan selama sesi agar pergantian filter tidak menjalankan
    kompresi ulang.
    """
    st.subheader("Uji kerapuhan kompresi JPEG")
    st.caption(
        "Bandingkan beberapa kualitas JPEG dan lihat dampaknya pada pemulihan "
        "pesan yang disisipkan dengan LSB."
    )
    cover_upload = st.file_uploader(
        "Gambar cover",
        type=["png", "bmp"],
        key="jpeg_cover",
    )
    preview_column, _ = st.columns(2)
    with preview_column:
        _render_uploaded_image_preview(cover_upload, "Cover · Citra asli")
    message = st.text_area("Pesan uji", height=70, key="jpeg_message")
    stego_key = st.text_input(
        "Stego-key",
        type="password",
        key="jpeg_key",
    )
    qualities = st.multiselect(
        "Kualitas JPEG yang diuji",
        [95, 90, 85, 70, 50],
        default=[90, 70, 50],
        help="Kualitas lebih rendah biasanya mengubah lebih banyak nilai piksel.",
    )

    if st.button(
        "Jalankan uji kualitas",
        type="primary",
        key="run_jpeg_attack_sweep",
    ):
        if not cover_upload or not message or not stego_key or not qualities:
            st.warning(
                "Unggah gambar, isi pesan dan stego-key, lalu pilih minimal "
                "satu kualitas JPEG."
            )
        else:
            try:
                cover_upload.seek(0)
                with Image.open(cover_upload) as source:
                    cover_image = source.convert("RGB")
                with st.spinner("Menjalankan uji kompresi JPEG..."):
                    sweep = run_jpeg_quality_sweep(
                        cover_image,
                        message,
                        stego_key.encode("utf-8"),
                        qualities=tuple(sorted(qualities, reverse=True)),
                    )
                # Bedakan payload rusak dari uji yang gagal membentuk JPEG.
                st.session_state["jpeg_attack_results"] = [
                    {
                        "quality": result.quality,
                        "jpeg_created": result.jpeg_created,
                        "jpeg_size_bytes": result.jpeg_size_bytes,
                        "extraction_succeeded": result.extraction_succeeded,
                        "decryption_succeeded": result.decryption_succeeded,
                        "plaintext_matches": result.plaintext_matches,
                        "outcome": "error"
                        if not result.jpeg_created
                        else "destroyed"
                        if result.attack_destroyed_payload
                        else "survived",
                        "error_stage": result.error_stage,
                        "error_type": result.error_type,
                    }
                    for result in sweep
                ]
                st.session_state["jpeg_attack_updated_at"] = (
                    pd.Timestamp.now().strftime("%d %b %Y, %H:%M")
                )
            except Exception as error:
                st.error(f"Uji JPEG gagal dijalankan: {error}")

    if st.button("Hapus hasil uji JPEG", key="clear_jpeg_attack_results"):
        st.session_state.pop("jpeg_attack_results", None)
        st.session_state.pop("jpeg_attack_updated_at", None)

    # Filter membaca hasil batch yang tersimpan, sehingga kompresi tidak diulang.
    saved_results = st.session_state.get("jpeg_attack_results", [])
    if not saved_results:
        st.info("Jalankan pengujian untuk melihat grafik dan ringkasan hasil.")
        return

    results_df = pd.DataFrame(saved_results).sort_values(
        "quality", ascending=False
    )
    destroyed_count = int((results_df["outcome"] == "destroyed").sum())
    survived_count = int((results_df["outcome"] == "survived").sum())
    error_count = int((results_df["outcome"] == "error").sum())
    st.caption(
        f"Batch terakhir diperbarui "
        f"{st.session_state.get('jpeg_attack_updated_at', '—')} · "
        f"{len(results_df)} kualitas diuji"
    )
    with st.container(horizontal=True):
        st.metric("Kualitas diuji", len(results_df), border=True)
        st.metric("Payload rusak", destroyed_count, border=True)
        st.metric("Pesan berhasil dipulihkan", survived_count, border=True)
    if error_count:
        st.warning(f"{error_count} uji gagal dijalankan; lihat tahap gagal pada tabel.")

    summary_df = pd.DataFrame(
        {
            "Kualitas JPEG": results_df["quality"],
            "Payload rusak": (results_df["outcome"] == "destroyed").astype(int),
            "Payload bertahan": (results_df["outcome"] == "survived").astype(int),
            "Uji gagal": (results_df["outcome"] == "error").astype(int),
        }
    )
    st.bar_chart(
        summary_df,
        x="Kualitas JPEG",
        y=["Payload rusak", "Payload bertahan", "Uji gagal"],
        width="stretch",
    )

    outcome_filter = st.selectbox(
        "Filter hasil",
        ["Semua hasil", "Payload rusak", "Payload bertahan", "Uji gagal"],
        key="jpeg_attack_outcome_filter",
    )
    displayed_df = results_df.copy()
    if outcome_filter == "Payload rusak":
        displayed_df = displayed_df[displayed_df["outcome"] == "destroyed"]
    elif outcome_filter == "Payload bertahan":
        displayed_df = displayed_df[displayed_df["outcome"] == "survived"]
    elif outcome_filter == "Uji gagal":
        displayed_df = displayed_df[displayed_df["outcome"] == "error"]

    outcome_labels = {
        "destroyed": "Payload rusak",
        "survived": "Payload bertahan",
        "error": "Uji gagal",
    }
    displayed_df["outcome"] = displayed_df["outcome"].map(outcome_labels)
    st.dataframe(
        displayed_df.rename(
            columns={
                "quality": "Kualitas JPEG",
                "jpeg_created": "JPEG terbentuk",
                "jpeg_size_bytes": "Ukuran hasil (byte)",
                "extraction_succeeded": "Ekstraksi berhasil",
                "decryption_succeeded": "Dekripsi berhasil",
                "plaintext_matches": "Pesan cocok",
                "outcome": "Hasil serangan",
                "error_stage": "Tahap gagal",
                "error_type": "Jenis error",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.info(
        f"Kompresi JPEG merusak payload pada {destroyed_count} dari "
        f"{destroyed_count + survived_count} uji JPEG yang selesai. Hasil ini memperlihatkan "
        "kerapuhan LSB terhadap format lossy; gunakan PNG atau BMP untuk "
        "menjaga payload tetap utuh."
    )


def _render_laboratory_runner() -> None:
    """Uji kombinasi gambar bawaan atau unggahan dengan ukuran pesan yang dipilih.

    Modul laboratory menjalankan logika kasus; panel ini mengelola progres,
    filter, grafik, detail, serta unduhan CSV dan XLSX dari hasil sesi.
    """
    st.subheader("Experiment Runner")
    st.caption(
        "Jalankan pengujian pada beberapa gambar dan ukuran pesan. Hasil tersimpan "
        "selama sesi ini sehingga filter, grafik, dan detail tetap dapat dijelajahi."
    )

    image_dir = "data/test_images"
    try:
        import os

        image_files = sorted(
            filename
            for filename in os.listdir(image_dir)
            if filename.lower().endswith((".png", ".bmp"))
        )
    except FileNotFoundError:
        st.warning(f"Folder gambar bawaan tidak ditemukan: {image_dir}")
        image_files = []

    if not image_files:
        st.info("Belum ada gambar bawaan. Kamu tetap bisa mengunggah gambar sendiri.")

    uploaded_images = st.file_uploader(
        "Unggah gambar uji sendiri (PNG/BMP)",
        type=["png", "bmp"],
        accept_multiple_files=True,
        key="lab_uploaded_images",
        help="Gambar yang diunggah akan digabung dengan pilihan bawaan saat eksperimen dijalankan.",
    )
    if uploaded_images:
        st.markdown("**Pratinjau gambar uji yang diunggah**")
        for start in range(0, len(uploaded_images), 2):
            preview_columns = st.columns(2)
            for column, uploaded in zip(
                preview_columns, uploaded_images[start : start + 2]
            ):
                with column:
                    _render_uploaded_image_preview(uploaded, uploaded.name)

    # Form menjalankan eksperimen setelah tombol submit, bukan tiap perubahan pilihan.
    with st.form("lab_experiment_form", border=False):
        selected_images = st.multiselect(
            "Gambar uji bawaan",
            image_files,
            default=image_files[: min(5, len(image_files))],
            help="Pilih gambar yang sudah tersedia di folder gambar uji proyek.",
        )
        message_sizes = st.multiselect(
            "Ukuran pesan (byte)",
            [10, 50, 100, 200, 500],
            default=[10, 50, 100],
            help="Pesan uji dibuat dari karakter ASCII agar ukuran byte konsisten.",
        )
        stego_key = st.text_input(
            "Stego-key untuk pengujian",
            type="password",
            key="lab_key",
            help="Kunci hanya dipakai selama proses pengujian dan tidak masuk ke hasil ekspor.",
        )
        run_requested = st.form_submit_button(
            "Jalankan eksperimen",
            type="primary",
            width="stretch",
        )
    clear_requested = st.button("Hapus hasil", key="clear_laboratory_results")

    if clear_requested:
        st.session_state.pop("lab_results", None)
        st.session_state.pop("lab_results_updated_at", None)
        st.info("Hasil eksperimen sesi ini sudah dihapus.")
        return

    if run_requested:
        # Satukan path gambar bawaan dan bytes unggahan dalam daftar kasus yang sama.
        experiment_images: list[tuple[str, str | bytes]] = [
            (image_name, f"{image_dir}/{image_name}")
            for image_name in selected_images
        ]
        experiment_images.extend(
            (
                f"Unggahan {index}: {uploaded.name}",
                uploaded.getvalue(),
            )
            for index, uploaded in enumerate(uploaded_images or [], start=1)
        )

        if not experiment_images or not message_sizes:
            st.warning("Pilih atau unggah minimal satu gambar dan pilih ukuran pesan.")
        elif not stego_key:
            st.warning("Masukkan stego-key untuk menjalankan eksperimen.")
        else:
            results: list[dict[str, Any]] = []
            total_cases = len(experiment_images) * len(message_sizes)
            progress_bar = st.progress(0.0)
            progress_label = st.empty()
            current_case = 0
            stego_key_bytes = stego_key.encode("utf-8")

            for image_name, image_source in experiment_images:
                try:
                    image_input = (
                        io.BytesIO(image_source)
                        if isinstance(image_source, bytes)
                        else image_source
                    )
                    with Image.open(image_input) as source:
                        cover_image = source.convert("RGB")
                    for message_size in message_sizes:
                        current_case += 1
                        progress_label.caption(
                            f"Memproses kasus {current_case} dari {total_cases}: "
                            f"{image_name}, pesan {message_size} byte"
                        )
                        # Huruf X memakai satu byte UTF-8 agar ukuran uji tepat sesuai pilihan.
                        result = run_experiment_case(
                            cover_image,
                            "X" * message_size,
                            stego_key_bytes,
                        )
                        row = asdict(result)
                        row["image_name"] = image_name
                        row["jpeg_attack_result"] = result.jpeg_attack_result or "not_run"
                        results.append(row)
                        progress_bar.progress(current_case / total_cases)
                except Exception as error:
                    st.error(f"Gagal memproses {image_name}: {error}")

            st.session_state["lab_results"] = results
            st.session_state["lab_results_updated_at"] = pd.Timestamp.now().strftime(
                "%d %b %Y, %H:%M"
            )
            progress_label.empty()
            progress_bar.empty()
            successful_cases = sum(
                row["embed_success"] and row["extract_success"] for row in results
            )
            st.success(
                f"Selesai: {len(results)} kasus dianalisis, "
                f"{successful_cases} berhasil dipulihkan."
            )

    results = st.session_state.get("lab_results", [])
    if not results:
        st.info(
            "Hasil akan muncul di sini setelah eksperimen dijalankan. "
            "Pilih gambar, ukuran pesan, dan stego-key di atas."
        )
        return

    results_df = pd.DataFrame(results)
    # Status ekstraksi berhasil hanya jika embedding dan pemulihan sama-sama sukses.
    results_df["overall_success"] = (
        results_df["embed_success"].fillna(False)
        & results_df["extract_success"].fillna(False)
    )
    results_df["psnr"] = pd.to_numeric(results_df["psnr"], errors="coerce")
    results_df["mse"] = pd.to_numeric(results_df["mse"], errors="coerce")
    st.caption(
        f"Hasil terakhir diperbarui {st.session_state.get('lab_results_updated_at', '—')} · "
        f"{len(results_df)} kasus tersimpan"
    )

    filter_cols = st.columns([1.2, 1, 1])
    image_options = ["Semua gambar", *sorted(results_df["image_name"].unique())]
    size_values = sorted(results_df["message_size_bytes"].unique())
    size_options = ["Semua ukuran", *[f"{size} byte" for size in size_values]]
    # Sesuaikan pilihan filter lama jika batch baru memiliki gambar atau ukuran berbeda.
    if st.session_state.get("lab_filter_image") not in image_options:
        st.session_state["lab_filter_image"] = image_options[0]
    if st.session_state.get("lab_filter_size") not in size_options:
        st.session_state["lab_filter_size"] = size_options[0]

    with filter_cols[0]:
        selected_image = st.selectbox(
            "Filter gambar", image_options, key="lab_filter_image"
        )
    with filter_cols[1]:
        selected_size = st.selectbox(
            "Filter pesan", size_options, key="lab_filter_size"
        )
    with filter_cols[2]:
        selected_status = st.selectbox(
            "Status ekstraksi",
            ["Semua status", "Berhasil", "Gagal"],
            key="lab_filter_status",
        )
    trend_metric = st.segmented_control(
        "Metrik grafik",
        ["PSNR", "MSE"],
        default="PSNR",
        key="lab_trend_metric",
    )

    filtered_df = results_df.copy()
    if selected_image != "Semua gambar":
        filtered_df = filtered_df[filtered_df["image_name"] == selected_image]
    if selected_size != "Semua ukuran":
        size_value = int(selected_size.split()[0])
        filtered_df = filtered_df[
            filtered_df["message_size_bytes"] == size_value
        ]
    if selected_status == "Berhasil":
        filtered_df = filtered_df[filtered_df["overall_success"]]
    elif selected_status == "Gagal":
        filtered_df = filtered_df[~filtered_df["overall_success"]]

    if filtered_df.empty:
        st.info("Tidak ada kasus yang cocok dengan filter ini.")
        return

    st.subheader("Ringkasan hasil")
    success_count = int(filtered_df["overall_success"].sum())
    # Ringkasan kualitas hanya menghitung kasus yang benar-benar memiliki nilai PSNR.
    measured_psnr = filtered_df["psnr"].dropna()
    average_psnr = measured_psnr.mean() if not measured_psnr.empty else None
    quality_pass_count = int((measured_psnr >= 30).sum())
    jpeg_tested = filtered_df[
        filtered_df["jpeg_attack_result"].isin(["destroyed", "survived"])
    ]
    jpeg_destroyed_count = int(
        (jpeg_tested["jpeg_attack_result"] == "destroyed").sum()
    )
    average_capacity = filtered_df["capacity_utilization_percent"].mean()

    with st.container(horizontal=True):
        st.metric("Total kasus", len(filtered_df), border=True)
        st.metric(
            "Ekstraksi berhasil",
            f"{success_count}/{len(filtered_df)} "
            f"({success_count / len(filtered_df) * 100:.1f}%)",
            border=True,
        )
        st.metric(
            "Rata-rata PSNR",
            f"{average_psnr:.2f} dB" if average_psnr is not None else "—",
            border=True,
        )
        st.metric(
            "Payload rusak oleh JPEG",
            f"{jpeg_destroyed_count}/{len(jpeg_tested)}"
            if len(jpeg_tested)
            else "Belum diuji",
            border=True,
        )
    st.caption(
        f"PSNR memenuhi ambang 30 dB pada {quality_pass_count}/"
        f"{len(measured_psnr)} kasus terukur · "
        f"Rata-rata penggunaan kapasitas {average_capacity:.2f}%"
    )
    if measured_psnr.empty:
        st.warning("Belum ada PSNR yang dapat dihitung dari kasus terfilter.")
    elif quality_pass_count < len(measured_psnr):
        st.warning(
            "Sebagian hasil berada di bawah ambang PSNR 30 dB. "
            "Coba ukuran pesan yang lebih kecil atau gambar dengan kapasitas lebih besar."
        )
    else:
        st.success("Semua kasus terukur memenuhi ambang PSNR 30 dB.")

    st.subheader("Grafik interaktif")
    chart_cols = st.columns(2)
    metric_key = "psnr" if trend_metric == "PSNR" else "mse"
    metric_unit = "dB" if trend_metric == "PSNR" else "piksel kuadrat"
    trend_df = filtered_df.dropna(subset=[metric_key]).sort_values(
        ["image_name", "message_size_bytes"]
    )
    with chart_cols[0]:
        st.markdown(f"**{trend_metric} menurut ukuran pesan**")
        if trend_df.empty:
            st.info(f"Belum ada nilai {trend_metric} untuk filter ini.")
        else:
            st.line_chart(
                trend_df,
                x="message_size_bytes",
                y=metric_key,
                x_label="Ukuran pesan (byte)",
                y_label=f"{trend_metric} ({metric_unit})",
                color="image_name",
                width="stretch",
                height=300,
            )

    with chart_cols[1]:
        st.markdown("**Dampak kompresi JPEG**")
        jpeg_labels = {
            "destroyed": "Payload rusak",
            "survived": "Payload bertahan",
            "not_run": "Tidak diuji",
            "error": "Uji JPEG gagal dijalankan",
        }
        jpeg_counts = (
            filtered_df["jpeg_attack_result"]
            .map(jpeg_labels)
            .value_counts()
            .rename_axis("Hasil JPEG")
            .reset_index(name="Jumlah kasus")
        )
        if jpeg_counts.empty:
            st.info("Belum ada hasil uji JPEG untuk filter ini.")
        else:
            st.bar_chart(
                jpeg_counts,
                x="Hasil JPEG",
                y="Jumlah kasus",
                width="stretch",
                height=300,
            )

    if len(jpeg_tested):
        st.info(
            f"Kompresi JPEG merusak payload pada {jpeg_destroyed_count} dari "
            f"{len(jpeg_tested)} pengujian. Ini menunjukkan kerapuhan LSB terhadap "
            "penyimpanan lossy; gunakan PNG atau BMP untuk membawa pesan."
        )

    st.subheader("Data eksperimen")
    display_columns = [
        "image_name",
        "width",
        "height",
        "message_size_bytes",
        "payload_size_bytes",
        "capacity_utilization_percent",
        "mse",
        "psnr",
        "embed_success",
        "extract_success",
        "jpeg_attack_result",
        "error",
    ]
    column_labels = {
        "image_name": "Gambar",
        "width": "Lebar",
        "height": "Tinggi",
        "message_size_bytes": "Pesan (byte)",
        "payload_size_bytes": "Payload (byte)",
        "capacity_utilization_percent": "Kapasitas terpakai (%)",
        "mse": "MSE",
        "psnr": "PSNR (dB)",
        "embed_success": "Penyisipan berhasil",
        "extract_success": "Ekstraksi berhasil",
        "jpeg_attack_result": "Hasil JPEG",
        "error": "Catatan",
    }
    # Ubah label untuk tampilan; nilai numerik asli tetap dipakai saat analisis dan ekspor.
    visible_df = filtered_df[display_columns].rename(columns=column_labels)
    visible_df["Hasil JPEG"] = visible_df["Hasil JPEG"].map(
        {
            "destroyed": "Payload rusak",
            "survived": "Payload bertahan",
            "not_run": "Tidak diuji",
            "error": "Uji JPEG gagal dijalankan",
        }
    )
    visible_df["Penyisipan berhasil"] = visible_df["Penyisipan berhasil"].map(
        {True: "Ya", False: "Tidak"}
    )
    visible_df["Ekstraksi berhasil"] = visible_df["Ekstraksi berhasil"].map(
        {True: "Ya", False: "Tidak"}
    )
    st.dataframe(
        visible_df,
        width="stretch",
        hide_index=True,
        column_config={
            "MSE": st.column_config.NumberColumn(format="%.6g"),
            "PSNR (dB)": st.column_config.NumberColumn(format="%.2f"),
            "Kapasitas terpakai (%)": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    st.subheader("Detail kasus")
    detail_rows = filtered_df.reset_index(drop=True)
    detail_labels = [
        f"{row['image_name']} · pesan {row['message_size_bytes']} byte · "
        f"{'berhasil' if row['overall_success'] else 'gagal'}"
        for _, row in detail_rows.iterrows()
    ]
    if st.session_state.get("lab_detail_case") not in detail_labels:
        st.session_state["lab_detail_case"] = detail_labels[0]
    selected_detail_label = st.selectbox(
        "Pilih kasus untuk melihat hasilnya",
        detail_labels,
        key="lab_detail_case",
    )
    detail_index = detail_labels.index(selected_detail_label)
    detail = detail_rows.iloc[detail_index]
    detail_cols = st.columns(3)
    detail_cols[0].metric(
        "Resolusi gambar", f"{detail['width']} × {detail['height']} px"
    )
    detail_cols[1].metric(
        "PSNR", f"{detail['psnr']:.2f} dB" if pd.notna(detail["psnr"]) else "—"
    )
    detail_cols[2].metric(
        "Kapasitas terpakai", f"{detail['capacity_utilization_percent']:.2f}%"
    )
    if detail["overall_success"]:
        st.success("Penyisipan, ekstraksi, dan pemulihan pesan berhasil.")
    else:
        st.error("Kasus ini gagal. Periksa kapasitas gambar atau catatan error di bawah.")
    if detail["error"]:
        st.code(str(detail["error"]), language=None)

    export_df = visible_df
    download_cols = st.columns(2)
    with download_cols[0]:
        st.download_button(
            "Unduh hasil terfilter (CSV)",
            data=export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="stegochat_laboratory_filtered.csv",
            mime="text/csv",
            width="stretch",
        )
    with download_cols[1]:
        workbook = io.BytesIO()
        # Excel memuat seluruh hasil dan filter aktif; CSV hanya memuat hasil terfilter.
        with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
            results_df.drop(columns=["overall_success"]).to_excel(
                writer, index=False, sheet_name="Hasil eksperimen"
            )
            visible_df.to_excel(writer, index=False, sheet_name="Filter aktif")
        st.download_button(
            "Unduh seluruh hasil (XLSX)",
            data=workbook.getvalue(),
            file_name="laboratory_results.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            width="stretch",
        )


def tab_laboratory() -> None:
    """Tampilkan lima tab analisis: histogram, bidang LSB, JPEG, runner, dan Chi-Square.

    Histogram dan bidang LSB membandingkan cover-stego; Chi-Square hanya
    memerlukan satu citra dan memberi indikasi statistik per kanal.
    """
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

        preview_columns = st.columns(2)
        with preview_columns[0]:
            _render_uploaded_image_preview(cover_upload, "Cover · Citra asli")
        with preview_columns[1]:
            _render_uploaded_image_preview(stego_upload, "Stego · Hasil penyisipan")

        if cover_upload and stego_upload:
            try:
                cover_image = Image.open(cover_upload).convert("RGB")
                stego_image = Image.open(stego_upload).convert("RGB")

                comparison = compare_rgb_histograms(
                    cover_image,
                    stego_image,
                )

                # Grid dua baris menempatkan histogram cover di atas dan stego di bawah.
                fig, axes = plt.subplots(
                    2,
                    3,
                    figsize=(15, 8),
                    constrained_layout=True,
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
                        f"Cover {channel} Channel",
                        fontsize=11,
                    )
                    axes[0, i].set_xlabel("Intensity", fontsize=9)
                    axes[0, i].set_ylabel("Count", fontsize=9)
                    axes[0, i].tick_params(axis="both", labelsize=8)

                    axes[1, i].bar(
                        range(256),
                        comparison.stego.for_channel(channel),
                        color=color,
                        alpha=0.7,
                        label="Stego",
                    )

                    axes[1, i].set_title(
                        f"Stego {channel} Channel",
                        fontsize=11,
                    )
                    axes[1, i].set_xlabel("Intensity", fontsize=9)
                    axes[1, i].set_ylabel("Count", fontsize=9)
                    axes[1, i].tick_params(axis="both", labelsize=8)

                with st.container(key="lab-histogram-responsive"):
                    st.pyplot(fig, width="stretch")
                    # Tutup figure setelah tampil agar rerun tidak menumpuk objek Matplotlib.
                    plt.close(fig)
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

        preview_columns = st.columns(2)
        with preview_columns[0]:
            _render_uploaded_image_preview(cover_upload, "Cover · Citra asli")
        with preview_columns[1]:
            _render_uploaded_image_preview(stego_upload, "Stego · Hasil penyisipan")

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

                with st.container(key="lab-lsb-responsive"):
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
                                width="stretch",
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
                                width="stretch",
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
                        width="stretch",
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
        _render_jpeg_attack_panel()

    with tab4:
        _render_laboratory_runner()

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
        preview_column, _ = st.columns(2)
        with preview_column:
            _render_uploaded_image_preview(
                test_upload, "Citra · Gambar yang dianalisis"
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
                # Format p-value hanya untuk tabel; hasil perhitungan aslinya tetap numerik.
                display_rows = [
                    {
                        **row,
                        "p_value": format_p_value_for_display(row["p_value"]),
                    }
                    for row in rows
                ]

                st.subheader(
                    "Hasil per Channel"
                )

                st.dataframe(
                    pd.DataFrame(display_rows),
                    width="stretch",
                )

                suspected = (
                    report.suspected_channel_count()
                )

                # Dua kanal mencurigakan memicu indikasi; hasil rendah bukan bukti bebas pesan.
                if suspected >= 2:
                    st.warning(
                        f"⚠️ {suspected} dari 3 channel menunjukkan "
                        f"p-value tinggi — citra ini KEMUNGKINAN BESAR "
                        "mengandung pesan tersembunyi."
                    )
                else:
                    st.markdown(
                        '<div class="chi-square-success" role="status">'
                        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                        '<circle cx="12" cy="12" r="9"/>'
                        '<path d="m8 12.2 2.6 2.6 5.4-5.4"/>'
                        '</svg>'
                        '<span>Pesan tidak terdeteksi oleh uji Chi-Square pada '
                        'tingkat pengisian dan karakteristik citra ini.</span>'
                        '</div>',
                        unsafe_allow_html=True,
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
