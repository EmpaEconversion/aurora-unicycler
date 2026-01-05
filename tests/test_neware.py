"""Tests for Neware XML conversion."""

from __future__ import annotations

from xml.etree.ElementTree import Element

from defusedxml import ElementTree

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


def test_to_neware_xml(test_data: dict) -> None:
    """Test converting a Protocol instance to Neware XML format."""
    protocol = Protocol.from_dict(test_data["protocol_dicts"][0])
    xml_string = protocol.to_neware_xml()
    assert isinstance(xml_string, str)
    assert xml_string.startswith("<?xml")
    assert "<config" in xml_string
    # read the xml to element tree
    root = ElementTree.fromstring(xml_string)
    assert root.tag == "root"
    config = root.find("config")
    assert config is not None
    assert config.attrib["type"] == "Step File"
    assert config.attrib["client_version"].startswith("BTS Client")
    assert config.find("Head_Info") is not None
    assert config.find("Whole_Prt") is not None
    assert config.find("Whole_Prt/Protect") is not None
    assert config.find("Whole_Prt/Record") is not None
    step_info = config.find("Step_Info")
    assert step_info is not None
    assert step_info.attrib["Num"] == str(
        len(protocol.method) + 1
    )  # +1 for 'End' step added for Neware
    assert len(step_info) == int(step_info.attrib["Num"])


def test_tag_neware(test_data: dict) -> None:
    """Test tags in Neware XML."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag1"),
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=1),
            Loop(loop_to="tag1", cycle_count=3),
        ],
    )
    xml_string = protocol.to_neware_xml(sample_name="test")
    neware_ET = ElementTree.fromstring(xml_string)
    loopstep = neware_ET.find("config/Step_Info/Step5")
    assert loopstep is not None
    assert loopstep.attrib["Step_Type"] == "5"
    loop_to = loopstep.find("Limit/Other/Start_Step")
    assert loop_to is not None
    assert loop_to.attrib["Value"] == "3"

    protocol1 = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            Tag(tag="tag1"),
            OpenCircuitVoltage(until_time_s=2),
            Tag(tag="tag2"),
            OpenCircuitVoltage(until_time_s=3),
            OpenCircuitVoltage(until_time_s=4),
            OpenCircuitVoltage(until_time_s=5),
            Loop(loop_to="tag2", cycle_count=3),
            OpenCircuitVoltage(until_time_s=6),
            Loop(loop_to="tag1", cycle_count=5),
            OpenCircuitVoltage(until_time_s=7),
        ],
    )

    protocol2 = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            OpenCircuitVoltage(until_time_s=2),
            OpenCircuitVoltage(until_time_s=3),
            OpenCircuitVoltage(until_time_s=4),
            OpenCircuitVoltage(until_time_s=5),
            Loop(loop_to=3, cycle_count=3),
            OpenCircuitVoltage(until_time_s=6),
            Loop(loop_to=2, cycle_count=5),
            OpenCircuitVoltage(until_time_s=7),
        ],
    )
    neware1 = protocol1.to_neware_xml(sample_name="test")
    neware2 = protocol2.to_neware_xml(sample_name="test")
    # remove the date and uuid from the xml, starts with Guid=" and ends with "
    # use regex to remove it
    idx = neware1.find("date=")
    neware1 = neware1[:idx] + neware1[idx + 65 :]
    neware2 = neware2[:idx] + neware2[idx + 65 :]
    assert neware1 == neware2


def test_cv_neware(test_data: dict) -> None:
    """Test if CV steps get start current from previous steps."""
    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            ConstantCurrent(rate_C=0.1, until_voltage_V=4.2),
            ConstantVoltage(voltage_V=4.2, until_rate_C=0.01),
            ConstantCurrent(rate_C=-0.1, until_voltage_V=3.5),
        ],
    )
    xml = protocol.to_neware_xml(sample_name="test", capacity_mAh=5)
    step3 = ElementTree.fromstring(xml).find("config/Step_Info/Step3/Limit/Main")
    assert isinstance(step3, Element)
    rate = step3.find("Rate")
    assert isinstance(rate, Element)
    assert float(rate.get("Value")) == 0.1
    curr = step3.find("Curr")
    assert isinstance(curr, Element)
    assert float(curr.get("Value")) == 0.5

    protocol = Protocol(
        record=RecordParams(time_s=1),
        safety=SafetyParams(),
        method=[
            OpenCircuitVoltage(until_time_s=1),
            ConstantCurrent(current_mA=0.5, until_voltage_V=4.2),
            ConstantVoltage(voltage_V=4.2, until_current_mA=0.05),
            ConstantCurrent(current_mA=-0.5, until_voltage_V=3.5),
        ],
    )
    xml = protocol.to_neware_xml(sample_name="test", capacity_mAh=1)
    step3 = ElementTree.fromstring(xml).find("config/Step_Info/Step3/Limit/Main")
    assert isinstance(step3, Element)
    rate = step3.find("Rate")
    assert rate is None
    curr = step3.find("Curr")
    assert isinstance(curr, Element)
    assert float(curr.get("Value")) == 0.5
