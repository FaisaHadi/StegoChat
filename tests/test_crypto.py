"""Tests for StegoChat V1 cryptographic contracts."""

from __future__ import annotations

import secrets

import pytest
from cryptography.exceptions import InvalidTag

from crypto.aes import AUTH_TAG_LENGTH, generate_nonce, decrypt_gcm, encrypt_gcm
from crypto.kdf import AES_KEY_LENGTH, SALT_LENGTH, derive_aes_key, generate_salt


def test_pbkdf2_returns_32_byte_key() -> None:
    derived_key = derive_aes_key(secrets.token_bytes(32), generate_salt())

    assert len(derived_key) == AES_KEY_LENGTH


def test_same_stego_key_and_salt_produce_same_key() -> None:
    stego_key = secrets.token_bytes(32)
    salt = generate_salt()

    assert derive_aes_key(stego_key, salt) == derive_aes_key(stego_key, salt)


def test_different_salts_produce_different_keys() -> None:
    stego_key = secrets.token_bytes(32)

    assert derive_aes_key(stego_key, generate_salt()) != derive_aes_key(
        stego_key, generate_salt()
    )


def test_aes_gcm_round_trip() -> None:
    aes_key = derive_aes_key(secrets.token_bytes(32), generate_salt())
    nonce = generate_nonce()
    plaintext = b"StegoChat V1 authenticated message"

    ciphertext, auth_tag = encrypt_gcm(plaintext, aes_key, nonce)

    assert len(auth_tag) == AUTH_TAG_LENGTH
    assert decrypt_gcm(ciphertext, auth_tag, aes_key, nonce) == plaintext


def test_wrong_key_fails_authentication() -> None:
    correct_key = secrets.token_bytes(32)
    wrong_key = secrets.token_bytes(32)
    nonce = generate_nonce()
    plaintext = b"Protected StegoChat message"
    ciphertext, auth_tag = encrypt_gcm(plaintext, correct_key, nonce)

    with pytest.raises(InvalidTag):
        decrypt_gcm(ciphertext, auth_tag, wrong_key, nonce)


def test_derive_aes_key_rejects_non_v1_salt_length() -> None:
    with pytest.raises(ValueError):
        derive_aes_key(secrets.token_bytes(32), secrets.token_bytes(SALT_LENGTH - 1))


def test_modified_ciphertext_fails_authentication() -> None:
    aes_key = secrets.token_bytes(32)
    nonce = generate_nonce()
    ciphertext, auth_tag = encrypt_gcm(b"Authenticated data", aes_key, nonce)
    modified_ciphertext = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]

    with pytest.raises(InvalidTag):
        decrypt_gcm(modified_ciphertext, auth_tag, aes_key, nonce)


def test_modified_authentication_tag_fails_authentication() -> None:
    aes_key = secrets.token_bytes(32)
    nonce = generate_nonce()
    ciphertext, auth_tag = encrypt_gcm(b"Authenticated data", aes_key, nonce)
    modified_tag = bytes([auth_tag[0] ^ 1]) + auth_tag[1:]

    with pytest.raises(InvalidTag):
        decrypt_gcm(ciphertext, modified_tag, aes_key, nonce)


def test_decrypt_gcm_rejects_non_v1_authentication_tag_length() -> None:
    aes_key = secrets.token_bytes(32)
    nonce = generate_nonce()
    ciphertext, auth_tag = encrypt_gcm(b"Authenticated data", aes_key, nonce)

    with pytest.raises(ValueError):
        decrypt_gcm(ciphertext, auth_tag[:-1], aes_key, nonce)


@pytest.mark.parametrize(
    ("key_length", "nonce_length"),
    [(AES_KEY_LENGTH - 1, 12), (AES_KEY_LENGTH + 1, 12), (AES_KEY_LENGTH, 11), (AES_KEY_LENGTH, 13)],
)
def test_invalid_key_or_nonce_sizes_are_rejected(
    key_length: int, nonce_length: int
) -> None:
    with pytest.raises(ValueError):
        encrypt_gcm(
            b"input",
            secrets.token_bytes(key_length),
            secrets.token_bytes(nonce_length),
        )


def test_generated_salt_and_nonce_have_v1_lengths() -> None:
    assert len(generate_salt()) == SALT_LENGTH
    assert len(generate_nonce()) == 12
