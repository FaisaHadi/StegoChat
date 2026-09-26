"""Tests for the StegoChat V1 binary payload format."""

from __future__ import annotations

import secrets

import pytest

from stego.payload import (
    AUTH_TAG_LENGTH,
    HEADER_SIZE,
    MAGIC,
    NONCE_LENGTH,
    SALT_LENGTH,
    build_header,
    build_payload,
    parse_header,
    parse_payload,
    split_body,
)


def test_build_header_uses_v1_field_order_and_size() -> None:
    salt = secrets.token_bytes(SALT_LENGTH)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    body_length = AUTH_TAG_LENGTH + 5

    header = build_header(body_length, salt, nonce)

    assert len(header) == HEADER_SIZE == 34
    assert header[:2] == MAGIC == b"SG"
    assert int.from_bytes(header[2:6], byteorder="big") == body_length
    assert header[6:22] == salt
    assert header[22:34] == nonce


def test_parse_header_round_trips_v1_fields() -> None:
    salt = secrets.token_bytes(SALT_LENGTH)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    body_length = AUTH_TAG_LENGTH + 9

    assert parse_header(build_header(body_length, salt, nonce)) == (
        body_length,
        salt,
        nonce,
    )


def test_build_and_parse_payload_round_trip() -> None:
    ciphertext = secrets.token_bytes(21)
    auth_tag = secrets.token_bytes(AUTH_TAG_LENGTH)
    salt = secrets.token_bytes(SALT_LENGTH)
    nonce = secrets.token_bytes(NONCE_LENGTH)

    payload = build_payload(ciphertext, auth_tag, salt, nonce)

    assert parse_payload(payload) == (ciphertext, auth_tag, salt, nonce)


def test_header_rejects_invalid_magic() -> None:
    header = build_header(
        AUTH_TAG_LENGTH,
        secrets.token_bytes(SALT_LENGTH),
        secrets.token_bytes(NONCE_LENGTH),
    )
    invalid_magic_header = b"XX" + header[2:]

    with pytest.raises(ValueError, match="magic"):
        parse_header(invalid_magic_header)


def test_header_rejects_length_smaller_than_authentication_tag() -> None:
    header = (
        MAGIC
        + (AUTH_TAG_LENGTH - 1).to_bytes(4, byteorder="big")
        + secrets.token_bytes(SALT_LENGTH)
        + secrets.token_bytes(NONCE_LENGTH)
    )

    with pytest.raises(ValueError, match="authentication tag"):
        parse_header(header)


def test_build_header_rejects_invalid_salt_or_nonce_lengths() -> None:
    with pytest.raises(ValueError, match="salt"):
        build_header(
            AUTH_TAG_LENGTH,
            secrets.token_bytes(SALT_LENGTH - 1),
            secrets.token_bytes(NONCE_LENGTH),
        )

    with pytest.raises(ValueError, match="nonce"):
        build_header(
            AUTH_TAG_LENGTH,
            secrets.token_bytes(SALT_LENGTH),
            secrets.token_bytes(NONCE_LENGTH - 1),
        )


def test_parse_payload_rejects_truncated_header() -> None:
    with pytest.raises(ValueError, match="shorter than the V1 header"):
        parse_payload(secrets.token_bytes(HEADER_SIZE - 1))


def test_payload_rejects_mismatched_declared_body_length() -> None:
    header = build_header(
        AUTH_TAG_LENGTH + 1,
        secrets.token_bytes(SALT_LENGTH),
        secrets.token_bytes(NONCE_LENGTH),
    )

    with pytest.raises(ValueError, match="body length"):
        parse_payload(header + secrets.token_bytes(AUTH_TAG_LENGTH))


def test_split_body_rejects_a_body_smaller_than_tag() -> None:
    with pytest.raises(ValueError, match="authentication tag"):
        split_body(secrets.token_bytes(AUTH_TAG_LENGTH - 1))
