# StegoChat System Design V1

## Purpose and settled V1 decision

StegoChat hides an encrypted payload in the least significant bits of an RGB image. V1 uses an independent user-provided secret string called `stego_key` for deterministic position selection. It is never stored inside the payload.

The random payload salt is not used to derive `stego_key`. Instead, it is public payload metadata used only with `stego_key` to derive the AES-256-GCM encryption key. This avoids a circular extraction dependency: header positions can be derived before the salt is known.

## Overall architecture

```text
Sender: message + stego_key + RGB cover image
  -> PBKDF2-HMAC-SHA256(stego_key, random salt, 100000) -> AES-256 key
  -> AES-256-GCM(random nonce) -> ciphertext + authentication tag
  -> V1 payload: fixed header + ciphertext + tag
  -> deterministic header/body positions from stego_key
  -> one-bit RGB LSB embedding -> RGB stego image

Recipient: RGB stego image + stego_key
  -> header positions from stego_key -> fixed 34-byte header
  -> validate and parse magic, length, salt, nonce
  -> body positions from stego_key + salt -> ciphertext + tag
  -> PBKDF2-HMAC-SHA256(stego_key, salt, 100000) -> AES-256 key
  -> AES-256-GCM authentication and decryption -> message or failure
```

A future Streamlit interface would only be a presentation boundary. It delegates protocol work to the project modules and must not define crypto, payload, or position-selection behavior.

## LSB layer versus crypto layer

V1 keeps embedding/position selection strictly separate from cryptography. Neither layer may perform the other's job:

| Layer         | Modules                                                                  | Owns                                                                                                                    | Must never                                               |
| ------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| LSB layer     | `stego/lsb.py`, `stego/prng.py`, `stego/capacity.py`, `stego/payload.py` | Deterministic RGB position selection, capacity checks, one-bit LSB embed/extract, and byte-level V1 payload build/parse | Derive keys, decrypt, authenticate, or produce plaintext |
| Crypto layer  | `crypto/kdf.py`, `crypto/aes.py`                                         | PBKDF2-HMAC-SHA256 key derivation and AES-256-GCM encrypt/decrypt                                                       | Read or write image pixels, or select positions          |
| Orchestration | `stegochat/core.py`                                                      | Composing the two layers end to end                                                                                     | Reimplement either layer                                 |

The key consequence, stated explicitly:

- `stego.lsb.extract_payload()` returns the **raw V1 payload** (`header + body`) exactly as embedded. It is an LSB-only operation. It does not parse the payload, derive keys, authenticate, or decrypt, and it never returns plaintext.
- Plaintext is produced **only** by `stegochat.core.extract_plaintext()`, which consumes that raw payload, parses it, derives the AES key, and decrypts with AES-GCM after authentication succeeds.

## Crypto flow

1. The user supplies independent `stego_key` secret bytes. Its byte representation must remain stable between embed and extract operations.
2. Generate a fresh random 16-byte salt.
3. Derive a 32-byte AES key with `PBKDF2-HMAC-SHA256(stego_key, salt, 100000 iterations)`.
4. Generate a fresh random 12-byte nonce.
5. Encrypt the message with AES-256-GCM, producing ciphertext and a 16-byte authentication tag.
6. Construct the V1 payload and embed its bits in the RGB cover image.

During extraction, derive the AES key only after recovering the salt from the header. AES-GCM must authenticate before plaintext is accepted. An incorrect `stego_key`, altered ciphertext/tag, or corrupted protected data must result in extraction/decryption failure without returning plaintext.

The salt and nonce are public metadata carried in the payload. They do not replace the need to protect `stego_key`. A nonce must be fresh for every encryption made with the same derived AES key.

## Payload format

The payload is byte-aligned and ordered exactly as follows:

```text
Magic 2B | Length 4B | Salt 16B | Nonce 12B | Ciphertext N | Auth Tag 16B
```

