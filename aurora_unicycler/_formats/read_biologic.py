"""Experimental module for reading an .mps into a unicycler protocol.

The scope of .mps is much larger than unicycler - so the conversion will always be lossy.
"""

import logging
import re
from typing import Any
from uuid import uuid4

from aurora_unicycler import _core

logger = logging.getLogger(__name__)

CURR_MULT = {
    "A": 1e3,
    "mA": 1,
    "uA": 1e-3,
    "μA": 1e-3,
    "nA": 1e-6,
    "pA": 1e-9,
}
RATE_MULT = {
    "V/s": 1e3,
    "mV/s": 1,
    "mV/mn": 1 / 60,
}


def parse_techniques(text: str) -> list[dict[str, list[str | float]]]:
    """Read an mps string, split into techniques."""
    # Split on "Technique : N" headers
    technique_blocks = re.split(r"Technique\s*:\s*\d+\s*\n", text)
    technique_blocks = [b for b in technique_blocks[1:] if b.strip()]

    techniques = []

    for block in technique_blocks:
        lines = block.split("\n")
        # First non-empty line is the technique name
        name = next((l.strip() for l in lines if l.strip()), None)
        result = {"technique": name}
        for line in lines[1:]:
            if not line.strip():
                continue
            # Key is first 20 chars (stripped), rest are values in 20-char cells
            key = line[:20].strip()
            if not key:
                continue
            # Split remainder into 20-char chunks
            rest = line[20:]
            values = [rest[i : i + 20].strip() for i in range(0, len(rest), 20)]
            values = [v for v in values if v]  # drop empty trailing cells
            if values:
                if key in result:
                    i = 1
                    while f"{key}_{i}" in result:
                        i += 1
                    result[f"{key}_{i}"] = values
                else:
                    result[key] = values
        techniques.append(result)

    return techniques


def parse_time(time_str: str) -> float:
    h, m, s = time_str.split(":")
    return float(h) * 3600 + float(m) * 60 + float(s)


def unicycle_gcpl(tech: dict) -> list[_core.AnyTechnique]:
    """Convert GCPL to unicycler technique list."""
    uuid = uuid4().hex[:8]
    method_with_pos: dict[float, list[Any]] = {}
    n_subtechs = len(tech["Set I/C"])

    for i in range(n_subtechs):
        method_with_pos[i] = []

        # CC step
        mult = -1 if i == n_subtechs - 1 else 1  # Discharge or charge
        if tech["Set I/C"][i] == "C / N" and float(tech["N"][i]):  # CC with C/x c-rate
            method_with_pos[i].append(
                _core.ConstantCurrent(
                    rate_C=mult / float(tech["N"][i]),
                    until_voltage_V=tech["EM (V)"][i],
                    until_time_s=parse_time(tech["t1 (h:m:s)"][i]),
                )
            )
        elif tech["Set I/C"][i] == "C x N" and float(tech["N"][i]):  # CC with xC c-rate
            method_with_pos[i].append(
                _core.ConstantCurrent(
                    rate_C=mult * float(tech["N"][i]),
                    until_voltage_V=tech["EM (V)"][i],
                    until_time_s=parse_time(tech["t1 (h:m:s)"][i]),
                )
            )
        elif tech["Set I/C"][i] == "I" and float(tech["Is"][i]):  # CC with current
            method_with_pos[i].append(
                _core.ConstantCurrent(
                    current_mA=CURR_MULT[tech["unit Is"][i]] * float(tech["Is"][i]),
                    until_voltage_V=tech["EM (V)"][i],
                    until_time_s=parse_time(tech["t1 (h:m:s)"][i]),
                )
            )

        # CV step
        hold_time = parse_time(tech["tR (h:m:s)"][i])
        if hold_time > 0:
            if float(tech["dI/dt"][i]):
                logger.warning("GCPL CV step - Unicycler doesn't support dI/dt termination")
            if float(tech["dQM"][i]):
                logger.warning("GCPL CV step - Unicycler doesn't support Q termination")
            method_with_pos[i].append(
                _core.ConstantVoltage(
                    voltage_V=tech["EM (V)"][i],
                    until_current_mA=float(tech["Im"][i]) * CURR_MULT[tech["unit Im"][i]],
                    until_time_s=hold_time,
                )
            )

        # OCV step
        rest_time = parse_time(tech["tR (h:m:s)"][i])
        if rest_time > 0:
            if float(tech["dER/dt (mV/h)"][i]):
                logger.warning("GCPL rest step - Unicycler doesn't support dV/dt termination")
            method_with_pos[i].append(_core.OpenCircuitVoltage(until_time_s=rest_time))

    # Loop on the last one
    if int(tech["nc cycles"][-1]):
        index = int(tech["goto Ns'"][-1])
        cycle_count = int(tech["nc cycles"][-1]) + 1
        if cycle_count > 1:
            method_with_pos[index - 0.5] = [_core.Tag(tag=uuid)]
            method_with_pos[999] = [_core.Loop(loop_to=uuid, cycle_count=cycle_count)]

    # Sort and flatten the list of techniques
    return [item for k in sorted(method_with_pos) for item in method_with_pos[k]]


