# StegoChat Planning

## Project goal

StegoChat is a university UTS project that encrypts a message and conceals the resulting authenticated payload in an RGB image. A recipient who supplies the same independent user-provided `stego_key` can deterministically find the payload, validate it, and decrypt it. The project demonstrates applied cryptography, image steganography, capacity handling, integrity checking, and objective image-quality measurement.

## Scope

### In scope

- A local Streamlit workflow for hiding and extracting a message in an RGB image.
- PBKDF2-HMAC-SHA256 with 100,000 iterations to derive a 32-byte AES-256 key from `stego_key` and a random payload salt.
- AES-256-GCM encryption and authentication.
- The V1 payload format, deterministic two-stage position selection, and RGB one-bit LSB embedding in [System Design V1](system-design-v1.md).
- Capacity validation before modifying an image.
- Extraction validation, clear failure handling, and MSE/PSNR reporting.
- Automated unit/integration tests, documentation, and demonstration evidence.

### Explicitly out of scope

- Network chat, accounts, user authentication, databases, cloud storage, or message-delivery services.
- Storing, recovering, transmitting, or logging `stego_key` values.
- Custom cryptographic algorithms, alternative encryption modes, or alternate key-derivation schemes.
- Hiding data in audio, video, documents, indexed-color images, or non-RGB channels.
- Compression, forward error correction, payload fragmentation, steganalysis-resistance claims, or covert-channel guarantees.
- Mobile clients, multi-user collaboration, persistent chat history, and production deployment.

## Lightweight Scrum: one-week plan

The three-person team holds a short daily stand-up covering completed work, next work, and blockers. Work is kept on a visible task board, reviewed in small increments, and adjusted from test feedback.

| Day | Focus | Expected outcome |
| --- | --- | --- |
| 1 | Confirm requirements, document V1, and prepare repository/test layout | Agreed protocol, roles, backlog, and acceptance criteria |
| 2 | Implement and test cryptography and payload boundaries | Key-derivation, encrypt/decrypt, and format tests pass |
| 3 | Implement and test positions, capacity checks, and RGB LSB operations | Deterministic embed/extract primitives pass |
| 4 | Integrate the hide/extract path and image metrics | End-to-end round trip and failure cases pass |
| 5 | Implement the Streamlit workflow and input validation | Usable local demonstration path |
| 6 | Regression test, peer review, measure quality, and capture evidence | Test report, screenshots, and demo assets |
| 7 | Hold buffer, review documentation, rehearse, and package submission | Submission-ready result with limitations stated |

## Product backlog and epics

| Priority | Epic | Backlog items |
| --- | --- | --- |
| 1 | Protocol foundation | Record V1 decisions, constants, error model, and acceptance tests |
| 2 | Cryptography and payload | PBKDF2, AES-GCM, V1 payload construction/parsing, authentication failures |
| 3 | Image steganography | RGB validation, capacity, HMAC-seeded positions, reserved headers, LSB operations |
| 4 | Quality and verification | MSE/PSNR, malformed-input checks, wrong-key/tamper checks, repeatable test evidence |
| 5 | User workflow | Streamlit hide/extract screens, file handling, validation, status/errors, downloads |
| 6 | Submission readiness | README, design document, test results, demo images/screenshots, presentation material |

## Three-person responsibility split

| Team member | Primary responsibility | Review responsibility |
| --- | --- | --- |
| Member 1 | Cryptography and payload: PBKDF2, AES-GCM, V1 payload boundaries, crypto tests | Review positions and integration tests |
| Member 2 | Steganography and metrics: RGB validation, capacity, deterministic positions, LSB, MSE/PSNR, image tests | Review crypto and payload tests |
| Member 3 | Streamlit integration and delivery: input/output validation, user errors, documentation, demo evidence | Review end-to-end flows and release checklist |

All members attend stand-ups, review changes, and share responsibility for integration and regression testing.

## Definition of Done

A backlog item is complete only when:

- It follows System Design V1 and has been peer reviewed.
- Focused automated tests pass for valid, boundary, and relevant failure cases.
- Its error behavior is deliberate and does not expose `stego_key` or decrypted content.
- Documentation and visible behavior are updated where required.
- It adds no unapproved dependency, secret, or unrelated repository change.
- The integrated application still completes a valid hide/extract round trip where applicable.

## Main technical and project risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Image capacity is too small | The payload cannot be embedded | Calculate capacity before modification and test exact boundaries |
| PRNG positions differ during extraction | Header/body cannot be recovered | Use specified HMAC-SHA256 seeds, deterministic unique sampling, and test vectors; never use Python `hash()` |
| Header/body position overlap | Data is overwritten or extraction becomes inconsistent | Reserve header positions and exclude them from body selection |
| Wrong `stego_key` or altered payload | Misleading decrypted output or lost integrity | Validate header fields and require AES-GCM authentication before returning plaintext |
| AES-GCM nonce reuse | Breaks AES-GCM security guarantees | Generate a fresh random nonce per payload and test the construction boundary |
| Payload-format inconsistency | Components cannot interoperate | Maintain one V1 format definition and build/parse tests |
| Lossy image conversion | Embedded bits can be destroyed | Require a lossless RGB-preserving output path and test it |
| One-week schedule pressure | Incomplete or weakly verified submission | Deliver vertical slices early and retain a final buffer day |

## Testing and assignment deliverables

The submission evidence should include the approved source code, the existing dependency manifest, this plan, System Design V1, and the README. Verification evidence must cover:

- Unit tests for key derivation, AES-GCM success/failure behavior, payload fields, deterministic header/body positions, reserved-position exclusion, RGB LSB operations, capacity limits, MSE, and PSNR.
- Integration tests for a message round trip and wrong `stego_key`, altered image/payload, invalid magic, invalid length, unsupported image mode, and insufficient capacity.
- Demonstration evidence showing cover/stego images, successful extraction, a failed wrong-key or tamper attempt, and MSE/PSNR results.
- A brief presentation or report explaining the V1 architecture, security boundaries, stated scope limitations, test results, and each member's contribution.

StegoChat is an educational implementation. The submission must not claim that LSB embedding is undetectable or sufficient as production-grade secrecy on its own.
