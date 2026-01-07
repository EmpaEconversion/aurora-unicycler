"""Extension for Neware BTS protocols."""

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from xml.dom import minidom

from aurora_unicycler import _core, _utils


def _neware_cc(
    step: _core.ConstantCurrent, step_num: int, capacity_mAh: float | None
) -> ET.Element:
    """Create ConstantCurrent step XML element."""
    if step.rate_C is not None and step.rate_C != 0:
        step_type = "1" if step.rate_C > 0 else "2"
    else:
        assert step.current_mA is not None  # noqa: S101  ensured by Pydantic
        assert step.current_mA != 0  # noqa: S101  ensured by Pydantic
        step_type = "1" if step.current_mA > 0 else "2"

    step_element = ET.Element(f"Step{step_num}", Step_ID=str(step_num), Step_Type=step_type)
    limit = ET.SubElement(step_element, "Limit")
    main = ET.SubElement(limit, "Main")
    if step.rate_C is not None:
        assert capacity_mAh is not None  # noqa: S101, from _validate_capacity_c_rates()
        ET.SubElement(main, "Rate", Value=f"{abs(step.rate_C):f}")
        ET.SubElement(
            main,
            "Curr",
            Value=f"{abs(step.rate_C) * capacity_mAh:f}",
        )
    elif step.current_mA is not None:
        ET.SubElement(main, "Curr", Value=f"{abs(step.current_mA):f}")
    if step.until_time_s is not None:
        ET.SubElement(main, "Time", Value=f"{step.until_time_s * 1000:f}")
    if step.until_voltage_V is not None:
        ET.SubElement(main, "Stop_Volt", Value=f"{step.until_voltage_V * 10000:f}")
    return step_element


def _neware_cv(
    step: _core.ConstantVoltage,
    prev_step: _core.Step | None,
    step_num: int,
    capacity_mAh: float | None,
):
    """Create ConstantVoltage step XML element."""
    # Check if CV follows CC and has the same voltage cutoff
    prev_rate_C = None
    prev_current_mA = None
    if isinstance(prev_step, _core.ConstantCurrent) and prev_step.until_voltage_V == step.voltage_V:
        if prev_step.rate_C is not None:
            assert capacity_mAh is not None  # noqa: S101, from _validate_capacity_c_rates()
            prev_rate_C = abs(prev_step.rate_C)
            prev_current_mA = abs(prev_step.rate_C) * capacity_mAh
        elif prev_step.current_mA is not None:
            prev_current_mA = abs(prev_step.current_mA)
    if step.until_rate_C is not None and step.until_rate_C != 0:
        step_type = "3" if step.until_rate_C > 0 else "19"
    elif step.until_current_mA is not None and step.until_current_mA != 0:
        step_type = "3" if step.until_current_mA > 0 else "19"
    else:
        step_type = "3"  # If it can't be figured out, default to charge
    step_element = ET.Element(f"Step{step_num}", Step_ID=str(step_num), Step_Type=step_type)
    limit = ET.SubElement(step_element, "Limit")
    main = ET.SubElement(limit, "Main")
    ET.SubElement(main, "Volt", Value=f"{step.voltage_V * 10000:f}")
    if step.until_time_s is not None:
        ET.SubElement(main, "Time", Value=f"{step.until_time_s * 1000:f}")
    if step.until_rate_C is not None:
        assert capacity_mAh is not None  # noqa: S101, from _validate_capacity_c_rates()
        ET.SubElement(main, "Stop_Rate", Value=f"{abs(step.until_rate_C):f}")
        ET.SubElement(
            main,
            "Stop_Curr",
            Value=f"{abs(step.until_rate_C) * capacity_mAh:f}",
        )
    elif step.until_current_mA is not None:
        ET.SubElement(main, "Stop_Curr", Value=f"{abs(step.until_current_mA):f}")
    if prev_rate_C is not None:
        assert capacity_mAh is not None  # noqa: S101, from _validate_capacity_c_rates()
        ET.SubElement(main, "Rate", Value=f"{abs(prev_rate_C):f}")
        ET.SubElement(
            main,
            "Curr",
            Value=f"{abs(prev_rate_C) * capacity_mAh:f}",
        )
    elif prev_current_mA is not None:
        ET.SubElement(main, "Curr", Value=f"{abs(prev_current_mA):f}")
    return step_element


def _neware_ocv(step: _core.OpenCircuitVoltage, step_num: int) -> ET.Element:
    """Create OpenCircuitVoltage step XML element."""
    step_element = ET.Element(f"Step{step_num}", Step_ID=str(step_num), Step_Type="4")
    limit = ET.SubElement(step_element, "Limit")
    main = ET.SubElement(limit, "Main")
    ET.SubElement(main, "Time", Value=f"{step.until_time_s * 1000:f}")
    return step_element


def _neware_loop(step: _core.Loop, step_num: int) -> ET.Element:
    """Create Loop step XML element."""
    step_element = ET.Element(f"Step{step_num}", Step_ID=str(step_num), Step_Type="5")
    limit = ET.SubElement(step_element, "Limit")
    other = ET.SubElement(limit, "Other")
    ET.SubElement(other, "Start_Step", Value=str(step.loop_to))
    ET.SubElement(other, "Cycle_Count", Value=str(step.cycle_count))
    return step_element


