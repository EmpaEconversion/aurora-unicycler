"""Pytest configuration."""

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data() -> dict:
    """Data passed to all pytests."""
    base_folder = Path(__file__).parent / "test_data"
    example_protocol_paths = [
        base_folder / "test_protocol.json",
        base_folder / "test_protocol_placeholder_sample.json",
        base_folder / "test_protocol_no_sample.json",
        base_folder / "test_protocol_with_floats.json",
    ]
    data = []
    for path in example_protocol_paths:
        with path.open("r") as f:
            data.append(json.load(f))

    return {
        "protocol_dicts": data,
        "protocol_paths": example_protocol_paths,
        "jsonld_path": base_folder / "test_battinfo.jsonld",
        "emmo_context_path": base_folder / "emmo_context.json",
    }