| Field      |     Size | Meaning                                                         |
| ---------- | -------: | --------------------------------------------------------------- |
| Magic      |  2 bytes | V1 identifier used to reject images without a StegoChat payload |
| Length     |  4 bytes | Byte length of `Ciphertext + Auth Tag` only                     |
| Salt       | 16 bytes | Random PBKDF2 salt; public metadata                             |
| Nonce      | 12 bytes | Fresh AES-GCM nonce; public metadata                            |
| Ciphertext |  N bytes | AES-GCM encrypted message bytes                                 |
| Auth Tag   | 16 bytes | AES-GCM authentication tag                                      |

The fixed header is `2 + 4 + 16 + 12 = 34` bytes, or 272 bits. The body is exactly `Length` bytes and contains the ciphertext followed by its 16-byte authentication tag. A valid `Length` is therefore at least 16 bytes. It does not include Magic, Length, Salt, or Nonce.

### V1 payload field constants

| Constant           | Value                   | Notes                                    |
| ------------------ | ----------------------- | ---------------------------------------- |
| Magic              | `b"SG"`                 | Literal V1 identifier bytes              |
| Magic length       | 2 bytes                 | Fixed                                    |
| Length             | 4-byte unsigned integer | Body byte count                          |
| Length encoding    | Big-endian              | Serialized with `int.to_bytes(4, "big")` |
| Length meaning     | `len(ciphertext) + 16`  | Ciphertext plus the auth tag only        |
| Salt               | 16 bytes                | Random PBKDF2 salt                       |
| Nonce              | 12 bytes                | Fresh AES-GCM nonce                      |
| Auth tag           | 16 bytes                | Final 16 bytes of the body               |
| Total fixed header | 34 bytes                | `2 + 4 + 16 + 12` = 272 bits             |

These constants are defined by `stego/payload.py` (`MAGIC`, `MAGIC_LENGTH`, `LENGTH_FIELD_LENGTH`, `SALT_LENGTH`, `NONCE_LENGTH`, `AUTH_TAG_LENGTH`, `HEADER_SIZE`) and must not vary between embed and extract.

## RGB one-bit LSB embedding and capacity

Only RGB images are supported. Each R, G, and B channel byte is one embeddable location. One payload bit replaces the least significant bit of one selected channel; all higher bits remain unchanged.

For width `W` and height `H`:

```text
Available channel positions (bits) = W * H * 3
Header bits                        = 34 * 8 = 272
Body bits                          = Length * 8
Required bits                      = 272 + (Length * 8)
```

Embedding is permitted only when:

```text
272 + (Length * 8) <= W * H * 3
```

The maximum body length is:

```text
floor((W * H * 3 - 272) / 8) bytes
```

Capacity is checked before any output image is produced. An image too small to hold the 34-byte header has no valid V1 payload capacity.

## Two-stage deterministic PRNG

V1 uses two HMAC-SHA256-derived seeds for deterministic position selection:

```text
Header seed = HMAC-SHA256(stego_key, b"STEGOCHAT-HEADER")
Body seed   = HMAC-SHA256(stego_key, b"STEGOCHAT-BODY" + salt)
```

The header seed depends on `stego_key` alone. The recipient can therefore reproduce header positions and extract the fixed header before knowing the payload salt. Once the salt is parsed, the body seed deterministically locates the encrypted body.

Position-selection invariants:

- Header selection returns exactly 272 unique RGB-channel positions.
- Header positions are reserved for the header.
- Body selection returns exactly `Length * 8` unique positions and excludes every header position.
- Embed and extract use the same RGB-channel indexing and deterministic sampling procedure.
- `stego_key` is not embedded, stored, logged, or returned in error messages.

Python's built-in `hash()` must not be used to seed this process. Python randomizes `hash()` values between interpreter processes, so it cannot reliably reproduce positions across runs. HMAC-SHA256 is keyed and deterministic for the same `stego_key` and input bytes, which makes it suitable for the required seed derivation.

## Embed flow

1. Validate the cover image as RGB and calculate its available RGB-channel positions.
2. Obtain `stego_key`; do not persist it.
3. Generate salt and nonce, derive the AES key with PBKDF2-HMAC-SHA256 at 100,000 iterations, then encrypt with AES-256-GCM.
4. Build the 34-byte header from Magic, Length, Salt, and Nonce. Build the body from ciphertext plus authentication tag.
5. Validate `272 + (Length * 8)` against image capacity. Stop before modification if it will not fit.
6. Derive the header seed from `stego_key` and choose 272 unique header positions.
7. Derive the body seed from `stego_key` and salt. Choose required unique body positions while excluding all header positions.
8. Embed one header bit at each header position and one body bit at each body position, then save through a lossless RGB-preserving path.
9. Calculate MSE and PSNR between cover and stego images.