def unicycle_cp(tech: dict) -> list[_core.AnyTechnique]:
    """Convert chronopotentiometry (constant current) to unicycler technique list."""
    mult = {
        "uA": 1e-3,
        "mA": 1,
        "A": 1e3,
    }
    return [
        _core.ConstantCurrent(
            current_mA=float(tech["Is"][i]) * mult[tech["unit Is"][i]],
            until_time_s=parse_time(tech["ts (h:m:s)"][i]),
        )
        for i in range(len(tech["Is"]))
    ]


def unicycle_ca(tech: dict) -> list[_core.AnyTechnique]:
    """Convert chronoamperometry (constant voltage) to unicycler technique list."""
    # TODO: No way to say voltage is vs open-circuit in unicycler
    # TODO: Not clear on the current limit here
    mult = {
        "uA": 1e-3,
        "mA": 1,
        "A": 1e3,
    }
    return [
        _core.ConstantVoltage(
            voltage_V=float(tech["Ei (V)"][i]),
            until_time_s=parse_time(tech["ti (h:m:s)"][i]),
            until_current_mA=tech["Imin"][i] * mult[tech["unit Imin"][i]],
        )
        for i in range(len(tech["Ei (V)"]))
    ]


def unicycle_lsv(tech: dict) -> list[_core.AnyTechnique]:
    """Convert LSV to unicycler technique list."""
    return [
        _core.VoltageScan(
            start_voltage_V=tech["Ei (V)"][i],
            end_voltage_V=tech["EL (V)"][i],
            scan_rate_mV_per_s=tech["dE/dt"][i] * RATE_MULT[tech["dE/dt unit"][i]],
        )
        for i in range(len(tech["Ei (V)"]))
    ]


def unicycle_eis(tech: dict) -> list[_core.AnyTechnique]:
    """Convert EIS to unicycler technique list."""
    mult = {
        "mHz": 1e-3,
        "Hz": 1,
        "kHz": 1e3,
    }
    return [
        _core.ImpedanceSpectroscopy(
            amplitude_V=float(tech["Va (mV)"][i]) * 1e-3,
            start_frequency_Hz=float(tech["fi"][i]) * mult[tech["unit fi"][i]],
            end_frequency_Hz=float(tech["ff"][i]) * mult[tech["unit ff"][i]],
            drift_correction=tech["Mode"][i] == "Multi sine",
        )
        for i in range(len(tech["Va (mV)"]))
    ]


def unicycle_ocv(tech: dict) -> list[_core.AnyTechnique]:
    """Convert OCV to unicycler technique list."""
    return [
        _core.OpenCircuitVoltage(
            until_time_s=parse_time(tech["tR (h:m:s)"][i]),
        )
        for i in range(len(tech["tR (h:m:s)"]))
    ]


