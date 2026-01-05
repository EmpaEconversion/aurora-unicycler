"""Extension for tomato automation."""

import json
from pathlib import Path

from aurora_unicycler import _core, _utils


def to_tomato_mpg2(  # noqa: D417
    protocol: _core.BaseProtocol,
    save_path: Path | str | None = None,
    tomato_output: Path = Path("C:/tomato_data/"),
    sample_name: str | None = None,
    capacity_mAh: float | None = None,
) -> str:
    """Convert protocol to tomato 0.2.3 + MPG2 compatible JSON format.

    Args:
        save_path: (optional) File path of where to save the json file.
        tomato_output: (optional) Where to save the data from tomato.
        sample_name: (optional) Override the protocol sample name.
        capacity_mAh: (optional) Override the protocol sample capacity.

    Returns:
        json string representation of the protocol.

    """
    # Create and operate on a copy of the original object
    protocol = protocol.model_copy(deep=True)

    # Allow overwriting name and capacity
    if sample_name:
        protocol.sample.name = sample_name
    if capacity_mAh:
        protocol.sample.capacity_mAh = capacity_mAh

    # Make sure sample name is set
    if not protocol.sample.name or protocol.sample.name == "$NAME":
        msg = (
            "If using blank sample name or $NAME placeholder, "
            "a sample name must be provided in this function."
        )
        raise ValueError(msg)

    # Make sure capacity is set if using C-rate steps
    _utils.validate_capacity_c_rates(protocol)

    # Remove tags and convert to indices
    _utils.tag_to_indices(protocol)
    _utils.check_for_intersecting_loops(protocol)

    # Create JSON structure
    tomato_dict: dict = {
        "version": "0.1",
        "sample": {},
        "method": [],
        "tomato": {
            "unlock_when_done": True,
            "verbosity": "DEBUG",
            "output": {
                "path": str(tomato_output),
                "prefix": protocol.sample.name,
            },
        },
    }
    # tomato -> MPG2 does not support safety parameters, they are set in the instrument
    tomato_dict["sample"]["name"] = protocol.sample.name
    tomato_dict["sample"]["capacity_mAh"] = protocol.sample.capacity_mAh
    for step in protocol.method:
        tomato_step: dict = {}
        tomato_step["device"] = "MPG2"
        tomato_step["technique"] = step.step
        if isinstance(
            step, (_core.ConstantCurrent, _core.ConstantVoltage, _core.OpenCircuitVoltage)
        ):
            if protocol.record.time_s:
                tomato_step["measure_every_dt"] = protocol.record.time_s
            if protocol.record.current_mA:
                tomato_step["measure_every_dI"] = protocol.record.current_mA
            if protocol.record.voltage_V:
                tomato_step["measure_every_dE"] = protocol.record.voltage_V
            tomato_step["I_range"] = "10 mA"
            tomato_step["E_range"] = "+-5.0 V"

        match step:
            case _core.OpenCircuitVoltage():
                tomato_step["time"] = step.until_time_s

            case _core.ConstantCurrent():
                if step.rate_C:
                    if step.rate_C > 0:
                        charging = True
                        tomato_step["current"] = str(step.rate_C) + "C"
                    else:
                        charging = False
                        tomato_step["current"] = str(abs(step.rate_C)) + "D"
                elif step.current_mA:
                    if step.current_mA > 0:
                        charging = True
                        tomato_step["current"] = step.current_mA / 1000
                    else:
                        charging = False
                        tomato_step["current"] = step.current_mA / 1000
                else:
                    msg = "Must have a current or C-rate"
                    raise ValueError(msg)
                if step.until_time_s:
                    tomato_step["time"] = step.until_time_s
                if step.until_voltage_V:
                    if charging:
                        tomato_step["limit_voltage_max"] = step.until_voltage_V
                    else:
                        tomato_step["limit_voltage_min"] = step.until_voltage_V

            case _core.ConstantVoltage():
                tomato_step["voltage"] = step.voltage_V
                if step.until_time_s:
                    tomato_step["time"] = step.until_time_s
                if step.until_rate_C:
                    if step.until_rate_C > 0:
                        tomato_step["limit_current_min"] = str(step.until_rate_C) + "C"
                    else:
                        tomato_step["limit_current_max"] = str(abs(step.until_rate_C)) + "D"

            case _core.Loop():
                assert isinstance(step.loop_to, int)  # noqa: S101, from _tag_to_indices()
                tomato_step["goto"] = step.loop_to - 1  # 0-indexed in mpr
                tomato_step["n_gotos"] = step.cycle_count - 1  # gotos is one less than cycles

            case _:
                msg = f"to_tomato_mpg2 does not support step type: {step.step}"
                raise TypeError(msg)

        tomato_dict["method"].append(tomato_step)

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open("w", encoding="utf-8") as f:
            json.dump(tomato_dict, f, indent=4)
    return json.dumps(tomato_dict, indent=4)
