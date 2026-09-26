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
analysis/             Reserved for quality metrics (currently empty)
tests/                Unit and integration tests for the V1 core pipeline
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

An incorrect `stego_key` or a modified protected payload makes `extract_plaintext` raise `cryptography.exceptions.InvalidTag`; plaintext is never returned in that case.

## Implemented features

- AES-256-GCM authenticated encryption (`crypto/aes.py`).
- PBKDF2-HMAC-SHA256 key derivation with a random 16-byte salt at 100,000 iterations (`crypto/kdf.py`).
- V1 payload build and parse with a fixed 34-byte header (`stego/payload.py`).
- Two-stage deterministic HMAC-SHA256 RGB position selection (`stego/prng.py`).
- RGB-channel capacity checks (`stego/capacity.py`).
- One-bit RGB LSB embedding and extraction of raw payload bytes (`stego/lsb.py`).
- End-to-end `embed_plaintext` / `extract_plaintext` orchestration (`stegochat/core.py`).
- Unit and integration tests for the core pipeline (`tests/`).

## Planned features (not in the current code)

These are described in the system design but are absent from the current implementation:

- Streamlit interface / laboratory UI.
- MSE and PSNR image-quality metrics (`analysis/` is empty).
- Histogram analysis.
- JPEG / lossy-transport robustness testing.
- Any report, notebook, or generated quality artifact.
