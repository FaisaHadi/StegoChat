"""Tests for StegoChat V1 deterministic position selection."""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

from stego.prng import (
    HEADER_POSITION_COUNT,
    body_seed,
    header_seed,
    select_body_positions,
    select_header_positions,
)
from stego.payload import SALT_LENGTH

WIDTH = 16
HEIGHT = 16


def test_header_seed_is_deterministic() -> None:
    stego_key = secrets.token_bytes(32)

    assert header_seed(stego_key) == header_seed(stego_key)


def test_body_seed_is_deterministic() -> None:
    stego_key = secrets.token_bytes(32)
    salt = secrets.token_bytes(SALT_LENGTH)

    assert body_seed(stego_key, salt) == body_seed(stego_key, salt)


def test_header_and_body_seeds_differ() -> None:
    stego_key = secrets.token_bytes(32)
    salt = secrets.token_bytes(SALT_LENGTH)

    assert header_seed(stego_key) != body_seed(stego_key, salt)


def test_changing_stego_key_changes_seed() -> None:
    assert header_seed(secrets.token_bytes(32)) != header_seed(secrets.token_bytes(32))


def test_changing_salt_changes_body_seed() -> None:
    stego_key = secrets.token_bytes(32)

    assert body_seed(stego_key, secrets.token_bytes(SALT_LENGTH)) != body_seed(
        stego_key, secrets.token_bytes(SALT_LENGTH)
    )


def test_same_inputs_produce_identical_header_positions() -> None:
    stego_key = secrets.token_bytes(32)

    assert select_header_positions(stego_key, WIDTH, HEIGHT) == select_header_positions(
        stego_key, WIDTH, HEIGHT
    )


def test_different_seeds_produce_different_position_ordering() -> None:
    salt = secrets.token_bytes(SALT_LENGTH)
    first_key = secrets.token_bytes(32)
    second_key = secrets.token_bytes(32)

    first_positions = select_body_positions(
        first_key, salt, WIDTH, HEIGHT, 24, ()
    )
    second_positions = select_body_positions(
        second_key, salt, WIDTH, HEIGHT, 24, ()
    )

    assert first_positions != second_positions


def test_header_positions_are_unique_and_exactly_v1_size() -> None:
    positions = select_header_positions(secrets.token_bytes(32), WIDTH, HEIGHT)

    assert len(positions) == HEADER_POSITION_COUNT == 272
    assert len(set(positions)) == HEADER_POSITION_COUNT


def test_body_positions_are_unique_and_exclude_reserved_header_positions() -> None:
    stego_key = secrets.token_bytes(32)
    salt = secrets.token_bytes(SALT_LENGTH)
    header_positions = select_header_positions(stego_key, WIDTH, HEIGHT)

    body_positions = select_body_positions(
        stego_key, salt, WIDTH, HEIGHT, 100, header_positions
    )

    assert len(body_positions) == 100
    assert len(set(body_positions)) == len(body_positions)
    assert set(body_positions).isdisjoint(header_positions)


def test_header_selection_rejects_an_image_that_is_too_small() -> None:
    with pytest.raises(ValueError, match="insufficient"):
        select_header_positions(secrets.token_bytes(32), 9, 10)


def test_body_selection_rejects_insufficient_non_reserved_positions() -> None:
    stego_key = secrets.token_bytes(32)
    salt = secrets.token_bytes(SALT_LENGTH)
    reserved_position = [(0, 0, 0)]

    with pytest.raises(ValueError, match="insufficient"):
        select_body_positions(stego_key, salt, 1, 1, 3, reserved_position)


def test_positions_are_valid_rgb_channel_coordinates() -> None:
    stego_key = secrets.token_bytes(32)
    salt = secrets.token_bytes(SALT_LENGTH)
    header_positions = select_header_positions(stego_key, WIDTH, HEIGHT)
    body_positions = select_body_positions(
        stego_key, salt, WIDTH, HEIGHT, 50, header_positions
    )

    for x, y, channel in header_positions + body_positions:
        assert 0 <= x < WIDTH
        assert 0 <= y < HEIGHT
        assert channel in (0, 1, 2)


def test_header_positions_are_reproducible_across_python_processes() -> None:
    stego_key = secrets.token_bytes(32)
    project_root = Path(__file__).resolve().parents[1]
    process_code = (
        "import json, sys\n"
        "from stego.prng import select_header_positions\n"
        "positions = select_header_positions(bytes.fromhex(sys.argv[1]), 16, 16)\n"
        "print(json.dumps(positions))\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", process_code, stego_key.hex()],
        check=True,
        capture_output=True,
        cwd=project_root,
        text=True,
    )

    assert json.loads(completed.stdout) == [
        list(position) for position in select_header_positions(stego_key, WIDTH, HEIGHT)
    ]