def unicycle_cva(tech: dict) -> list[_core.AnyTechnique]:
    """Convert CV or CVA to unicycler technique list."""
    all_methods = []
    n_subtechs = len(tech["Ns"])

    for i in range(n_subtechs):
        submethod = []
        scan_rate = float(tech["dE/dt"][i]) * RATE_MULT[tech["dE/dt unit"][i]]
        start_hold = parse_time(tech["ti (h:m:s)"][i]) if "ti (h:m:s)" in tech else 0
        start_V = float(tech["Ei (V)"][i])
        start_V_vs = tech["vs."][i] if "vs." in tech else "Ref"
        top_hold = parse_time(tech["t1 (h:m:s)"][i]) if "t1 (h:m:s)" in tech else 0
        top_V = float(tech["E1 (V)"][i])
        top_V_vs = tech["vs._1"][i] if "t1 (h:m:s)" in tech else "Ref"
        bottom_hold = parse_time(tech["t2 (h:m:s)"][i]) if "t2 (h:m:s)" in tech else 0
        bottom_V = float(tech["E2 (V)"][i])
        bottom_V_vs = tech["vs._2"][i] if "t2 (h:m:s)" in tech else "Ref"
        final_hold = parse_time(tech["tf (h:m:s)"][i]) if "tf (h:m:s)" in tech else 0
        final_V = float(tech["Ef (V)"][i])
        final_V_vs = tech["vs._3"][i] if "tf (h:m:s)" in tech else "Ref"
        n_cycles = int(tech["nc cycles"][i]) + 1

        # CV start
        if start_hold > 0:
            if start_V_vs == "Ref":
                submethod.append(
                    _core.ConstantVoltage(
                        voltage_V=start_V,
                        until_time_s=start_hold,
                    )
                )
            else:
                logger.warning(
                    "Unicycler only supports voltage hold vs ref, not vs '%s' in CV start hold.",
                    start_V_vs,
                )
        # Skip from here if no rate
        if not scan_rate:
            continue
        # LSV up
        submethod.append(
            _core.VoltageScan(
                start_voltage_V=start_V,
                end_voltage_V=top_V,
                scan_rate_mV_per_s=scan_rate,
            )
        )
        # CV top
        if top_hold > 0:
            if top_V_vs == "Ref":
                submethod.append(
                    _core.ConstantVoltage(
                        voltage_V=top_V,
                        until_time_s=top_hold,
                    )
                )
            else:
                logger.warning(
                    "Unicycler only supports voltage hold vs ref, not vs '%s' in CV top hold.",
                    top_V_vs,
                )
        # LSV down
        submethod.append(
            _core.VoltageScan(
                start_voltage_V=top_V,
                end_voltage_V=bottom_V,
                scan_rate_mV_per_s=scan_rate,
            )
        )
        # CV bottom
        if bottom_hold > 0:
            if bottom_V_vs == "Ref":
                submethod.append(
                    _core.ConstantVoltage(voltage_V=bottom_V, until_time_s=bottom_hold)
                )
            else:
                logger.warning(
                    "Unicycler only supports voltage hold vs ref, not vs '%s' in CV bottom hold.",
                    bottom_V_vs,
                )
        # Loop
        if n_cycles > 1:
            uuid = uuid4().hex[:8]
            submethod.append(_core.Loop(loop_to=uuid, cycle_count=n_cycles))
            submethod.insert(0, _core.Tag(tag=uuid))

        # Final hold
        if final_hold > 0:
            if final_V_vs == "Ref":
                submethod.append(_core.ConstantVoltage(voltage_V=final_V, until_time_s=final_hold))
            else:
                logger.warning(
                    "Unicycler only supports voltage hold vs ref, not vs '%s' in CV final hold.",
                    bottom_V_vs,
                )

        all_methods.extend(submethod)

    return all_methods


def unicycle_techniques(techniques: list[dict]) -> list[_core.AnyTechnique]:
    """Convert a list of mps techniques to unicycler technique list."""
    method_with_pos: dict[float, list[Any]] = {}
    for i, tech in enumerate(techniques):
        tech_name = tech["technique"].strip()
        if tech_name == "Galvanostatic Cycling with Potential Limitation":
            method_with_pos[i] = unicycle_gcpl(tech)
        elif tech_name == "Potentio Electrochemical Impedance Spectroscopy":
            method_with_pos[i] = unicycle_eis(tech)
        elif tech_name == "Chronoamperometry / Chronocoulometry":
            method_with_pos[i] = unicycle_ca(tech)
        elif tech_name == "Chronopotentiometry":
            method_with_pos[i] = unicycle_cp(tech)
        elif tech_name == "Linear Sweep Voltammetry":
            method_with_pos[i] = unicycle_lsv(tech)
        elif tech_name == "Open Circuit Voltage":
            method_with_pos[i] = unicycle_ocv(tech)
        elif tech_name in {"Cyclic Voltammetry", "Cyclic Voltammetry Advanced"}:
            method_with_pos[i] = unicycle_cva(tech)
        elif tech_name == "Loop":
            uuid = uuid4().hex[:8]
            index = int(tech["goto Ne"][0]) - 1
            cycle_count = int(tech["nt times"][0]) + 1
            method_with_pos[i] = [_core.Loop(loop_to=uuid, cycle_count=cycle_count)]
            method_with_pos[index - 0.5] = [_core.Tag(tag=uuid)]
        else:
            msg = f"didnt understand technique {tech['technique']}"
            raise ValueError(msg)
    return [item for k in sorted(method_with_pos) for item in method_with_pos[k]]


def mps_to_unicycler_list(mps_string: str) -> list[_core.AnyTechnique]:
    technqiues = parse_techniques(mps_string)
    return unicycle_techniques(technqiues)
