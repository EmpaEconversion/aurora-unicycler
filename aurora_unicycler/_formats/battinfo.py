"""Extension for BattINFO ontology."""

import json
from collections.abc import Sequence
from pathlib import Path

from aurora_unicycler import _core, _utils


def _group_iterative_tasks(
    step_numbers: list[int], method: Sequence[_core.AnyTechnique]
) -> list[int | tuple[int, list]]:
    """Take a list of techniques, find the iterative loops.

    Returns a list containing ints (a task) or a tuple of an int and
    list (an iterative workflow).

    E.g. [0,1,2,(1000, [4,5,6])]
    Means do tasks 0, 1, 2, then loop over 4, 5, 6 1000 times.
    """
    # Either this is surprisingly complex, or I am just stupid
    # Assume there are no intersecting loops and tags are removed
    # Must iterate BACKWARDS over techniques and treat loops recursively

    tasks: list[int | tuple[int, list]] = []
    skip_above: int | None = None

    list_indices = list(range(len(method)))

    for i, step_number in zip(reversed(list_indices), reversed(step_numbers), strict=True):
        # If the techniques are already included in a loop at a higher depth, skip
        if skip_above and step_numbers[i] >= skip_above:
            continue

        # If the technique is a loop, the whole loop goes inside a tuple
        if isinstance(method[i], _core.Loop):
            loop_object = method[i]
            assert isinstance(loop_object, _core.Loop)  # noqa: S101
            assert isinstance(loop_object.loop_to, int)  # noqa: S101
            cycle_count = loop_object.cycle_count
            start_step: int = loop_object.loop_to - 1  # because loop_to is 1-indexed

            # Find the subsection that the loop belongs to
            start_i = next(j for j, n in enumerate(step_numbers) if n == start_step)
            end_i = i

            # Add this element, recursively run this function on the loops subsection
            tasks.append(
                (
                    cycle_count,
                    _group_iterative_tasks(step_numbers[start_i:end_i], method[start_i:end_i]),
                ),
            )

            # Skip the rest of the loop at this depth
            skip_above = start_step
        else:
            # Just add the technique
            tasks.append(step_number)
    return tasks[::-1]


def _battinfoify_technique(step: _core.AnyTechnique, capacity_mAh: float | None) -> dict:
    """Create a single BattINFO dict from a technique."""
    match step:
        case _core.OpenCircuitVoltage():
            tech_dict = {
                "@type": "Resting",
                "hasInput": [
                    {
                        "@type": "Duration",
                        "hasNumericalPart": {
                            "@type": "RealData",
                            "hasNumberValue": step.until_time_s,
                        },
                        "hasMeasurementUnit": "Second",
                    }
                ],
            }
        case _core.ConstantCurrent():
            inputs = []
            current_mA: float | None = None
            if step.rate_C and capacity_mAh:
                current_mA = step.rate_C * capacity_mAh
            elif step.current_mA:
                current_mA = step.current_mA
            charging = (current_mA and current_mA > 0) or (step.rate_C and step.rate_C > 0)
            if current_mA:
                inputs.append(
                    {
                        "@type": "ElectricCurrent",
                        "hasNumericalPart": {
                            "@type": "RealData",
                            "hasNumberValue": abs(current_mA),
                        },
                        "hasMeasurementUnit": "MilliAmpere",
                    },
                )
            if step.rate_C:
                inputs.append(
                    {
                        "@type": "CRate",
                        "hasNumericalPart": {
                            "@type": "RealData",
                            "hasNumberValue": abs(step.rate_C),
                        },
                        "hasMeasurementUnit": "CRateUnit",
                    },
                )
            if step.until_voltage_V:
                inputs.append(
                    {
                        "@type": [
                            "UpperVoltageLimit" if charging else "LowerVoltageLimit",
                            "TerminationQuantity",
                        ],
                        "hasNumericalPart": {
                            "@type": "RealData",
                            "hasNumberValue": step.until_voltage_V,
                        },
                        "hasMeasurementUnit": "Volt",
                    }
                )
            if step.until_time_s:
                inputs.append(
                    {
                        "@type": "Duration",
                        "hasNumericalPart": {
                            "@type": "RealData",
                            "hasNumberValue": step.until_time_s,
                        },
                        "hasMeasurementUnit": "Second",
                    }
                )
            tech_dict = {
                "@type": "Charging" if charging else "Discharging",
                "hasInput": inputs,
            }
        case _core.ConstantVoltage():
            inputs = [
                {
                    "@type": "Voltage",
                    "hasNumericalPart": {
                        "@type": "RealData",
                        "hasNumberValue": step.voltage_V,
                    },
                    "hasMeasurementUnit": "Volt",
                }
            ]
            until_current_mA: None | float = None
            if step.until_rate_C and capacity_mAh:
                until_current_mA = step.until_rate_C * capacity_mAh
            elif step.until_current_mA:
                until_current_mA = step.until_current_mA
            if until_current_mA is not None:
                inputs.append(
                    {
                        "@type": ["LowerCurrentLimit", "TerminationQuantity"],
                        "hasNumericalPart": {
                            "@type": "RealData",
                            "hasNumberValue": abs(until_current_mA),
                        },
                        "hasMeasurementUnit": "MilliAmpere",
                    }
                )
            if step.until_rate_C:
                inputs.append(
                    {
                        "@type": ["LowerCRateLimit", "TerminationQuantity"],
                        "hasNumericalPart": {
                            "@type": "RealData",
                            "hasNumberValue": abs(step.until_rate_C),
                        },
                        "hasMeasurementUnit": "CRateUnit",
                    },
                )
            if step.until_time_s:
                inputs.append(
                    {
                        "@type": "Duration",
                        "hasNumericalPart": {
                            "@type": "RealData",
                            "hasNumberValue": step.until_time_s,
                        },
                        "hasMeasurementUnit": "Second",
                    }
                )
            tech_dict = {
                "@type": "Hold",
                "hasInput": inputs,
            }
        case _:
            msg = f"Technique {step.step} not supported by to_battinfo_jsonld()"
            raise NotImplementedError(msg)
    return tech_dict


