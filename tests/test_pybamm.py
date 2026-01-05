"""Tests for PyBaMM conversion."""

from __future__ import annotations

from aurora_unicycler import (
    Loop,
    OpenCircuitVoltage,
    Protocol,
    RecordParams,
    SafetyParams,
    SampleParams,
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


def test_pybamm_loops(test_data: dict) -> None:
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
