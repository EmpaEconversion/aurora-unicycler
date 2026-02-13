"""Tests for tomato conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    CyclingProtocol,
    Loop,
    OpenCircuitVoltage,
    RecordParams,
    SampleParams,
    Step,
    Tag,
)


def test_to_tomato_mpg2(test_data: dict) -> None:
    """Test converting a CyclingProtocol instance to Tomato MPG2 format."""
    protocol = CyclingProtocol.from_dict(test_data["protocol_dicts"][0])
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


def test_overwriting_name_capacity(test_data: dict) -> None:
    """Allow overwriting name and capacity."""
    protocol = CyclingProtocol.from_dict(test_data["protocol_dicts"][0])
    tomato_json = json.loads(
        protocol.to_tomato_mpg2(sample_name="this has changed", capacity_mAh=99.99),
    )
    assert tomato_json["sample"]["name"] == "this has changed"
    assert tomato_json["sample"]["capacity_mAh"] == 99.99


def test_blank_name() -> None:
    """Converting without sample name fails."""
    protocol = CyclingProtocol(
        record=RecordParams(time_s=1),
        method=[OpenCircuitVoltage(until_time_s=1)],
    )
    with pytest.raises(ValueError) as excinfo:
        protocol.to_tomato_mpg2()
    assert "blank sample name" in str(excinfo.value)


def test_techniques() -> None:
    """Ensure techniques are created as expected."""
    protocol = CyclingProtocol(
        sample=SampleParams(name="test", capacity_mAh=1),
        record=RecordParams(time_s=1),
        method=[
            ConstantCurrent(current_mA=-1, until_time_s=12, until_voltage_V=3),
            ConstantVoltage(voltage_V=3, until_rate_C=-1),
            ConstantCurrent(rate_C=1, until_time_s=60),
        ],
    )
    tomato_json = json.loads(protocol.to_tomato_mpg2())
    assert tomato_json["method"][0]["technique"] == "constant_current"
    assert tomato_json["method"][0]["current"] == -0.001
    assert tomato_json["method"][0]["limit_voltage_min"] == 3.0
    assert tomato_json["method"][1]["technique"] == "constant_voltage"
    assert tomato_json["method"][1]["voltage"] == 3.0
    assert tomato_json["method"][1]["limit_current_max"] == "1.0D"
    assert tomato_json["method"][2]["technique"] == "constant_current"
    assert tomato_json["method"][2]["current"] == "1.0C"


def test_unknown_step() -> None:
    """If unsupported steps are in protocol, raise error."""

    class UnknownStep(Step):
        step: str = "wait, what"

    protocol = CyclingProtocol.model_construct(
        sample=SampleParams(name="test"),
        record=RecordParams(time_s=1),
        method=[UnknownStep()],
    )
    with pytest.raises(NotImplementedError) as excinfo:
        protocol.to_tomato_mpg2()
    assert "to_tomato_mpg2() does not support step type: wait, what" in str(excinfo.value)


def test_save_file(tmpdir: Path) -> None:
    """Check file is written correctly."""
    protocol = CyclingProtocol(
        sample=SampleParams(name="test"),
        record=RecordParams(time_s=1),
        method=[
            Tag(tag="a"),
            ConstantCurrent(current_mA=0.01, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_time_s=1),
            ConstantCurrent(current_mA=0.01, until_voltage_V=3),
            Loop(loop_to="a", cycle_count=100),
        ],
    )
    filepath = Path(tmpdir / "test.json")
    res = json.loads(protocol.to_tomato_mpg2(save_path=filepath))
    assert filepath.exists()
    with (tmpdir / "test.json").open("r") as f:
        file_res = json.loads(f.read())
    assert res == file_res
