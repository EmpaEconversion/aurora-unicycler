"""Tests for BattINFO jsonld conversion."""

from __future__ import annotations

import json

from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    Loop,
    OpenCircuitVoltage,
    Protocol,
    RecordParams,
    SampleParams,
    Tag,
)


def test_to_battinfo_jsonld(test_data: dict) -> None:
    """Test converting to BattINFO JSON-LD."""
    my_protocol = Protocol(
        sample=SampleParams(
            name="test_sample",
            capacity_mAh=45,
        ),
        record=RecordParams(time_s=1),
        method=[
            OpenCircuitVoltage(until_time_s=300),
            ConstantCurrent(rate_C=0.05, until_voltage_V=4.2),
            ConstantVoltage(voltage_V=4.2, until_rate_C=0.01),
            ConstantCurrent(rate_C=-0.05, until_voltage_V=3.2),
            Loop(loop_to=2, cycle_count=5),
            Tag(tag="longterm"),
            Tag(tag="recovery"),
            ConstantCurrent(rate_C=0.5, until_voltage_V=4.2),
            ConstantVoltage(voltage_V=4.2, until_rate_C=0.05),
            ConstantCurrent(rate_C=-0.5, until_voltage_V=3.2),
            Loop(loop_to="longterm", cycle_count=24),
            ConstantCurrent(rate_C=0.1, until_voltage_V=4.2),
            ConstantVoltage(voltage_V=4.2, until_rate_C=0.01),
            ConstantCurrent(rate_C=-0.1, until_voltage_V=3.2),
            Loop(loop_to="recovery", cycle_count=10),
        ],
    )
    bij = my_protocol.to_battinfo_jsonld()
    assert isinstance(bij, dict)
    json.dumps(bij)  # should be valid JSON

    # Check that every key is valid term from emmo
    with test_data["emmo_context_path"].open("r") as f:
        emmo_context = set(json.load(f))
    emmo_context.add("@type")

    def recursive_search(obj: dict | list | str | float, context: set) -> None:
        if isinstance(obj, (int, float)):
            return
        if isinstance(obj, str) and obj not in context:
            msg = f"Unknown key: {obj}"
            raise ValueError(msg)
        if isinstance(obj, list):
            for item in obj:
                recursive_search(item, context)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k not in context:
                    msg = f"Unknown key: {k}"
                    raise ValueError(msg)
                recursive_search(v, context)

    recursive_search(bij, emmo_context)

    # This is only a regression test, does not check for correctness
    with test_data["jsonld_path"].open("r") as f:
        expected = json.load(f)
    assert bij == expected

    # Check if capacity overriding works
    my_protocol.sample.capacity_mAh = 100
    bij = my_protocol.to_battinfo_jsonld()
    assert bij["hasNext"]["hasTask"]["hasInput"][0]["hasNumericalPart"]["hasNumberValue"] == 5

    # Check if adding context works
    bij = my_protocol.to_battinfo_jsonld(include_context=True)
    assert bij["@context"] == ["https://w3id.org/emmo/domain/battery/context"]
