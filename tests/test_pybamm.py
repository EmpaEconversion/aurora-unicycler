"""Tests for PyBaMM conversion."""

from __future__ import annotations

import pytest

from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    Loop,
    OpenCircuitVoltage,
    Protocol,
    RecordParams,
    SafetyParams,
    SampleParams,
    Step,
    Tag,
)


def test_to_pybamm_experiment(test_data: dict) -> None:
    """Test converting a Protocol instance to PyBaMM experiment format."""
    protocol = Protocol.from_dict(test_data["protocol_dicts"][0])
    experiment_list = protocol.to_pybamm_experiment()
    assert isinstance(experiment_list, list)
    assert len(experiment_list) > 0
    assert isinstance(experiment_list[0], str)
    assert experiment_list[0].startswith("Rest for")
    assert experiment_list[1].startswith("Charge at")
    assert experiment_list[2].startswith("Rest for")
    assert experiment_list[3].startswith("Charge at")
    assert experiment_list[4].startswith("Hold at")
    assert experiment_list[5].startswith("Discharge at")
    assert experiment_list[6].startswith("Charge at")  # no 'loop' in pybamm experiment


def test_different_currents() -> None:
    """Test different current and voltage settings."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ConstantCurrent(current_mA=1, until_time_s=7200),
            ConstantCurrent(current_mA=-1, until_time_s=3600),
            ConstantCurrent(current_mA=1, until_time_s=120),
            ConstantCurrent(current_mA=-1, until_time_s=60),
            ConstantCurrent(current_mA=1, until_time_s=67, until_voltage_V=3),
            ConstantCurrent(current_mA=-1, until_time_s=12, until_voltage_V=3),
            ConstantVoltage(voltage_V=3, until_time_s=7200, until_current_mA=0.1),
            ConstantVoltage(voltage_V=3, until_time_s=3600, until_current_mA=0.1),
            ConstantVoltage(voltage_V=3, until_time_s=120),
            ConstantVoltage(voltage_V=3, until_time_s=60),
            ConstantVoltage(voltage_V=3, until_time_s=123.456),
            ConstantVoltage(voltage_V=3, until_current_mA=0.1),
        ],
    )
    experiment_list = protocol.to_pybamm_experiment()
    assert experiment_list[0] == "Charge at 1.0 mA for 2 hours"
    assert experiment_list[1] == "Discharge at 1.0 mA for 1 hour"
    assert experiment_list[2] == "Charge at 1.0 mA for 2 minutes"
    assert experiment_list[3] == "Discharge at 1.0 mA for 1 minute"
    assert experiment_list[4] == "Charge at 1.0 mA for 67.0 seconds or until 3.0 V"
    assert experiment_list[5] == "Discharge at 1.0 mA for 12.0 seconds or until 3.0 V"
    assert experiment_list[6] == "Hold at 3.0 V for 2 hours or until 0.1 mA"
    assert experiment_list[7] == "Hold at 3.0 V for 1 hour or until 0.1 mA"
    assert experiment_list[8] == "Hold at 3.0 V for 2 minutes"
    assert experiment_list[9] == "Hold at 3.0 V for 1 minute"
    assert experiment_list[10] == "Hold at 3.0 V for 123.456 seconds"
    assert experiment_list[11] == "Hold at 3.0 V until 0.1 mA"


def test_pybamm_loops() -> None:
    """Ensure PyBaMM loops as expected."""
    protocol = Protocol(
        sample=SampleParams(
            name="test_sample",
            capacity_mAh=123,
        ),
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            Tag(tag="A"),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="A", cycle_count=123),
        ],
    )
    pybamm_experiment = protocol.to_pybamm_experiment()
    assert len(pybamm_experiment) == 123

    protocol = Protocol(
        sample=SampleParams(
            name="test_sample",
            capacity_mAh=123,
        ),
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            Tag(tag="A"),
            Tag(tag="B"),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="B", cycle_count=12),
            Loop(loop_to="A", cycle_count=34),
        ],
    )
    pybamm_experiment = protocol.to_pybamm_experiment()
    assert len(pybamm_experiment) == 12 * 34


def test_pybamm_bomb_protection() -> None:
    """Don't allow users to make a recursion bomb."""
    protocol = Protocol.model_construct(
        sample=SampleParams(name="test"),
        record=RecordParams(time_s=1),
        method=[
            Tag(tag="A"),
            Tag(tag="B"),
            Tag(tag="C"),
            Tag(tag="D"),
            Tag(tag="E"),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="E", cycle_count=100),
            Loop(loop_to="D", cycle_count=100),
            Loop(loop_to="C", cycle_count=100),
            Loop(loop_to="B", cycle_count=100),
            Loop(loop_to="A", cycle_count=100),
        ],
    )
    with pytest.raises(RuntimeError) as excinfo:
        protocol.to_pybamm_experiment()
    assert "loop definition error" in str(excinfo.value)


def test_unknown_step() -> None:
    """If unsupported steps are in protocol, raise error."""

    class UnknownStep(Step):
        step: str = "wait, what"

    protocol = Protocol.model_construct(
        sample=SampleParams(name="test"),
        record=RecordParams(time_s=1),
        method=[UnknownStep()],
    )
    with pytest.raises(NotImplementedError) as excinfo:
        protocol.to_pybamm_experiment()
    assert "to_pybamm_experiment() does not support step type: wait, what" in str(excinfo.value)
