"""Larger integration tests for the unicycler CyclingProtocol class."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    CyclingProtocol,
    Loop,
    OpenCircuitVoltage,
    RecordParams,
    SafetyParams,
    SampleParams,
    Step,
    Tag,
)
from aurora_unicycler._utils import tag_to_indices
from aurora_unicycler.version import __version__


def test_from_json(test_data: dict) -> None:
    """Test creating a CyclingProtocol instance from a JSON file."""
    protocol = CyclingProtocol.from_json(test_data["protocol_paths"][0])
    assert isinstance(protocol, CyclingProtocol)
    assert protocol.sample.name == "test_sample"
    assert protocol.sample.capacity_mAh == Decimal(123)
    assert len(protocol.method) == 15
    assert isinstance(protocol.method[0], OpenCircuitVoltage)
    assert isinstance(protocol.method[1], ConstantCurrent)
    assert isinstance(protocol.method[2], OpenCircuitVoltage)
    assert isinstance(protocol.method[3], ConstantCurrent)
    assert isinstance(protocol.method[4], ConstantVoltage)
    assert isinstance(protocol.method[5], ConstantCurrent)
    assert isinstance(protocol.method[6], Loop)


def test_from_dict(test_data: dict) -> None:
    """Test creating a CyclingProtocol instance from a dictionary."""
    protocol_from_dict = CyclingProtocol.from_dict(test_data["protocol_dicts"][0])
    protocol_from_file = CyclingProtocol.from_json(test_data["protocol_paths"][0])
    assert protocol_from_dict == protocol_from_file


def test_check_sample_details(test_data: dict) -> None:
    """Test handling of missing sample details."""
    missing_name_msg = (
        "If using blank sample name or $NAME placeholder, "
        "a sample name must be provided in this function."
    )
    protocol = CyclingProtocol.from_dict(test_data["protocol_dicts"][1])
    with pytest.raises(ValueError) as context:
        protocol.to_neware_xml()
    assert str(context.value) == missing_name_msg
    protocol = CyclingProtocol.from_dict(test_data["protocol_dicts"][2])
    with pytest.raises(ValueError) as context:
        protocol.to_neware_xml()
    assert str(context.value) == missing_name_msg

    missing_cap_msg = "Sample capacity must be set if using C-rate steps."
    protocol = CyclingProtocol.from_dict(test_data["protocol_dicts"][1], sample_name="test_sample")
    with pytest.raises(ValueError) as context:
        protocol.to_neware_xml()
    assert str(context.value) == missing_cap_msg
    protocol = CyclingProtocol.from_dict(test_data["protocol_dicts"][2], sample_name="test_sample")
    with pytest.raises(ValueError) as context:
        protocol.to_neware_xml()
    assert str(context.value) == missing_cap_msg

    # should not raise error if both are provided
    protocol1 = CyclingProtocol.from_dict(
        test_data["protocol_dicts"][1], sample_name="test_sample", sample_capacity_mAh=123
    )
    protocol2 = CyclingProtocol.from_dict(
        test_data["protocol_dicts"][2],
        sample_name="test_sample",
        sample_capacity_mAh=123,
    )
    protocol1.to_neware_xml()
    protocol2.to_neware_xml()
    assert protocol1.sample.name == "test_sample"
    assert protocol1.sample.capacity_mAh == Decimal(123)
    assert protocol1 == protocol2


def test_overwriting_sample_details(test_data: dict) -> None:
    """Test overwriting sample details when creating from a dictionary."""
    protocol = CyclingProtocol.from_dict(
        test_data["protocol_dicts"][0], sample_name="NewName", sample_capacity_mAh=456
    )
    assert protocol.sample.name == "NewName"
    assert protocol.sample.capacity_mAh == Decimal(456)


def test_create_protocol(test_data: dict) -> None:
    """Test creating a CyclingProtocol instance from a dictionary."""
    protocol = CyclingProtocol.from_dict(test_data["protocol_dicts"][0])
    protocol = CyclingProtocol(
        sample=SampleParams(
            name="test_sample",
            capacity_mAh=123,
        ),
        record=RecordParams(
            time_s=Decimal(10),
            voltage_V=0.1,
            current_mA="0.1",
        ),
        safety=SafetyParams(
            max_current_mA=10,
            min_current_mA=-10,
            max_voltage_V=5,
            min_voltage_V=-0.1,
            delay_s=10,
        ),
        method=[
            OpenCircuitVoltage(
                until_time_s=60 * 60,
            ),
            ConstantCurrent(
                rate_C=1 / 10,
                until_time_s=60 * 10,
                until_voltage_V=2,
            ),
            OpenCircuitVoltage(
                until_time_s=60 * 60 * 12,
            ),
            ConstantCurrent(
                rate_C=0.1,
                until_time_s=60 * 60 * 1 / 0.1 * 1.5,
                until_voltage_V=4.9,
            ),
            ConstantVoltage(
                voltage_V=4.9,
                until_rate_C=0.01,
                until_time_s=60 * 60 * 6,
            ),
            ConstantCurrent(
                rate_C=-0.1,
                until_time_s=60 * 60 * 1 / 0.1 * 1.5,
                until_voltage_V=3.5,
            ),
            Loop(
                loop_to=4,
                cycle_count=3,
            ),
        ],
    )
    protocol_dict = json.loads(protocol.model_dump_json())
    assert protocol_dict["sample"]["name"] == "test_sample"
    # Should be able to be parsed into other formats
    protocol.to_neware_xml()
    protocol.to_tomato_mpg2()
    protocol.to_pybamm_experiment()
    protocol.to_biologic_mps()


def test_tags() -> None:
    """Test tags in CyclingProtocol."""
    # Different tags are fine
    CyclingProtocol(
        record=RecordParams(time_s=1),
        method=[Tag(tag="a"), Tag(tag="aa"), Tag(tag="aaa")],
    )
    # Duplicates not allowed
    with pytest.raises(ValueError) as exc_info:
        CyclingProtocol(
            record=RecordParams(time_s=1),
            method=[Tag(tag="a"), Tag(tag="b"), Tag(tag="b")],
        )
    assert "Duplicate tags" in str(exc_info)


def test_tags_to_indices() -> None:
    """Test converting tags to indices in CyclingProtocol."""
    protocol = CyclingProtocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=2, cycle_count=3),
        ],
    )
    tag_to_indices(protocol)
    # this should not change the loop step
    assert isinstance(protocol.method[4], Loop)
    assert protocol.method[4].loop_to == 2

    protocol = CyclingProtocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),  # 0
            OpenCircuitVoltage(until_time_s=1),  # 1
            Tag(tag="tag1"),
            OpenCircuitVoltage(until_time_s=1),  # 2
            OpenCircuitVoltage(until_time_s=1),  # 3
            Loop(loop_to="tag1", cycle_count=3),  # 4
            OpenCircuitVoltage(until_time_s=1),  # 5
            Loop(loop_to=3, cycle_count=3),  # 6
        ],
    )
    # tag should be removed and replaced with the index
    tag_to_indices(protocol)
    assert isinstance(protocol.method[4], Loop)
    assert protocol.method[4].loop_to == 3
    assert isinstance(protocol.method[6], Loop)
    assert protocol.method[6].loop_to == 3

    protocol = CyclingProtocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),  # 0
            OpenCircuitVoltage(until_time_s=1),  # 1
            Tag(tag="tag1"),
            OpenCircuitVoltage(until_time_s=1),  # 2
            Tag(tag="tag2"),
            OpenCircuitVoltage(until_time_s=1),  # 3
            Loop(loop_to="tag1", cycle_count=3),  # 4
            OpenCircuitVoltage(until_time_s=1),  # 5
            Loop(loop_to=6, cycle_count=3),  # 6
            Tag(tag="tag3"),
            OpenCircuitVoltage(until_time_s=1),  # 7
            Loop(loop_to="tag2", cycle_count=3),  # 8
            OpenCircuitVoltage(until_time_s=1),  # 9
            OpenCircuitVoltage(until_time_s=1),  # 10
            Loop(loop_to="tag1", cycle_count=3),  # 11
            Tag(tag="tag that doesnt do anything"),
            Loop(loop_to="tag3", cycle_count=3),  # 12
        ],
    )
    tag_to_indices(protocol)
    assert isinstance(protocol.method[4], Loop)
    assert protocol.method[4].loop_to == 3
    assert isinstance(protocol.method[6], Loop)
    assert protocol.method[6].loop_to == 4
    assert isinstance(protocol.method[8], Loop)
    assert protocol.method[8].loop_to == 4
    assert isinstance(protocol.method[11], Loop)
    assert protocol.method[11].loop_to == 3
    assert isinstance(protocol.method[12], Loop)
    assert protocol.method[12].loop_to == 8


def test_coerce_c_rate_in_protocol(test_data: dict) -> None:
    """Test the coerce_c_rate function in a protocol context."""
    protocol = CyclingProtocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            ConstantCurrent(until_time_s=1, rate_C="1/5"),
            ConstantCurrent(until_time_s=1, rate_C=0.2),
            ConstantCurrent(until_time_s=1, rate_C="C / 5"),
            ConstantCurrent(until_time_s=1, rate_C="0.2"),
            ConstantCurrent(until_time_s=1, rate_C=1 / 5),
            ConstantCurrent(until_time_s=1, rate_C="-0.2"),
            ConstantCurrent(until_time_s=1, rate_C="D/5"),
            ConstantVoltage(voltage_V=4.2, until_rate_C="C/5"),
            ConstantVoltage(voltage_V=4.2, until_rate_C="0.2"),
            ConstantVoltage(voltage_V=4.2, until_rate_C=1 / 5),
            ConstantVoltage(voltage_V=4.2, until_rate_C="C/5"),
        ],
    )
    assert protocol.method[0].rate_C == 0.2
    assert protocol.method[1].rate_C == 0.2
    assert protocol.method[2].rate_C == 0.2
    assert protocol.method[3].rate_C == 0.2
    assert protocol.method[4].rate_C == 0.2
    assert protocol.method[5].rate_C == -0.2
    assert protocol.method[6].rate_C == -0.2
    assert protocol.method[7].until_rate_C == 0.2
    assert protocol.method[8].until_rate_C == 0.2
    assert protocol.method[9].until_rate_C == 0.2
    assert protocol.method[10].until_rate_C == 0.2


def test_build_steps() -> None:
    """User should be able to make steps with Step base class."""
    CyclingProtocol.from_dict(
        {
            "record": {"time_s": 1},
            "safety": {},
            "method": [
                {"step": "open_circuit_voltage", "until_time_s": 1},
                {"step": "tag", "tag": "tag1"},
                {"step": "constant_current", "rate_C": 0.5, "until_voltage_V": 4.2},
                {"step": "constant_voltage", "voltage_V": 4.2, "until_rate_C": 0.05},
                {"step": "constant_current", "rate_C": -0.5, "until_voltage_V": 3.0},
                {"step": "loop", "loop_to": "tag1", "cycle_count": 3},
                {
                    "step": "impedance_spectroscopy",
                    "amplitude_V": 0.1,
                    "start_frequency_Hz": 1e3,
                    "end_frequency_Hz": 1,
                },
            ],
        }
    )


def test_naughty_step_building() -> None:
    """Users can give a dict for methods without from_dict, but type checkers don't like it."""
    CyclingProtocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            {"step": "open_circuit_voltage", "until_time_s": 1},
            {"step": "tag", "tag": "tag1"},
            {"step": "constant_current", "rate_C": 0.5, "until_voltage_V": 4.2},
            {"step": "constant_voltage", "voltage_V": 4.2, "until_rate_C": 0.05},
            {"step": "constant_current", "rate_C": -0.5, "until_voltage_V": 3.0},
            {"step": "loop", "loop_to": "tag1", "cycle_count": 3},
            {
                "step": "impedance_spectroscopy",
                "amplitude_V": 0.1,
                "start_frequency_Hz": 1e3,
                "end_frequency_Hz": 1,
            },
        ],
    )