## Extract flow

1. Validate the input image as RGB and confirm it has at least 272 RGB-channel positions.
2. Obtain `stego_key`; do not persist it.
3. Derive header positions from `stego_key`, extract the fixed 34-byte header, then validate Magic and parse Length, Salt, and Nonce.
4. Reject a malformed header, including a `Length` below 16 bytes or one that does not fit image capacity.
5. Derive the body seed from `stego_key` and parsed salt. Reproduce body positions while excluding header positions, then extract `Length` bytes.
6. Split the body into ciphertext and final 16-byte authentication tag.
7. Derive the AES key using `PBKDF2-HMAC-SHA256(stego_key, salt, 100000 iterations)` and decrypt with the extracted nonce and tag.
8. Return plaintext only after AES-GCM authentication succeeds. Treat wrong `stego_key` and protected-payload modification as extraction/decryption failure.

Steps 1–6 belong to the LSB and payload layers and operate only on raw payload bytes. Steps 7–8 belong to the crypto layer. The end-to-end plaintext result is assembled only by `stegochat.core.extract_plaintext()`; `stego.lsb.extract_payload()` stops after step 6 and returns `header + body`.

## MSE and PSNR

For same-size 8-bit RGB cover image `I` and stego image `K`, with width `W`, height `H`, and `C = 3` channels:

```text
MSE = (1 / (W * H * C)) * sum((I[x,y,c] - K[x,y,c])^2)
```

```text
PSNR = 10 * log10((255^2) / MSE) dB
```

If MSE is zero, PSNR is infinite. These metrics quantify pixel differences; they do not prove that LSB embedding is undetectable or resistant to steganalysis.

## Error cases

| Condition                                      | Required result                                                            |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| Unsupported or non-RGB image                   | Reject before embedding or extraction                                      |
| Image cannot hold the header                   | Reject as insufficient capacity or invalid carrier                         |
| Payload exceeds capacity                       | Reject before producing an output image                                    |
| Duplicate/overlapping header or body positions | Treat as an invariant failure; do not write or return data                 |
| Invalid Magic                                  | Reject as no valid StegoChat V1 payload or wrong `stego_key`               |
| `Length < 16` or body does not fit             | Reject as malformed payload                                                |
| Truncated or corrupted embedded bits           | Reject without partial plaintext                                           |
| AES-GCM authentication failure                 | Reject decryption; do not distinguish wrong key from tampering to the user |
| Lossy output would alter pixels                | Reject or require a lossless RGB-preserving format                         |

## Function contracts

The `crypto/`, `stego/`, and `stegochat/` core pipeline implements these contracts. The `analysis/` metrics (MSE/PSNR) and the Streamlit interface are still documentation-only and are not implemented.

### LSB and payload layer

