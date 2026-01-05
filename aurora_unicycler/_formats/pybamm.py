"""Extension for PyBaMM experiment."""

from aurora_unicycler import _core, _utils


def to_pybamm_experiment(protocol: _core.BaseProtocol) -> list[str]:
    """Convert protocol to PyBaMM experiment format."""
    # Don't need to validate capacity if using C-rate steps
    # Create and operate on a copy of the original object
    protocol = protocol.model_copy(deep=True)

    # Remove tags and convert to indices
    _utils.tag_to_indices(protocol)
    _utils.check_for_intersecting_loops(protocol)

    pybamm_experiment: list[str] = []
    loops: dict[int, dict] = {}
    for i, step in enumerate(protocol.method):
        step_str = ""
        match step:
            case _core.ConstantCurrent():
                if step.rate_C:
                    if step.rate_C > 0:
                        step_str += f"Charge at {step.rate_C}C"
                    else:
                        step_str += f"Discharge at {abs(step.rate_C)}C"
                elif step.current_mA:
                    if step.current_mA > 0:
                        step_str += f"Charge at {step.current_mA} mA"
                    else:
                        step_str += f"Discharge at {abs(step.current_mA)} mA"
                if step.until_time_s:
                    if step.until_time_s % 3600 == 0:
                        step_str += f" for {int(step.until_time_s / 3600)} hours"
                    elif step.until_time_s % 60 == 0:
                        step_str += f" for {int(step.until_time_s / 60)} minutes"
                    else:
                        step_str += f" for {step.until_time_s} seconds"
                if step.until_voltage_V:
                    step_str += f" until {step.until_voltage_V} V"

            case _core.ConstantVoltage():
                step_str += f"Hold at {step.voltage_V} V"
                conditions = []
                if step.until_time_s:
                    if step.until_time_s % 3600 == 0:
                        step_str += f" for {int(step.until_time_s / 3600)} hours"
                    elif step.until_time_s % 60 == 0:
                        step_str += f" for {int(step.until_time_s / 60)} minutes"
                    else:
                        conditions.append(f"for {step.until_time_s} seconds")
                if step.until_rate_C:
                    conditions.append(f"until {step.until_rate_C}C")
                if step.until_current_mA:
                    conditions.append(f" until {step.until_current_mA} mA")
                if conditions:
                    step_str += " " + " or ".join(conditions)

            case _core.OpenCircuitVoltage():
                step_str += f"Rest for {step.until_time_s} seconds"

            case _core.Loop():
                # The string from this will get dropped later
                assert isinstance(step.loop_to, int)  # noqa: S101, from _tag_to_indices()
                loops[i] = {"goto": step.loop_to - 1, "n": step.cycle_count, "n_done": 0}

            case _:
                msg = f"to_pybamm_experiment does not support step type: {step.step}"
                raise TypeError(msg)

        pybamm_experiment.append(step_str)

    exploded_steps = []
    i = 0
    total_itr = 0
    while i < len(pybamm_experiment):
        exploded_steps.append(i)
        if i in loops and loops[i]["n_done"] < loops[i]["n"]:
            # check if it passes over a different loop, if so reset its count
            for j in loops:  # noqa: PLC0206
                if j < i and j >= loops[i]["goto"]:
                    loops[j]["n_done"] = 0
            loops[i]["n_done"] += 1
            i = loops[i]["goto"]
        else:
            i += 1
        total_itr += 1
        if total_itr > 10000:
            msg = (
                "Over 10000 steps in protocol to_pybamm_experiment(), "
                "likely a loop definition error."
            )
            raise RuntimeError(msg)

    # remove all loop steps from the list
    cleaned_exploded_steps = [i for i in exploded_steps if i not in loops]
    # change from list of indices to list of strings
    return [pybamm_experiment[i] for i in cleaned_exploded_steps]