def test_empty_steps() -> None:
    """CyclingProtocols with empty steps should give a nice error."""
    # As a protocol
    with pytest.raises(ValidationError) as exc_info:
        CyclingProtocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                Step(),
            ],
        )
    assert "is incomplete" in str(exc_info.value)
    # From a dict
    with pytest.raises(ValidationError) as exc_info:
        CyclingProtocol.from_dict(
            {
                "record": {"time_s": 1},
                "safety": {},
                "method": [
                    {},
                ],
            }
        )
    assert "is incomplete" in str(exc_info.value)


def test_updating_version() -> None:
    """Reading the file in should update the version to current version."""
    my_protocol = CyclingProtocol.from_dict(
        {
            "unicycler": {"version": "x.y.z"},
            "record": {"time_s": 1},
            "safety": {},
            "method": [{"step": "open_circuit_voltage", "until_time_s": 1}],
        }
    )
    assert my_protocol.unicycler.version == __version__


def test_mutability() -> None:
    """Conversion functions should not mutate the protocol object."""
    my_protocol = CyclingProtocol.from_dict(
        {
            "unicycler": {"version": "x.y.z"},
            "sample": {"name": "test_sample"},
            "record": {"time_s": 1},
            "safety": {},
            "method": [
                {"step": "tag", "tag": "tag1"},
                {"step": "open_circuit_voltage", "until_time_s": 1},
                {"step": "loop", "loop_to": "tag1", "cycle_count": 3},
            ],
        }
    )
    my_original_protocol = my_protocol.model_copy()
    assert my_protocol is not my_original_protocol
    assert my_protocol == my_original_protocol

    my_protocol.to_neware_xml()
    assert my_protocol == my_original_protocol

    my_protocol.to_tomato_mpg2()
    assert my_protocol == my_original_protocol

    my_protocol.to_pybamm_experiment()
    assert my_protocol == my_original_protocol

    my_protocol.to_biologic_mps()
    assert my_protocol == my_original_protocol

    my_protocol.to_battinfo_jsonld()
    assert my_protocol == my_original_protocol


