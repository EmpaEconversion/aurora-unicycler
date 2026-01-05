"""Tests for tomato conversion."""

from __future__ import annotations

import json

from aurora_unicycler import Protocol


def test_to_tomato_mpg2(test_data: dict) -> None:
    """Test converting a Protocol instance to Tomato MPG2 format."""
    protocol = Protocol.from_dict(test_data["protocol_dicts"][0])
    json_string = protocol.to_tomato_mpg2()
    assert isinstance(json_string, str)
    tomato_dict = json.loads(json_string)
    assert all(k in tomato_dict for k in ["version", "sample", "method", "tomato"])
    assert isinstance(tomato_dict["method"], list)
    assert len(tomato_dict["method"]) == len(protocol.method)
    assert tomato_dict["method"][0]["device"] == "MPG2"
    assert tomato_dict["method"][0]["technique"] == "open_circuit_voltage"
    assert tomato_dict["method"][1]["technique"] == "constant_current"
    assert tomato_dict["method"][2]["technique"] == "open_circuit_voltage"
    assert tomato_dict["method"][3]["technique"] == "constant_current"
    assert tomato_dict["method"][4]["technique"] == "constant_voltage"
    assert tomato_dict["method"][5]["technique"] == "constant_current"
    assert tomato_dict["method"][6]["technique"] == "loop"
