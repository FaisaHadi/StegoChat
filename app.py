"""Antarmuka Streamlit untuk menyembunyikan, membaca, dan menguji pesan dalam gambar.

Proses kriptografi dan LSB dijalankan oleh modul inti; antarmuka mengelola
input, pratinjau, hasil sesi, visualisasi, dan unduhan.
"""

from __future__ import annotations

import streamlit as st

from ui.laboratory import tab_laboratory
from ui.messaging import tab_embed_send, tab_extract_read

# Konfigurasi halaman dan CSS berlaku bersama pada welcome serta semua tab aplikasi.
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

    /* Keep analysis visuals readable on wide screens and fluid on narrow ones. */
    div.st-key-main_navigation,
    div.st-key-tab-embed-responsive,
    div.st-key-tab-extract-responsive,
    div.st-key-tab-laboratory-responsive,
    div.st-key-lab-histogram-responsive,
    div.st-key-lab-lsb-responsive {
        width: 100%;
        max-width: 1100px;
        margin-left: auto;
        margin-right: auto;
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

    /* Ratakan navigasi utama ke kiri agar sejajar dengan judul dan subtab.
       Pilihan pertama tetap terjangkau saat tab melampaui lebar layar. */
    .st-key-main_navigation > div > [role="tablist"],
    .st-key-main_navigation > [data-baseweb="tab-list"] {
        justify-content: flex-start;
        gap: 0.5rem;
    }

    .st-key-main_navigation > div > [role="tablist"] > [role="tab"],
    .st-key-main_navigation > [data-baseweb="tab-list"] > [data-baseweb="tab"] {
        min-height: 3rem;
        padding: 0.625rem 1rem;
        flex-shrink: 0;
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

    /* Streamlit already provides its own show/hide-password button. Hide the
       browser's password-reveal affordance, which appears after the first
       character in Edge/Windows and otherwise creates a second eye icon. */
    .stTextInput input[type="password"]::-ms-reveal,
    .stTextInput input[type="password"]::-ms-clear {
        display: none !important;
    }

    .stTextInput input[type="password"]::-webkit-credentials-auto-fill-button {
        visibility: hidden !important;
        pointer-events: none !important;
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

    .embed-output-summary {
        display: grid;
        gap: 0.55rem;
        margin: 0.35rem 0 0.55rem;
    }

    .embed-success-banner {
        padding: 0.65rem 0.9rem;
        color: #4ADE80;
        background: rgba(20, 83, 45, 0.65);
        border: 1px solid rgba(34, 197, 94, 0.2);
        border-radius: 10px;
        line-height: 1.4;
    }

    .embed-metrics {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.6rem;
    }

    .embed-metric-card {
        min-width: 0;
        padding: 0.45rem 0.8rem;
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 10px;
    }

    .embed-metric-label {
        color: #CBD5E1;
        font-size: 0.85rem;
        margin-bottom: 0.2rem;
    }

    .embed-metric-value {
        color: #E2E8F0;
        font-size: clamp(1.15rem, 1.7vw, 1.55rem);
        line-height: 1.2;
        overflow-wrap: anywhere;
    }

    .embed-image-label {
        margin-top: 0.65rem;
        margin-bottom: 0.55rem;
        color: #E2E8F0;
        font-weight: 600;
        line-height: 1.4;
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
        margin-top: 0 !important;                     /* offset diatur oleh block container */
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

    .welcome-features > .welcome-feature {
        display: inline-flex;
        align-items: center;
        gap: 0.42rem;
        padding: 0.4rem 0.75rem;
        border: 1px solid #1E293B;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.55);
    }

    .welcome-feature svg {
        width: 14px;
        height: 14px;
        flex: 0 0 14px;
        stroke: #38BDF8;
        stroke-width: 1.8;
        stroke-linecap: round;
        stroke-linejoin: round;
        fill: none;
    }

    .chi-square-success {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        padding: 1rem;
        border: 1px solid rgba(34, 197, 94, 0.28);
        border-radius: 10px;
        background: rgba(20, 83, 45, 0.55);
        color: #4ADE80;
        line-height: 1.5;
    }

    .chi-square-success svg {
        width: 18px;
        height: 18px;
        flex: 0 0 18px;
        fill: none;
        stroke: currentColor;
        stroke-width: 1.8;
        stroke-linecap: round;
        stroke-linejoin: round;
    }

    .app-footer {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(21rem, auto);
        grid-template-areas: "brand team" "note team";
        align-items: center;
        column-gap: 2rem;
        row-gap: 0.35rem;
        width: 100%;
        margin-top: 2.5rem;
        padding: 1.1rem 0 0.25rem;
        border-top: 1px solid rgba(51, 65, 85, 0.72);
        color: #94A3B8;
        font-size: 0.72rem;
        line-height: 1.5;
    }

    .app-footer-brand {
        grid-area: brand;
        display: inline-flex;
        align-items: center;
        gap: 0.55rem;
        color: #CBD5E1;
        font-weight: 600;
        letter-spacing: 0.08em;
        white-space: nowrap;
    }

    .app-footer-brand svg {
        width: 17px;
        height: 17px;
        flex: 0 0 17px;
        fill: none;
        stroke: #38BDF8;
        stroke-width: 1.7;
        stroke-linecap: round;
        stroke-linejoin: round;
    }

    .app-footer-note {
        grid-area: note;
        margin: 0;
        text-align: left;
    }

    .app-footer-team {
        grid-area: team;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: baseline;
        column-gap: 1.25rem;
        row-gap: 0.2rem;
        min-width: 21rem;
        font-size: 0.74rem;
        line-height: 1.55;
    }

    .app-footer-team-title {
        grid-column: 1 / -1;
        margin: 0 0 0.1rem;
        color: #CBD5E1;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .app-footer-member-name {
        color: #CBD5E1;
    }

    .app-footer-member-id {
        color: #94A3B8;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
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
        position: relative !important;
        z-index: 10 !important;
        pointer-events: auto !important;
        cursor: pointer !important;
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

    /* Keep controls below Streamlit's transparent Deploy toolbar. Without this
       offset the toolbar sits above the back button and consumes mouse input. */
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        padding-top: 4rem !important;
        padding-bottom: 0.5rem !important;
    }

    /* ============ RESPONSIVE ============ */

    @media (max-width: 900px) {
        .main .block-container,
        [data-testid="stMainBlockContainer"],
        [data-testid="BlockContainer"] {
            padding: 3.75rem 1.25rem 1rem 1.25rem !important;
        }

        div.st-key-welcome_screen {
            min-height: calc(100vh - 5rem) !important;
            padding-top: 0.5rem !important;
        }

        .app-footer {
            grid-template-columns: minmax(0, 1fr);
            grid-template-areas: "brand" "team" "note";
            align-items: start;
            row-gap: 0.75rem;
            margin-top: 2rem;
        }

        .app-footer-team {
            width: min(100%, 28rem);
            min-width: 0;
            column-gap: 0.75rem;
        }

        .app-footer-note {
            text-align: left;
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

    /* Bungkus deskripsi pada layar ponsel tanpa mengubah tampilan desktop. */
    @media (max-width: 640px) {
        .main-header-center .hero-description {
            white-space: normal;
            overflow-wrap: anywhere;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# ALUR UTAMA APLIKASI
# ============================================================================


def render_footer() -> None:
    """Tampilkan identitas aplikasi dan anggota kelompok secara konsisten di tiap halaman."""
    st.markdown(
        '<footer class="app-footer" role="contentinfo">'
        '<div class="app-footer-brand">'
        '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
        '<rect x="4" y="10" width="16" height="10" rx="2"/>'
        '<path d="M8 10V7a4 4 0 0 1 8 0v3"/>'
        '<path d="M12 14v2"/>'
        '</svg>'
        '<span>STEGOCHAT</span>'
        '</div>'
        '<div class="app-footer-team" aria-label="Identitas kelompok">'
        '<p class="app-footer-team-title">Kelompok 11</p>'
        '<span class="app-footer-member-name">Faisal Hadi Saik</span>'
        '<span class="app-footer-member-id">247006111052</span>'
        '<span class="app-footer-member-name">Fadhila Hendani</span>'
        '<span class="app-footer-member-id">247006111053</span>'
        '<span class="app-footer-member-name">Irsyad Khoerul Umam</span>'
        '<span class="app-footer-member-id">247006111055</span>'
        '</div>'
        '<p class="app-footer-note">An educational project in cryptography and steganography.</p>'
        '</footer>',
        unsafe_allow_html=True,
    )


def show_welcome() -> None:
    """Tampilkan halaman pembuka dan tombol mulai yang mengaktifkan halaman utama melalui rerun."""
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
                width="stretch",
                key="start_stegochat",
            ):
                # Penanda halaman dipertahankan selama sesi; rerun menampilkan tab utama.
                st.session_state["started"] = True
                st.rerun()

        st.markdown(
            '<div class="welcome-features">'
            '<span class="welcome-feature">'
            '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<rect x="4" y="10" width="16" height="10" rx="2"/>'
            '<path d="M8 10V7a4 4 0 0 1 8 0v3"/>'
            '<path d="M12 14v2"/>'
            '</svg><span>AES-256-GCM</span></span>'
            '<span class="welcome-feature">'
            '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<rect x="3" y="5" width="18" height="14" rx="2"/>'
            '<circle cx="8" cy="10" r="1.5"/>'
            '<path d="m4 17 5-5 4 4 3-3 4 4"/>'
            '</svg><span>LSB STEGANOGRAPHY</span></span>'
            '<span class="welcome-feature">'
            '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
            '<path d="M12 3 19 6v5c0 4.4-3 7.4-7 9.5C8 18.4 5 15.4 5 11V6l7-3Z"/>'
            '<path d="m9 12 2 2 4-4"/>'
            '</svg><span>AUTHENTICATED PAYLOAD</span></span>'
            '</div>',
            unsafe_allow_html=True,
        )
        render_footer()


def return_to_welcome() -> None:
    """Ubah penanda started sebelum rerun agar aplikasi kembali ke halaman pembuka."""
    st.session_state["started"] = False


def main() -> None:
    """Pilih halaman pembuka atau aplikasi berdasarkan session_state, lalu susun tab dan footer."""

    if "started" not in st.session_state:
        st.session_state["started"] = False

    if not st.session_state["started"]:
        show_welcome()
        return

    # Susun tombol kembali dan badge AES pada baris header yang sama.
    header_left, header_center, header_right = st.columns(
        [0.35, 2, 0.35],
        gap="small",
    )

    with header_left:
        st.button(
            "←",
            key="back_to_welcome",
            help="Kembali ke halaman awal",
            on_click=return_to_welcome,
        )

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
        ],
        key="main_navigation",
    )

    with tab1:
        with st.container(key="tab-embed-responsive"):
            tab_embed_send()

    with tab2:
        with st.container(key="tab-extract-responsive"):
            tab_extract_read()

    with tab3:
        with st.container(key="tab-laboratory-responsive"):
            tab_laboratory()

    render_footer()


if __name__ == "__main__":
    main()
