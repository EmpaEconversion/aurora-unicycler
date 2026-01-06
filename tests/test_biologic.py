"""Tests for Biologic MPS conversion."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    ImpedanceSpectroscopy,
    Loop,
    OpenCircuitVoltage,
    Protocol,
    RecordParams,
    SafetyParams,
    Step,
    Tag,
)


def test_to_biologic_mps() -> None:
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


def test_biologic_units_ranges() -> None:
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


def test_current_outside_range() -> None:
    """Check large currents not allowed."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[ConstantCurrent(current_mA=10000, until_voltage_V=4)],
    )
    with pytest.raises(ValueError) as excinfo:
        protocol.to_biologic_mps(sample_name="test")
    assert "I range not supported" in str(excinfo.value)


def test_no_name() -> None:
    """Check invalid inputs raise expected errors."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[OpenCircuitVoltage(until_time_s=1)],
    )
    with pytest.raises(ValueError) as excinfo:
        protocol.to_biologic_mps()
    assert "sample name must be provided" in str(excinfo.value)

    # Runs without error
    protocol.to_biologic_mps(sample_name="test")


def test_voltage_range() -> None:
    """Check that voltage ranges can be set, warn, and error correctly."""
    # Constant current
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[ConstantCurrent(current_mA=1, until_voltage_V=6)],
    )
    # Voltage too large
    with pytest.raises(ValueError) as excinfo:
        protocol.to_biologic_mps(sample_name="test")
    assert "voltage outside of range" in str(excinfo.value)
    # Increases range fixes
    protocol.to_biologic_mps(sample_name="test", range_V=(0, 6))

    # Constant voltage
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[ConstantVoltage(voltage_V=6, until_time_s=1)],
    )
    # Voltage too large
    with pytest.raises(ValueError) as excinfo:
        protocol.to_biologic_mps(sample_name="test")
    assert "voltage outside of range" in str(excinfo.value)
    # Increases range fixes
    protocol.to_biologic_mps(sample_name="test", range_V=(1.234, 7.654))


def test_voltage_range_warnings(caplog: pytest.LogCaptureFixture) -> None:
    """If V range outside +- 10 V, warn."""
    caplog.set_level(logging.WARNING)
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[ConstantCurrent(current_mA=1, until_voltage_V=1)],
    )
    caplog.clear()
    protocol.to_biologic_mps(sample_name="test", range_V=(0, 11))
    assert "max voltage" in caplog.text
    caplog.clear()
    protocol.to_biologic_mps(sample_name="test", range_V=(-15, 5))
    assert "max voltage" in caplog.text
    caplog.clear()
    protocol.to_biologic_mps(sample_name="test", range_V=(12.345, 0))
    assert "max voltage" in caplog.text
    caplog.clear()
    protocol.to_biologic_mps(sample_name="test", range_V=(-1.23, 1.23))
    assert not caplog.text


def test_current_and_c_rate() -> None:
    """Check that CC-CV sets the right ranges for both current in mA and C-rate."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ConstantCurrent(current_mA=1, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_time_s=10),
            ConstantCurrent(rate_C=1, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_time_s=10),
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test", capacity_mAh=1)
    assert "I Range".ljust(20) + 4 * "1 mA".ljust(20) in res

    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ConstantCurrent(current_mA=10, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_time_s=10),
            ConstantCurrent(rate_C=1, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_time_s=10),
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test", capacity_mAh=10)
    assert "I Range".ljust(20) + 4 * "10 mA".ljust(20) in res

    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ConstantCurrent(current_mA=100, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_current_mA=10),
            ConstantCurrent(rate_C=1, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_rate_C=0.1),
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test", capacity_mAh=100)
    assert "I Range".ljust(20) + 4 * "100 mA".ljust(20) in res

    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ConstantCurrent(current_mA=1, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_current_mA=0.1),
            ConstantCurrent(rate_C=1, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_rate_C=0.1),
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test", capacity_mAh=100)
    assert "I Range".ljust(20) + 2 * "1 mA".ljust(20) + 2 * "100 mA".ljust(20) in res


