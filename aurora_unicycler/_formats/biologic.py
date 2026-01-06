"""Extension for Biologic mps settings."""

import logging
from pathlib import Path

from aurora_unicycler import _core, _utils

logger = logging.getLogger(__name__)


def to_biologic_mps(
    protocol: _core.BaseProtocol,
    save_path: Path | str | None = None,
    sample_name: str | None = None,
    capacity_mAh: float | None = None,
    range_V: tuple[float, float] = (0.0, 5.0),
) -> str:
    """Convert protocol to a Biologic Settings file (.mps)."""
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

    safety = ["Safety Limits :"]
    if protocol.safety.min_voltage_V:
        safety += [f"\tEwe min = {protocol.safety.min_voltage_V:.5f} V"]
    if protocol.safety.max_voltage_V:
        safety += [f"\tEwe max = {protocol.safety.max_voltage_V:.5f} V"]
    if protocol.safety.max_current_mA and protocol.safety.min_current_mA:
        max_abs_current_mA = max(
            [abs(protocol.safety.max_current_mA), abs(protocol.safety.min_current_mA)]
        )
        safety += [f"\t|I| = {max_abs_current_mA:.5f} mA"]
    delay_ms = (protocol.safety.delay_s or 0) * 1000
    if delay_ms > 1000:
        logger.warning(
            "Biologic max safety delay is 1000 ms, your value of %d ms will be capped",
            int(delay_ms),
        )
    safety += [f"\tfor t > {delay_ms} ms", "\tDo not start on E overload"]

    low_range_V, high_range_V = sorted(range_V)
    if any(abs(V) > 10 for V in range_V):
        logger.warning(
            "Biologic max voltage range is usually +-10 V, your range %d-%d V may be capped",
            *range_V,
        )
    for step in protocol.method:
        if (
            isinstance(step, _core.ConstantCurrent)
            and step.until_voltage_V
            and (step.until_voltage_V > high_range_V or step.until_voltage_V < low_range_V)
        ) or (
            isinstance(step, _core.ConstantVoltage)
            and step.voltage_V
            and (step.voltage_V > high_range_V or step.voltage_V < low_range_V)
        ):
            msg = f"Method contains step with voltage outside of range ({range_V} V)"
            raise ValueError(msg)

    header = [
        "EC-LAB SETTING FILE",
        "",
        "Number of linked techniques : 1",
        "Device : MPG-2",
        "CE vs. WE compliance from -10 V to 10 V",
        "Electrode connection : standard",
        "Potential control : Ewe",
        f"Ewe ctrl range : min = {low_range_V:.2f} V, max = {high_range_V:.2f} V",
        *safety,
        f"Comments : {protocol.sample.name}",
        "Cycle Definition : Charge/Discharge alternance",
        "Do not turn to OCV between techniques",
        "",
        "Technique : 1",
        "Modulo Bat",
    ]

    default_step = {
        "Ns": "",
        "ctrl_type": "",
        "Apply I/C": "I",
        "current/potential": "current",
        "ctrl1_val": "",
        "ctrl1_val_unit": "",
        "ctrl1_val_vs": "",
        "ctrl2_val": "",
        "ctrl2_val_unit": "",
        "ctrl2_val_vs": "",
        "ctrl3_val": "",
        "ctrl3_val_unit": "",
        "ctrl3_val_vs": "",
        "N": "0.00",
        "charge/discharge": "Charge",
        "charge/discharge_1": "Charge",
        "Apply I/C_1": "I",
        "N1": "0.00",
        "ctrl4_val": "",
        "ctrl4_val_unit": "",
        "ctrl5_val": "",
        "ctrl5_val_unit": "",
        "ctrl_tM": "0",
        "ctrl_seq": "0",
        "ctrl_repeat": "0",
        "ctrl_trigger": "Falling Edge",
        "ctrl_TO_t": "0.000",
        "ctrl_TO_t_unit": "d",
        "ctrl_Nd": "6",
        "ctrl_Na": "2",
        "ctrl_corr": "0",
        "lim_nb": "0",
        "lim1_type": "Time",
        "lim1_comp": ">",
        "lim1_Q": "",
        "lim1_value": "0.000",
        "lim1_value_unit": "s",
        "lim1_action": "Next sequence",
        "lim1_seq": "",
        "lim2_type": "",
        "lim2_comp": "",
        "lim2_Q": "",
        "lim2_value": "",
        "lim2_value_unit": "",
        "lim2_action": "Next sequence",
        "lim2_seq": "",
        "rec_nb": "0",
        "rec1_type": "",
        "rec1_value": "",
        "rec1_value_unit": "",
        "rec2_type": "",
        "rec2_value": "",
        "rec2_value_unit": "",
        "E range min (V)": f"{low_range_V:.3f}",
        "E range max (V)": f"{high_range_V:.3f}",
        "I Range": "Auto",
        "I Range min": "Unset",
        "I Range max": "Unset",
        "I Range init": "Unset",
        "auto rest": "1",
        "Bandwidth": "5",
    }

    # Use fixed I range for CC and GEIS steps, Auto otherwise
    # There is no Auto option for CC or GEIS
    I_ranges_mA = {
        0.01: "10 µA",
        0.1: "100 µA",
        1: "1 mA",
        10: "10 mA",
        100: "100 mA",
    }

    # Make a list of dicts, one for each step
    step_dicts = []
    for i, step in enumerate(protocol.method):
        step_dict = default_step.copy()
        step_dict.update(
            {
                "Ns": str(i),
                "lim1_seq": str(i + 1),
                "lim2_seq": str(i + 1),
            },
        )
        match step:
            case _core.OpenCircuitVoltage():
                step_dict.update(
                    {
                        "ctrl_type": "Rest",
                        "lim_nb": "1",
                        "lim1_type": "Time",
                        "lim1_comp": ">",
                        "lim1_value": f"{step.until_time_s:.3f}",
                        "lim1_value_unit": "s",
                        "rec_nb": "1",
                        "rec1_type": "Time",
                        "rec1_value": f"{protocol.record.time_s or 0:.3f}",
                        "rec1_value_unit": "s",
                    },
                )

            case _core.ConstantCurrent():
                if step.rate_C and protocol.sample.capacity_mAh:
                    current_mA = step.rate_C * protocol.sample.capacity_mAh
                elif step.current_mA:
                    current_mA = step.current_mA
                else:
                    msg = "Either rate_C or current_mA must be set for ConstantCurrent step."
                    raise ValueError(msg)

                if abs(current_mA) < 1:
                    step_dict.update(
                        {
                            "ctrl_type": "CC",
                            "ctrl1_val": f"{current_mA * 1e3:.3f}",
                            "ctrl1_val_unit": "uA",
                            "ctrl1_val_vs": "<None>",
                        },
                    )
                else:
                    step_dict.update(
                        {
                            "ctrl_type": "CC",
                            "ctrl1_val": f"{current_mA:.3f}",
                            "ctrl1_val_unit": "mA",
                            "ctrl1_val_vs": "<None>",
                        },
                    )
                for val, range_str in I_ranges_mA.items():
                    if abs(current_mA) <= val:
                        step_dict.update({"I Range": range_str})
                        break
                else:
                    msg = f"I range not supported for {current_mA} mA"
                    raise ValueError(msg)

                # Add limit details
                lim_num = 0
                if step.until_time_s:
                    lim_num += 1
                    step_dict.update(
                        {
                            f"lim{lim_num}_type": "Time",
                            f"lim{lim_num}_comp": ">",
                            f"lim{lim_num}_value": f"{step.until_time_s:.3f}",
                            f"lim{lim_num}_value_unit": "s",
                        },
                    )
                if step.until_voltage_V:
                    lim_num += 1
                    comp = ">" if current_mA > 0 else "<"
                    step_dict.update(
                        {
                            f"lim{lim_num}_type": "Ewe",
                            f"lim{lim_num}_comp": comp,
                            f"lim{lim_num}_value": f"{step.until_voltage_V:.3f}",
                            f"lim{lim_num}_value_unit": "V",
                        },
                    )
                step_dict.update(
                    {
                        "lim_nb": str(lim_num),
                    },
                )

                # Add record details
                rec_num = 0
                if protocol.record.time_s:
                    rec_num += 1
                    step_dict.update(
                        {
                            f"rec{rec_num}_type": "Time",
                            f"rec{rec_num}_value": f"{protocol.record.time_s:.3f}",
                            f"rec{rec_num}_value_unit": "s",
                        },
                    )
                if protocol.record.voltage_V:
                    rec_num += 1
                    step_dict.update(
                        {
                            f"rec{rec_num}_type": "Ewe",
                            f"rec{rec_num}_value": f"{protocol.record.voltage_V:.3f}",
                            f"rec{rec_num}_value_unit": "V",
                        },
                    )
                step_dict.update(
                    {
                        "rec_nb": str(rec_num),
                    },
                )

            case _core.ConstantVoltage():
                step_dict.update(
                    {
                        "ctrl_type": "CV",
                        "ctrl1_val": f"{step.voltage_V:.3f}",
                        "ctrl1_val_unit": "V",
                        "ctrl1_val_vs": "Ref",
                    },
                )

                # Add limit details
                lim_num = 0
                if step.until_time_s:
                    lim_num += 1
                    step_dict.update(
                        {
                            f"lim{lim_num}_type": "Time",
                            f"lim{lim_num}_comp": ">",
                            f"lim{lim_num}_value": f"{step.until_time_s:.3f}",
                            f"lim{lim_num}_value_unit": "s",
                        },
                    )
                if step.until_rate_C and protocol.sample.capacity_mAh:
                    until_mA = step.until_rate_C * protocol.sample.capacity_mAh
                elif step.until_current_mA:
                    until_mA = step.until_current_mA
                else:
                    until_mA = None
                if until_mA:
                    lim_num += 1
                    step_dict.update(
                        {
                            f"lim{lim_num}_type": "|I|",
                            f"lim{lim_num}_comp": "<",
                            f"lim{lim_num}_value": f"{abs(until_mA):.3f}",
                            f"lim{lim_num}_value_unit": "mA",
                        },
                    )
                step_dict.update(
                    {
                        "lim_nb": str(lim_num),
                    },
                )
                if i > 0:
                    prev_mA = None
                    prev_step = protocol.method[i - 1]
                    if isinstance(prev_step, _core.ConstantCurrent):
                        prev_mA = None
                        if prev_step.rate_C and protocol.sample.capacity_mAh:
                            prev_mA = prev_step.rate_C * protocol.sample.capacity_mAh
                        elif prev_step.current_mA:
                            prev_mA = prev_step.current_mA
                        if prev_mA and prev_step.until_voltage_V == step.voltage_V:
                            for val, range_str in I_ranges_mA.items():
                                if abs(prev_mA) <= val:
                                    step_dict.update({"I Range": range_str})
                                    break

                # Add record details
                rec_num = 0
                if protocol.record.time_s:
                    rec_num += 1
                    step_dict.update(
                        {
                            f"rec{rec_num}_type": "Time",
                            f"rec{rec_num}_value": f"{protocol.record.time_s:.3f}",
                            f"rec{rec_num}_value_unit": "s",
                        },
                    )
                if protocol.record.current_mA:
                    rec_num += 1
                    step_dict.update(
                        {
                            f"rec{rec_num}_type": "I",
                            f"rec{rec_num}_value": f"{protocol.record.current_mA:.3f}",
                            f"rec{rec_num}_value_unit": "mA",
                        },
                    )
                step_dict.update(
                    {
                        "rec_nb": str(rec_num),
                    },
                )

            case _core.ImpedanceSpectroscopy():
                if step.amplitude_V:
                    step_dict.update({"ctrl_type": "PEIS"})
                    if step.amplitude_V >= 0.1:
                        step_dict.update({"ctrl1_val": f"{step.amplitude_V:.3f}"})
                        step_dict.update({"ctrl1_val_unit": "V"})
                    elif step.amplitude_V >= 0.001:
                        step_dict.update({"ctrl1_val": f"{step.amplitude_V * 1e3:.3f}"})
                        step_dict.update({"ctrl1_val_unit": "mV"})
                    else:
                        step_dict.update({"ctrl1_val": f"{step.amplitude_V * 1e6:.3f}"})
                        step_dict.update({"ctrl1_val_unit": "uV"})

                elif step.amplitude_mA:
                    step_dict.update({"ctrl_type": "GEIS"})
                    if step.amplitude_mA >= 1000:
                        step_dict.update({"ctrl1_val": f"{step.amplitude_mA / 1000:.3f}"})
                        step_dict.update({"ctrl1_val_unit": "A"})
                    elif step.amplitude_mA >= 1:
                        step_dict.update({"ctrl1_val": f"{step.amplitude_mA:.3f}"})
                        step_dict.update({"ctrl1_val_unit": "mA"})
                    else:
                        step_dict.update({"ctrl1_val": f"{step.amplitude_mA * 1000:.3f}"})
                        step_dict.update({"ctrl1_val_unit": "uA"})

                    for val, range_str in I_ranges_mA.items():
                        # GEIS I range behaves differently to CC
                        # 1 mA range means 0.5 mA max amplitude
                        if abs(step.amplitude_mA) * 2 <= val:
                            step_dict.update({"I Range": range_str})
                            break
                    else:
                        msg = f"I range not supported for {step.amplitude_mA} mA"
                        raise ValueError(msg)

                else:
                    msg = "Either amplitude_V or amplitude_mA must be set."
                    raise ValueError(msg)

                for freq, ctrl in ((step.start_frequency_Hz, 2), (step.end_frequency_Hz, 3)):
                    if freq >= 1e3:
                        step_dict.update({f"ctrl{ctrl}_val": f"{freq / 1e3:.3f}"})
                        step_dict.update({f"ctrl{ctrl}_val_unit": "kHz"})
                    elif freq >= 1:
                        step_dict.update({f"ctrl{ctrl}_val": f"{freq:.3f}"})
                        step_dict.update({f"ctrl{ctrl}_val_unit": "Hz"})
                    elif freq >= 1e-3:
                        step_dict.update({f"ctrl{ctrl}_val": f"{freq * 1e3:.3f}"})
                        step_dict.update({f"ctrl{ctrl}_val_unit": "mHz"})
                step_dict.update(
                    {
                        "ctrl_Nd": f"{step.points_per_decade}",
                        "ctrl_Na": f"{step.measures_per_point}",
                        "ctrl_corr": f"{1 if step.drift_correction is True else 0}",
                    }
                )

            case _core.Loop():
                assert isinstance(step.loop_to, int)  # noqa: S101, from _tag_to_indices()
                step_dict.update(
                    {
                        "ctrl_type": "Loop",
                        "ctrl_seq": str(step.loop_to - 1),  # 0-indexed here
                        "ctrl_repeat": str(step.cycle_count - 1),  # cycles is one less than n_gotos
                    },
                )

            case _:
                msg = f"to_biologic_mps() does not support step type: {step.step}"
                raise NotImplementedError(msg)

        step_dicts.append(step_dict)

    # Transform list of dicts into list of strings
    # Each row is one key and all values of each step
    # All elements must be 20 characters wide
    rows = []
    for row_header in default_step:
        row_data = [step[row_header] for step in step_dicts]
        rows.append(row_header.ljust(20) + "".join(d.ljust(20) for d in row_data))

    settings_string = "\n".join([*header, *rows, ""])

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open("w", encoding="cp1252") as f:
            f.write(settings_string)

    return settings_string
