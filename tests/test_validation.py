"""Tests for validation functions used in unicycler."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    Loop,
    OpenCircuitVoltage,
    Protocol,
    RecordParams,
    SafetyParams,
    Tag,
)
from aurora_unicycler._core import _coerce_c_rate
from aurora_unicycler._utils import check_for_intersecting_loops, tag_to_indices


def test_constant_current_validation(test_data: dict) -> None:
    """Test validation of ConstantCurrent technique."""
    with pytest.raises(ValueError):
        # Missing rate_C and current_mA
        ConstantCurrent()
    with pytest.raises(ValueError):
        # rate_C and current_mA are zero
        ConstantCurrent(rate_C=0, current_mA=0)
    with pytest.raises(ValueError):
        # Missing stop condition
        ConstantCurrent(rate_C=0.1)
    with pytest.raises(ValueError):
        # stop conditions are zero
        ConstantCurrent(rate_C=0.1, until_time_s=0, until_voltage_V=0)
    cc = ConstantCurrent(rate_C=0.1, until_voltage_V=4.2)
    assert isinstance(cc, ConstantCurrent)


def test_constant_voltage_validation(test_data: dict) -> None:
    """Test validation of ConstantVoltage technique."""
    with pytest.raises(ValueError):
        # Missing stop condition
        ConstantVoltage(voltage_V=4.2)
    with pytest.raises(ValueError):
        # stop conditions are zero
        ConstantVoltage(
            voltage_V=4.2,
            until_time_s=0,
            until_rate_C=0,
            until_current_mA=0,
        )
    cv = ConstantVoltage(voltage_V=4.2, until_rate_C=0.05)
    assert isinstance(cv, ConstantVoltage)


def test_protocol_c_rate_validation(test_data: dict) -> None:
    """Test validation of Protocol with C-rate steps."""
    # Valid protocol
    protocol = Protocol.from_dict(test_data["protocol_dicts"][0])
    assert isinstance(protocol, Protocol)

    # Invalid protocol (missing capacity)
    protocol.sample.capacity_mAh = Decimal(0)
    with pytest.raises(ValueError) as context:
        protocol.to_neware_xml()
    assert str(context.value) == "Sample capacity must be set if using C-rate steps."


def test_loop_validation(test_data: dict) -> None:
    """Test validation of Loop technique."""
    with pytest.raises(ValueError):
        Loop(loop_to=0, cycle_count=1)  # loop_to is zero
    with pytest.raises(ValueError):
        Loop(loop_to=1, cycle_count=0)  # cycle_count is zero
    loop = Loop(loop_to=1, cycle_count=1)
    assert isinstance(loop, Loop)


def test_coerce_c_rate(test_data: dict) -> None:
    """Test the coerce_c_rate function."""
    assert _coerce_c_rate("0.05") == 0.05
    assert _coerce_c_rate("  0.05  ") == 0.05
    assert _coerce_c_rate("1/20") == 0.05
    assert _coerce_c_rate("C/5") == 0.2
    assert _coerce_c_rate("D/5") == -0.2
    assert _coerce_c_rate("3D/3") == -1.0
    assert _coerce_c_rate("C5/25") == 0.2
    assert _coerce_c_rate("2e-1") == 0.2
    assert _coerce_c_rate("1.23e3 C / 1.23e4") == 0.1
    assert _coerce_c_rate(" C 3   /    1 0 ") == 0.3
    assert _coerce_c_rate(0.1) == 0.1
    assert _coerce_c_rate(1) == 1.0
    assert _coerce_c_rate(Decimal("0.1")) == 0.1
    with pytest.raises(ValueError):
        _coerce_c_rate("invalid")
    with pytest.raises(ValueError):
        _coerce_c_rate("1/2/3")
    with pytest.raises(ValueError):
        _coerce_c_rate("1\5")
    with pytest.raises(ValueError):
        _coerce_c_rate(" 1 . 0 ")
    with pytest.raises(ValueError):
        _coerce_c_rate("5C/2D")
    with pytest.raises(ValueError):
        _coerce_c_rate("3C/2C")
    with pytest.raises(ZeroDivisionError):
        _coerce_c_rate("C/0")


def test_intersecting_loops(test_data: dict) -> None:
    """Protocols with intersecting loops should give a error."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag1"),
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag2"),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag2", cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag1", cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag3"),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag3", cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag1", cycle_count=3),
        ],
    )
    tag_to_indices(protocol)
    check_for_intersecting_loops(protocol)  # Should be fine

    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=2, cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=1, cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=7, cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=1, cycle_count=3),
        ],
    )
    tag_to_indices(protocol)
    check_for_intersecting_loops(protocol)  # Should be fine

    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag1"),
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag2"),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag1", cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag2", cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag3"),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag3", cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag1", cycle_count=3),
        ],
    )
    tag_to_indices(protocol)
    with pytest.raises(ValueError):  # Should fail
        check_for_intersecting_loops(protocol)

    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=2, cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=1, cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=5, cycle_count=3),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to=1, cycle_count=3),
        ],
    )
    tag_to_indices(protocol)
    with pytest.raises(ValueError):  # Should fail
        check_for_intersecting_loops(protocol)


def test_nonexistent_tag(test_data) -> None:
    """You should not be able to create a loop with a tag that does not exist."""
    with pytest.raises(ValidationError):
        Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="this tag does not exist", cycle_count=3),
            ],
        )


def test_forward_loop(test_data) -> None:
    """Loops are not allowed to go fowards, or land on themselves, or only go back one step."""
    with pytest.raises(ValidationError):
        Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag1", cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Tag(tag="tag1"),
            ],
        )

    # Loops cannot go forwards or land on themselves
    for i in [4, 5]:
        with pytest.raises(ValidationError):
            Protocol(
                record=RecordParams(time_s=1),
                safety=SafetyParams(),
                method=[
                    OpenCircuitVoltage(until_time_s=1),
                    OpenCircuitVoltage(until_time_s=1),
                    OpenCircuitVoltage(until_time_s=1),
                    Loop(loop_to=i, cycle_count=3),
                    OpenCircuitVoltage(until_time_s=1),
                    OpenCircuitVoltage(until_time_s=1),
                    OpenCircuitVoltage(until_time_s=1),
                ],
            )

    # Loops cannot go back to one index to a tag
    with pytest.raises(ValidationError):
        Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),
                Tag(tag="tag1"),
                Loop(loop_to="tag1", cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
            ],
        )
