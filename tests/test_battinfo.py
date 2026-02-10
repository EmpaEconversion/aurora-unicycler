"""Tests for BattINFO jsonld conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    Loop,
    OpenCircuitVoltage,
    Protocol,
    RecordParams,
    SampleParams,
    Step,
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
            ConstantCurrent(rate_C=0.5, until_voltage_V=4.2, until_time_s=3 * 60 * 60),
            ConstantVoltage(voltage_V=4.2, until_rate_C=0.05, until_time_s=1 * 60 * 60),
            ConstantCurrent(rate_C=-0.5, until_voltage_V=3.2, until_time_s=3 * 60 * 60),
            Loop(loop_to="longterm", cycle_count=24),
            ConstantCurrent(current_mA=0.1, until_voltage_V=4.2),
            ConstantVoltage(voltage_V=4.2, until_current_mA=0.01),
            ConstantCurrent(current_mA=-0.1, until_voltage_V=3.2),
            Loop(loop_to="recovery", cycle_count=10),
        ],
    )
    bij = my_protocol.to_battinfo_jsonld(include_context=True)
    assert isinstance(bij, dict)
    json.dumps(bij)  # should be valid JSON

    # Check that every key is valid term from emmo
    context = []
    for key, file in test_data["context_paths"].items():
        with file.open("r") as f:
            term_list = json.load(f)
            context += [key + c.split(".")[-1] for c in term_list]
    context += ["@type", "@id", "@context"]
    context = set(context)

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
                if k == "@type":
                    if isinstance(v, str) and v not in context:
                        msg = f"Unknown @type: {v}"
                        raise ValueError(msg)
                    if isinstance(v, list):
                        for el in v:
                            if el not in context:
                                msg = f"Unknown @type: {el}"
                                raise ValueError(msg)
                if k != "@context":
                    recursive_search(v, context)

    recursive_search(bij, context)

    # This is only a regression test, does not check for correctness
    with test_data["jsonld_path"].open("r") as f:
        expected = json.load(f)
    assert bij == expected

    # Check if capacity overriding works
    bij = my_protocol.to_battinfo_jsonld(capacity_mAh=200)
    assert bij["hasNext"]["hasTask"]["hasInput"][0]["hasNumericalPart"]["hasNumberValue"] == 10

    # But doesn't affect original capacity
    assert my_protocol.sample.capacity_mAh == 45

    # Overwriting capacity directly is also allowed
    my_protocol.sample.capacity_mAh = 100
    bij = my_protocol.to_battinfo_jsonld()
    assert bij["hasNext"]["hasTask"]["hasInput"][0]["hasNumericalPart"]["hasNumberValue"] == 5

    # Check if adding context works
    bij = my_protocol.to_battinfo_jsonld(include_context=True)
    assert bij["@context"] == [
        "https://w3id.org/emmo/domain/battery/context",
        {
            "emmo": "https://w3id.org/emmo#",
            "echem": "https://w3id.org/emmo/domain/electrochemistry#",
        },
    ]


def test_unknown_step() -> None:
    """If unsupported steps are in protocol, raise error."""

    class UnknownStep(Step):
        step: str = "wait, what"

    protocol = Protocol.model_construct(
        record=RecordParams(time_s=1),
        method=[UnknownStep()],
    )
    with pytest.raises(NotImplementedError) as excinfo:
        protocol.to_battinfo_jsonld()
    assert "to_battinfo_jsonld() does not support step type: wait, what" in str(excinfo.value)


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
    filepath = Path(tmpdir / "test.jsonld")
    res = protocol.to_battinfo_jsonld(save_path=filepath)
    assert filepath.exists()
    with (tmpdir / "test.jsonld").open("r") as f:
        file_res = json.loads(f.read())
    assert res == file_res
