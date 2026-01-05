"""Tests for Biologic MPS conversion."""

from __future__ import annotations

import re

from aurora_unicycler import (
    ConstantCurrent,
    ImpedanceSpectroscopy,
    Loop,
    OpenCircuitVoltage,
    Protocol,
    RecordParams,
    SafetyParams,
    Tag,
)


def test_to_biologic_mps(test_data: dict) -> None:
    """Test conversion to Biologic MPS."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag1"),
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag1", cycle_count=3),
            Loop(loop_to=4, cycle_count=3),
        ],
    )
    biologic_mps = protocol.to_biologic_mps(sample_name="test", capacity_mAh=1.0)
    # Find where the line begins with "ctrl_seq"
    lines = biologic_mps.splitlines()
    ctrl_seq_start = next(
        (i for i, line in enumerate(lines) if line.startswith("ctrl_seq")),
        None,
    )
    assert ctrl_seq_start is not None, "ctrl_seq not found in Biologic MPS"
    test_str = (
        "ctrl_seq            0                   0                   0                   "
        "0                   2                   2                   "
    )
    assert lines[ctrl_seq_start] == test_str, "ctrl_seq line does not match expected"


def test_biologic_units_ranges(test_data: dict) -> None:
    """Test that current ranges are given the expected values and units."""
    kw1 = {"until_time_s": 10.0}
    kw2 = {"start_frequency_Hz": 1e3, "end_frequency_Hz": 1}
    my_protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ConstantCurrent(**kw1, current_mA=0.001),
            ConstantCurrent(**kw1, current_mA=0.01),
            ConstantCurrent(**kw1, current_mA=0.011),
            ConstantCurrent(**kw1, current_mA=0.1),
            ConstantCurrent(**kw1, current_mA=0.11),
            ConstantCurrent(**kw1, current_mA=1.0),
            ConstantCurrent(**kw1, current_mA=1.1),
            ConstantCurrent(**kw1, current_mA=10.0),
            ConstantCurrent(**kw1, current_mA=10.1),
            ConstantCurrent(**kw1, current_mA=100),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=0.001),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=0.005),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=0.006),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=0.05),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=0.06),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=0.5),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=0.6),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=5),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=6),
            ImpedanceSpectroscopy(**kw2, amplitude_mA=50),
        ],
    )
    biologic_mps = my_protocol.to_biologic_mps(sample_name="test", capacity_mAh=1)

    # Check I range
    line = next(a for a in biologic_mps.splitlines() if a.startswith("I Range"))
    ranges = re.split(r"\s{2,}", line.strip())
    expected = ["10 µA", "100 µA", "1 mA", "10 mA", "100 mA"]
    expected = [x for x in expected for _ in (0, 1)] * 2  # a b c -> a a b b c c a a b b c c
    assert ranges[1:] == expected

    # Check applied current uses sensible units
    line = next(a for a in biologic_mps.splitlines() if a.startswith("ctrl1_val"))
    vals = [float(x) for x in line.strip().split()[1:]]
    assert vals[:10] == [1, 10, 11, 100, 110, 1.0, 1.1, 10.0, 10.1, 100]
    line = next(a for a in biologic_mps.splitlines() if a.startswith("ctrl1_val_unit"))
    units = line.strip().split()[1:]
    assert units[:10] == ["uA", "uA", "uA", "uA", "uA", "mA", "mA", "mA", "mA", "mA"]
    units_to_mA = {"uA": 1e-3, "mA": 1}
    vals = [v * units_to_mA[u] for v, u in zip(vals, units, strict=True)]
    print(vals)
    assert vals[:10] == [0.001, 0.01, 0.011, 0.1, 0.11, 1.0, 1.1, 10.0, 10.1, 100]
