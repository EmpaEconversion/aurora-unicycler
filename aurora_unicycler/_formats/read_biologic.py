"""Experimental module for reading an .mps into a unicycler protocol.

The scope of .mps is much larger than unicycler - so the conversion will always be lossy.
"""

import re
from typing import Any
from uuid import uuid4

from aurora_unicycler import _core


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

        mult = -1 if i == n_subtechs - 1 else 1  # Discharge or charge
        if tech["Set I/C"][i] == "C / N" and tech["N"][i]:
            method_with_pos[i].append(
                _core.ConstantCurrent(
                    rate_C=mult / float(tech["N"][i]),
                    until_voltage_V=tech["EM (V)"][i],
                    until_time_s=parse_time(tech["t1 (h:m:s)"][i]),
                )
            )
        rest_time = parse_time(tech["tR (h:m:s)"][i])
        if rest_time > 0:
            method_with_pos[i].append(_core.OpenCircuitVoltage(until_time_s=rest_time))

    # Loop on the last one
    if int(tech["nc cycles"][-1]):
        index = int(tech["goto Ns'"][-1])
        cycle_count = int(tech["nc cycles"][-1]) + 1
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
            current_mA=float(tech["Is"][0]) * mult[tech["unit Is"][0]],
            until_time_s=parse_time(tech["ts (h:m:s)"][0]),
        )
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
            voltage_V=float(tech["Ei (V)"][0]),
            until_time_s=parse_time(tech["ti (h:m:s)"][0]),
            until_current_mA=tech["Imin"][0] * mult[tech["unit Imin"][0]],
        )
    ]


def unicycle_lsv(tech: dict) -> list[_core.AnyTechnique]:
    """Convert LSV to unicycler technique list."""
    mult = {
        "mV/s": 1,
        "V/s": 1e3,
        "mV/mn": 1 / 60,
    }
    return [
        _core.VoltageScan(
            start_voltage_V=tech["Ei (V)"][0],
            end_voltage_V=tech["EL (V)"][0],
            scan_rate_mV_per_s=tech["dE/dt"][0] * mult[tech["dE/dt unit"][0]],
        )
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
            amplitude_V=float(tech["Va (mV)"][0]) * 1e-3,
            start_frequency_Hz=float(tech["fi"][0]) * mult[tech["unit fi"][0]],
            end_frequency_Hz=float(tech["ff"][0]) * mult[tech["unit ff"][0]],
            drift_correction=tech["Mode"][0] == "Multi sine",
        )
    ]


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