def _recursive_battinfo_build(
    order: list[int | tuple[int, list]],
    methods: Sequence[_core.AnyTechnique],
    capacity_mAh: float | None,
) -> dict:
    """Recursively build the a BattINFO JSON-LD from a method."""
    if isinstance(order[0], int):
        # It is just a normal techqniue
        this_tech = _battinfoify_technique(methods[order[0]], capacity_mAh)
    else:
        # It is an iterative workflow
        assert isinstance(order[0], tuple)  # noqa: S101
        this_tech = {
            "@type": "IterativeWorkflow",
            "hasInput": [
                {
                    "@type": "NumberOfIterations",
                    "hasNumericalPart": {
                        "@type": "RealData",
                        "hasNumberValue": order[0][0],
                    },
                    "hasMeasurementUnit": "UnitOne",
                }
            ],
            "hasTask": _recursive_battinfo_build(order[0][1], methods, capacity_mAh),
        }

    # If there is another technique, keep going
    if len(order) > 1:
        this_tech["hasNext"] = _recursive_battinfo_build(order[1:], methods, capacity_mAh)
    return this_tech


def to_battinfo_jsonld(  # noqa: D417
    protocol: _core.BaseProtocol,
    save_path: Path | str | None = None,
    capacity_mAh: float | None = None,
    *,
    include_context: bool = False,
) -> dict:
    """Convert protocol to BattInfo JSON-LD format."""
    # Create and operate on a copy of the original object
    protocol = protocol.model_copy(deep=True)

    # Allow overwriting capacity
    if capacity_mAh:
        protocol.sample.capacity_mAh = capacity_mAh

    # Make sure there are no tags or interecting loops
    _utils.tag_to_indices(protocol)
    _utils.check_for_intersecting_loops(protocol)

    # Get the order of techniques with nested loops
    battinfo_order = _group_iterative_tasks(list(range(len(protocol.method))), protocol.method)

    # Build the battinfo JSON-LD
    battinfo_dict = _recursive_battinfo_build(
        battinfo_order, protocol.method, protocol.sample.capacity_mAh
    )

    # Include context at this level, if requested
    if include_context:
        battinfo_dict["@context"] = [
            "https://w3id.org/emmo/domain/battery/context",
        ]

    # Optionally save
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open("w", encoding="utf-8") as f:
            json.dump(battinfo_dict, f, indent=4)

    return battinfo_dict