def test_protocol_export() -> None:
    """Check converting to dict or JSON works."""
    ref_protocol_dict = {
        "record": {
            "time_s": 1.0,
            "current_mA": None,
            "voltage_V": None,
        },
        "sample": {"capacity_mAh": None, "name": "test"},
        "safety": {
            "min_voltage_V": 0.0,
            "max_voltage_V": 5.0,
            "min_current_mA": -10.0,
            "max_current_mA": 10.0,
            "delay_s": 0.5,
            "max_capacity_mAh": None,
        },
        "method": [
            {"id": None, "step": "open_circuit_voltage", "until_time_s": 100.0},
        ],
    }
    protocol_dict = CyclingProtocol.from_dict(ref_protocol_dict).to_dict()
    ref_protocol_dict["unicycler"] = "don't check this"
    protocol_dict["unicycler"] = "don't check this"
    assert protocol_dict == ref_protocol_dict


def test_write_json(tmpdir: Path) -> None:
    """Test reading and writing to JSON file."""
    filepath = Path(tmpdir) / "protocol.json"
    ref_protocol_dict = {
        "record": {
            "time_s": 1.0,
            "current_mA": None,
            "voltage_V": None,
        },
        "sample": {"capacity_mAh": None, "name": "test"},
        "safety": {
            "min_voltage_V": 0.0,
            "max_voltage_V": 5.0,
            "min_current_mA": -10.0,
            "max_current_mA": 10.0,
            "delay_s": 0.5,
            "max_capacity_mAh": None,
        },
        "method": [
            {"id": None, "step": "open_circuit_voltage", "until_time_s": 100.0},
        ],
    }
    protocol = CyclingProtocol.from_dict(ref_protocol_dict)
    protocol_str = protocol.to_json(filepath, indent=4)
    protocol2 = CyclingProtocol.from_json(filepath)
    protocol3 = CyclingProtocol.from_dict(json.loads(protocol_str))
    assert protocol == protocol2
    assert protocol == protocol3