def test_impedance_currents() -> None:
    """Check if impedance currents set correct units and ranges."""
    # 1 uA, uses 10 uA range, gives values in uA
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_mA=0.001, start_frequency_Hz=1, end_frequency_Hz=100)
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "I Range".ljust(20) + "10 µA".ljust(20) in res
    assert "ctrl1_val".ljust(20) + "1.000".ljust(20) in res
    assert "ctrl1_val_unit".ljust(20) + "uA".ljust(20) in res

    # 0.5 mA, uses 1 mA range, gives values in uA
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_mA=0.5, start_frequency_Hz=1, end_frequency_Hz=100)
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "I Range".ljust(20) + "1 mA".ljust(20) in res
    assert "ctrl1_val".ljust(20) + "500.000".ljust(20) in res
    assert "ctrl1_val_unit".ljust(20) + "uA".ljust(20) in res

    # 1 mA, uses 10 mA range, gives values in mA
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[ImpedanceSpectroscopy(amplitude_mA=1, start_frequency_Hz=1, end_frequency_Hz=100)],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "I Range".ljust(20) + "10 mA".ljust(20) in res
    assert "ctrl1_val".ljust(20) + "1.000".ljust(20) in res
    assert "ctrl1_val_unit".ljust(20) + "mA".ljust(20) in res

    # 100 mA, uses 1 A range, gives values in mA
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_mA=100, start_frequency_Hz=1, end_frequency_Hz=100)
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "I Range".ljust(20) + "1 A".ljust(20) in res
    assert "ctrl1_val".ljust(20) + "100.000".ljust(20) in res
    assert "ctrl1_val_unit".ljust(20) + "mA".ljust(20) in res

    # I range (>1 A) not supported
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_mA=501, start_frequency_Hz=1, end_frequency_Hz=100)
        ],
    )
    with pytest.raises(ValueError) as excinfo:
        protocol.to_biologic_mps(sample_name="test")
    assert "I range not supported" in str(excinfo.value)


def test_impedance_voltage_units() -> None:
    """Check if impedance voltages set correct units."""
    # 0.5 mV, gives values in uV
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_V=5e-4, start_frequency_Hz=1, end_frequency_Hz=100)
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "ctrl1_val".ljust(20) + "500.000".ljust(20) in res
    assert "ctrl1_val_unit".ljust(20) + "uV".ljust(20) in res

    # 5 mV, gives values in mV
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_V=5e-3, start_frequency_Hz=1, end_frequency_Hz=100)
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "ctrl1_val".ljust(20) + "5.000".ljust(20) in res
    assert "ctrl1_val_unit".ljust(20) + "mV".ljust(20) in res

    # 999.999 mV, gives values in mV
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_V=0.999999, start_frequency_Hz=1, end_frequency_Hz=100)
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "ctrl1_val".ljust(20) + "999.999".ljust(20) in res
    assert "ctrl1_val_unit".ljust(20) + "mV".ljust(20) in res

    # 1 V, gives values in V
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[ImpedanceSpectroscopy(amplitude_V=1, start_frequency_Hz=1, end_frequency_Hz=100)],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "ctrl1_val".ljust(20) + "1.000".ljust(20) in res
    assert "ctrl1_val_unit".ljust(20) + "V".ljust(20) in res