def _step_to_element(
    step: _core.AnyTechnique,
    step_num: int,
    prev_step: _core.AnyTechnique | None = None,
    capacity_mAh: float | None = None,
) -> ET.Element:
    """Create step XML element."""
    match step:
        case _core.ConstantCurrent():
            return _neware_cc(step, step_num, capacity_mAh)

        case _core.ConstantVoltage():
            return _neware_cv(step, prev_step, step_num, capacity_mAh)

        case _core.OpenCircuitVoltage():
            return _neware_ocv(step, step_num)

        case _core.Loop():
            return _neware_loop(step, step_num)

        case _:
            msg = f"to_neware_xml() does not support step type: {step.step}"
            raise NotImplementedError(msg)


def _neware_record_params(record_params: _core.RecordParams) -> ET.Element:
    """Create record params XML element."""
    record_element = ET.Element("Record")
    main_record = ET.SubElement(record_element, "Main")
    if record_params.time_s:
        ET.SubElement(main_record, "Time", Value=f"{record_params.time_s * 1000:f}")
    if record_params.voltage_V:
        ET.SubElement(main_record, "Volt", Value=f"{record_params.voltage_V * 10000:f}")
    if record_params.current_mA:
        ET.SubElement(main_record, "Curr", Value=f"{record_params.current_mA:f}")
    return record_element


def _neware_safety_params(safety: _core.SafetyParams) -> ET.Element:
    """Create safety params XML element."""
    protect_element = ET.Element("Protect")
    main_protect = ET.SubElement(protect_element, "Main")
    volt = ET.SubElement(main_protect, "Volt")
    if safety.max_voltage_V is not None:
        ET.SubElement(volt, "Upper", Value=f"{safety.max_voltage_V * 10000:f}")
    if safety.min_voltage_V is not None:
        ET.SubElement(volt, "Lower", Value=f"{safety.min_voltage_V * 10000:f}")
    curr = ET.SubElement(main_protect, "Curr")
    if safety.max_current_mA:
        ET.SubElement(curr, "Upper", Value=f"{safety.max_current_mA:f}")
    if safety.min_current_mA:
        ET.SubElement(curr, "Lower", Value=f"{safety.min_current_mA:f}")
    if safety.delay_s:
        ET.SubElement(main_protect, "Delay_Time", Value=f"{safety.delay_s * 1000:f}")
    cap = ET.SubElement(main_protect, "Cap")
    if safety.max_capacity_mAh:
        ET.SubElement(cap, "Upper", Value=f"{safety.max_capacity_mAh * 3600:f}")
    return protect_element


def to_neware_xml(
    protocol: _core.BaseProtocol,
    save_path: Path | str | None = None,
    sample_name: str | None = None,
    capacity_mAh: float | None = None,
) -> str:
    """Convert the protocol to Neware XML format."""
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

    # Create XML structure
    root = ET.Element("root")
    config = ET.SubElement(
        root,
        "config",
        type="Step File",
        version="17",
        client_version="BTS Client 8.0.0.478(2024.06.24)(R3)",
        date=datetime.now().strftime("%Y%m%d%H%M%S"),
        Guid=str(uuid.uuid4()),
    )
    head_info = ET.SubElement(config, "Head_Info")
    ET.SubElement(head_info, "Operate", Value="66")
    ET.SubElement(head_info, "Scale", Value="1")
    ET.SubElement(head_info, "Start_Step", Value="1", Hide_Ctrl_Step="0")
    ET.SubElement(head_info, "Creator", Value="aurora-unicycler")
    ET.SubElement(head_info, "Remark", Value=protocol.sample.name)
    # 103, non C-rate mode, seems to give more precise values vs 105
    ET.SubElement(head_info, "RateType", Value="103")
    if protocol.sample.capacity_mAh:
        ET.SubElement(head_info, "MultCap", Value=f"{protocol.sample.capacity_mAh * 3600:f}")

    whole_prt = ET.SubElement(config, "Whole_Prt")
    whole_prt.append(_neware_safety_params(protocol.safety))
    whole_prt.append(_neware_record_params(protocol.record))

    step_info = ET.SubElement(
        config, "Step_Info", Num=str(len(protocol.method) + 1)
    )  # +1 for end step

    for i, technique in enumerate(protocol.method):
        step_num = i + 1
        prev_step = protocol.method[i - 1] if i >= 1 else None
        step_info.append(
            _step_to_element(technique, step_num, prev_step, protocol.sample.capacity_mAh),
        )

    # Add an end step
    step_num = len(protocol.method) + 1
    ET.SubElement(step_info, f"Step{step_num}", Step_ID=str(step_num), Step_Type="6")

    smbus = ET.SubElement(config, "SMBUS")
    ET.SubElement(smbus, "SMBUS_Info", Num="0", AdjacentInterval="0")

    # Convert to string and prettify it
    pretty_xml_string = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")  # noqa: S318
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with save_path.open("w", encoding="utf-8") as f:
            f.write(pretty_xml_string)
    return pretty_xml_string
