# StegoChat

StegoChat is a university UTS project that encrypts a message with AES-256-GCM and hides the authenticated payload in the least significant bits of an RGB image. A recipient who knows the same independent `stego_key` can deterministically locate, validate, and decrypt the message.

The agreed protocol is documented in [System Design V1](docs/system-design-v1.md). Delivery scope and team planning are in [planning.md](docs/planning.md).

## Current implemented core pipeline

Embedding (plaintext to stego image):

```text
plaintext
  -> PBKDF2-HMAC-SHA256(stego_key, random salt, 100000) -> AES-256 key
  -> AES-256-GCM(random nonce) -> ciphertext + 16-byte auth tag
  -> V1 payload (34-byte header + body)
  -> PRNG: HMAC-SHA256-derived deterministic RGB positions
  -> RGB 1-bit LSB embedding
  -> stego image
```

Extraction (stego image back to plaintext):

```text
stego image
  -> LSB extraction -> raw V1 payload (header + body)
  -> payload parsing (magic, length, salt, nonce, ciphertext, tag)
  -> PBKDF2-HMAC-SHA256(stego_key, salt, 100000) -> AES-256 key
  -> AES-256-GCM authenticate + decrypt
  -> plaintext
```

Layer split: `stego/lsb.py` operates only on raw payload bytes. `stego.lsb.extract_payload()` returns the raw V1 payload (`header + body`) and never decrypts. Plaintext is produced only by `stegochat/core.py`, after the payload is parsed and AES-GCM authentication succeeds.

## Repository structure

```text
crypto/               Key derivation and AES-256-GCM
  kdf.py                PBKDF2-HMAC-SHA256 key derivation, salt generation
  aes.py                AES-256-GCM encrypt/decrypt, nonce generation
stego/                Payload format, PRNG positions, capacity, LSB
  payload.py            V1 payload build/parse (magic, length, salt, nonce)
  prng.py               Deterministic HMAC-SHA256 RGB position selection
  capacity.py           RGB-channel capacity calculations
  lsb.py                One-bit RGB LSB embed/extract at the raw payload level
stegochat/            End-to-end orchestration
  core.py               embed_plaintext / extract_plaintext
analysis/             Image quality metrics and steganalysis tools
  metrics.py            MSE and PSNR calculations
  histogram.py          RGB histogram computation and comparison
  bitplane.py           LSB bit-plane extraction and visualization
  jpeg_fragility.py     JPEG recompression fragility testing
  image_utils.py        Shared image processing utilities
stegochat/            End-to-end orchestration
  core.py               embed_plaintext / extract_plaintext
laboratory.py         Laboratory experiment runner and XLSX export
app.py                Streamlit web application
analysis/             Image quality metrics and steganalysis tools
tests/                Unit and integration tests for all modules
data/                 Sample assets for tests and demonstrations
docs/                 System design and planning documents
results/              Generated local artifacts (ignored by Git)
```

## Environment setup

Create and activate a virtual environment from the repository root.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies from the existing manifest:

```powershell
python -m pip install -r requirements.txt
```

`requirements.txt` is the shared project manifest (streamlit, `cryptography`, Pillow, numpy, matplotlib, pandas, openpyxl, pytest). The implemented core pipeline only needs `cryptography`, Pillow, and pytest.

## Run tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Minimal core pipeline usage

```python
from PIL import Image

from stegochat.core import embed_plaintext, extract_plaintext

cover = Image.open("data/test_images/cover.png").convert("RGB")
stego_key = b"shared-secret-string"

stego = embed_plaintext(cover, "hello from StegoChat", stego_key)
stego.save("results/stego.png")  # lossless format required

recovered = extract_plaintext(
    Image.open("results/stego.png").convert("RGB"),
    stego_key,
)
assert recovered == "hello from StegoChat"
```

Extraction has two validation layers:

1. **Payload format validation** (before cryptographic authentication): If the extracted LSB data does not have valid V1 magic bytes, `extract_plaintext` raises `ValueError: invalid StegoChat V1 magic`. This occurs before AES-GCM authentication and indicates either a wrong `stego_key` (which produces wrong LSB positions), JPEG corruption, or non-StegoChat data.

2. **AES-GCM authentication** (after payload parsing): If the ciphertext or authentication tag is corrupted or the `stego_key` is wrong, `decrypt_gcm()` raises `cryptography.exceptions.InvalidTag`. Plaintext is never returned in either case.

## Implemented features

### Core Cryptography

- AES-256-GCM authenticated encryption (`crypto/aes.py`).
- PBKDF2-HMAC-SHA256 key derivation with a random 16-byte salt at 100,000 iterations (`crypto/kdf.py`).
- V1 payload build and parse with a fixed 34-byte header (`stego/payload.py`).
- Two-stage deterministic HMAC-SHA256 RGB position selection (`stego/prng.py`).
- RGB-channel capacity checks (`stego/capacity.py`).
- One-bit RGB LSB embedding and extraction of raw payload bytes (`stego/lsb.py`).
- End-to-end `embed_plaintext` / `extract_plaintext` orchestration (`stegochat/core.py`).

### Image Quality Metrics

- Mean Squared Error (MSE) calculation (`analysis/metrics.py`).
- Peak Signal-to-Noise Ratio (PSNR) calculation (`analysis/metrics.py`).
- RGB histogram computation and comparison (`analysis/histogram.py`).
- LSB bit-plane extraction and visualization (`analysis/bitplane.py`).

### Security Testing

- JPEG recompression fragility testing (`analysis/jpeg_fragility.py`).
- Automated laboratory experiment runner (`laboratory.py`).
- XLSX export for experiment results (`laboratory.py`).

### User Interface

- Streamlit web application with 3 tabs (`app.py`):
  - **Tab 1 - Embed & Send**: Upload cover image, enter message, embed and download stego image.
  - **Tab 2 - Extract & Read**: Upload stego image, enter key, extract and decrypt message.
  - **Tab 3 - Laboratory & Security Testing**: Histogram analysis, LSB bit-plane visualization, JPEG attack testing, and experiment runner.

### Testing

- Unit and integration tests for the core pipeline (`tests/`).
- Laboratory experiment tests (`tests/test_laboratory.py`).
- 71 total tests passing.

## Test Results

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Current result: **71 tests passing**

## Generated Artifacts

Run the laboratory experiment runner to generate results:

```python
from laboratory import run_default_laboratory

results = run_default_laboratory()
print(f"Generated {len(results)} experiment results")
```

This generates `results/laboratory_results.xlsx` with experiment data for 5 test images × 3 message sizes = 15 cases.

## Planned features (not in the current code)

These are described in the system design but are absent from the current implementation:

- Any additional steganalysis techniques beyond JPEG fragility.
- Advanced image quality metrics beyond MSE/PSNR.
- Perceptual similarity metrics (SSIM, etc.).