| Function                                                                         | Contract                                                                                                                                                                                                                        |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `derive_aes_key(stego_key_bytes, salt) -> aes_key_bytes`                         | Requires a 16-byte salt, applies PBKDF2-HMAC-SHA256 for 100,000 iterations, and returns exactly 32 bytes.                                                                                                                       |
| `encrypt_gcm(plaintext_bytes, aes_key_bytes, nonce) -> (ciphertext, auth_tag)`   | Requires a 32-byte key and 12-byte nonce; returns ciphertext and a 16-byte tag.                                                                                                                                                 |
| `decrypt_gcm(ciphertext, auth_tag, aes_key_bytes, nonce) -> plaintext_bytes`     | Requires a 32-byte key, 12-byte nonce, and 16-byte tag; fails authentication without returning plaintext.                                                                                                                       |
| `build_header(length, salt, nonce) -> header_bytes`                              | Validates field sizes and creates exactly 34 bytes in V1 field order.                                                                                                                                                           |
| `parse_header(header_bytes) -> (length, salt, nonce)`                            | Requires 34 bytes, validates Magic/Length, and rejects malformed input.                                                                                                                                                         |
| `header_seed(stego_key_bytes) -> seed_bytes`                                     | Returns `HMAC-SHA256(stego_key, b"STEGOCHAT-HEADER")`.                                                                                                                                                                          |
| `body_seed(stego_key_bytes, salt) -> seed_bytes`                                 | Returns `HMAC-SHA256(stego_key, b"STEGOCHAT-BODY" + salt)`.                                                                                                                                                                     |
| `select_positions(seed, width, height, count, excluded_positions) -> positions`  | Returns `count` unique valid `(x, y, channel)` RGB positions deterministically and excludes all supplied reserved positions; fails if they cannot fit.                                                                          |
| `stego.lsb.embed_payload(cover_rgb, header, body, stego_key_bytes) -> stego_rgb` | LSB layer only. Validates RGB/capacity, reserves header positions, excludes them from body selection, and changes only selected channel LSBs. It writes the caller-provided header and body and never derives keys or encrypts. |
| `stego.lsb.extract_payload(stego_rgb, stego_key_bytes) -> raw_payload_bytes`     | LSB layer only. Extracts and returns the **raw V1 payload** (`header + body`) exactly as embedded. It performs no parsing, key derivation, authentication, or decryption and never returns plaintext.                           |
| `capacity_bits(width, height) -> int`                                            | Returns `width * height * 3` for a valid RGB image.                                                                                                                                                                             |
| `mse(original_rgb, stego_rgb) -> float`                                          | Requires equal-size RGB images and returns mean squared channel error. Not implemented yet.                                                                                                                                     |
| `psnr(mse_value) -> float`                                                       | Returns infinite value for zero MSE; otherwise applies the 8-bit PSNR formula. Not implemented yet.                                                                                                                             |

### Core orchestration layer

These functions are the only V1 entry points that handle plaintext. They compose the LSB/payload layer and the crypto layer and own the plaintext boundary.

| Function                                                                             | Contract                                                                                                                                                                                                                                               |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `stegochat.core.embed_plaintext(cover_rgb, plaintext, stego_key_bytes) -> stego_rgb` | Orchestration. Validates and UTF-8 encodes plaintext, derives the AES key with PBKDF2-HMAC-SHA256, encrypts with AES-256-GCM, builds the V1 payload, and delegates embedding to `stego.lsb.embed_payload`.                                             |
| `stegochat.core.extract_plaintext(stego_rgb, stego_key_bytes) -> str`                | Orchestration. Calls `stego.lsb.extract_payload` to obtain the raw V1 payload, parses it, derives the AES key, and returns UTF-8 plaintext only after AES-GCM authentication and decryption succeed. This is the only V1 path that produces plaintext. |

Responsibility split: the LSB layer never holds an AES key, and the crypto layer never touches pixels. Only `stegochat.core` composes the two, which is why `stego.lsb.extract_payload()` returns `header + body` rather than plaintext.

## Repository module responsibilities

The repository already provides top-level package scaffolding. The following responsibility map guides later implementation without adding code in this stage.

| Planned path      | Responsibility                                                                                                                           |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `crypto/`         | PBKDF2-HMAC-SHA256 key derivation, AES-256-GCM encrypt/decrypt, and authentication failure boundary                                      |
| `stego/`          | V1 payload handling, HMAC seed derivation, deterministic positions, RGB validation, capacity checks, and LSB embed/extract orchestration |
| `analysis/`       | MSE, PSNR, and any non-protocol quality reporting                                                                                        |
| `tests/`          | Unit, boundary, and integration tests for all V1 contracts without storing real secrets                                                  |
| `data/`           | Non-secret sample assets used by tests/demonstrations, subject to source/licensing review                                                |
| `results/`        | Generated local artifacts such as reports or images; excluded from Git by the existing ignore policy                                     |
| `app.py` (future) | Streamlit presentation and file/input workflow; delegates to `crypto/`, `stego/`, and `analysis/`                                        |

No component may serialize `stego_key` into the payload, logs, tests, configuration, or generated results.