def test_impedance_frequency_units() -> None:
    """Check if impedance voltages set correct units."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_V=1e-3, start_frequency_Hz=1e-3, end_frequency_Hz=1)
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "ctrl2_val".ljust(20) + "1.000".ljust(20) in res
    assert "ctrl2_val_unit".ljust(20) + "mHz".ljust(20) in res
    assert "ctrl3_val".ljust(20) + "1.000".ljust(20) in res
    assert "ctrl3_val_unit".ljust(20) + "Hz".ljust(20) in res

    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            ImpedanceSpectroscopy(amplitude_V=1e-3, start_frequency_Hz=1e3, end_frequency_Hz=1e5)
        ],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "ctrl2_val".ljust(20) + "1.000".ljust(20) in res
    assert "ctrl2_val_unit".ljust(20) + "kHz".ljust(20) in res
    assert "ctrl3_val".ljust(20) + "100.000".ljust(20) in res
    assert "ctrl3_val_unit".ljust(20) + "kHz".ljust(20) in res


def test_save_file(tmpdir: Path) -> None:
    """Check file is written correctly."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        method=[
            Tag(tag="a"),
            ConstantCurrent(current_mA=0.01, until_voltage_V=4),
            ConstantVoltage(voltage_V=4, until_time_s=1),
            ConstantCurrent(current_mA=0.01, until_voltage_V=3),
            Loop(loop_to="a", cycle_count=100),
        ],
    )
    filepath = Path(tmpdir / "test.mps")
    res = protocol.to_biologic_mps(sample_name="test", save_path=filepath)
    assert filepath.exists()
    # Reading with utf-8 should fail
    with (tmpdir / "test.mps").open("r", encoding="utf-8") as f, pytest.raises(UnicodeDecodeError):
        text = f.read()
    # Reading with cp1252 should work
    with (tmpdir / "test.mps").open("r", encoding="cp1252") as f:
        text = f.read()
    assert res == text


def test_unknown_step() -> None:
    """If unsupported steps are in protocol, raise error."""

    class UnknownStep(Step):
        step: str = "wait, what"

    protocol = Protocol.model_construct(
        record=RecordParams(time_s=1),
        method=[UnknownStep()],
    )
    with pytest.raises(NotImplementedError) as excinfo:
        protocol.to_biologic_mps(sample_name="test")
    assert "to_biologic_mps() does not support step type: wait, what" in str(excinfo.value)


def test_safety_limits(caplog: pytest.LogCaptureFixture) -> None:
    """Check that safety limits are applied."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(
            max_voltage_V=1,
            min_voltage_V=0,
        ),
        method=[OpenCircuitVoltage(until_time_s=1000)],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "Safety Limits :" in res
    assert "\tEwe min = 0.00000 V" in res
    assert "\tEwe max = 1.00000 V" in res
    assert "\tfor t > 0 ms" in res

    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(
            max_voltage_V=4,
            min_voltage_V=-3,
            delay_s=0.123,
        ),
        method=[OpenCircuitVoltage(until_time_s=1000)],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "Safety Limits :" in res
    assert "\tEwe min = -3.00000 V" in res
    assert "\tEwe max = 4.00000 V" in res
    assert "\tfor t > 123.0 ms" in res

    # Adding currents - should not warn if symmetric
    caplog.clear()
    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(
            max_voltage_V=4,
            min_voltage_V=-3,
            min_current_mA=-3,
            max_current_mA=3,
            delay_s=0.123,
        ),
        method=[OpenCircuitVoltage(until_time_s=1000)],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "Safety Limits :" in res
    assert "\tEwe min = -3.00000 V" in res
    assert "\tEwe max = 4.00000 V" in res
    assert "\t|I| = 3.00000 mA" in res
    assert "\tfor t > 123.0 ms" in res
    assert not caplog.text

    # Assymetric currents - should warn and use biggest
    caplog.clear()
    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(
            max_voltage_V=4,
            min_voltage_V=-3,
            min_current_mA=-1,
            max_current_mA=3,
            delay_s=0.123,
        ),
        method=[OpenCircuitVoltage(until_time_s=1000)],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "Safety Limits :" in res
    assert "\tEwe min = -3.00000 V" in res
    assert "\tEwe max = 4.00000 V" in res
    assert "\t|I| = 3.00000 mA" in res
    assert "\tfor t > 123.0 ms" in res
    assert "Using 3.0 mA as the absolute limit." in caplog.text

    # Assymetric currents - should warn and use biggest
    caplog.clear()
    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(
            max_voltage_V=4,
            min_voltage_V=-3,
            max_current_mA=2.5,
            delay_s=0.123,
        ),
        method=[OpenCircuitVoltage(until_time_s=1000)],
    )
    res = protocol.to_biologic_mps(sample_name="test")
    assert "Safety Limits :" in res
    assert "\tEwe min = -3.00000 V" in res
    assert "\tEwe max = 4.00000 V" in res
    assert "\t|I| = 2.50000 mA" in res
    assert "\tfor t > 123.0 ms" in res
    assert "Using 2.5 mA as the absolute limit." in caplog.text
