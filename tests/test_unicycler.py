"""Tests for unicycler.py."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from unittest import TestCase
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree
from pydantic import ValidationError

from aurora_unicycler import __version__
from aurora_unicycler.unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    ImpedanceSpectroscopy,
    Loop,
    OpenCircuitVoltage,
    Protocol,
    RecordParams,
    SafetyParams,
    SampleParams,
    Step,
    Tag,
    coerce_c_rate,
)


class TestUnicycler(TestCase):
    """Unit tests for the unicycler module."""

    def setUp(self) -> None:
        """Set up for the tests."""
        base_folder = Path(__file__).parent / "test_data"
        self.example_protocol_paths = [
            base_folder / "test_protocol.json",
            base_folder / "test_protocol_placeholder_sample.json",
            base_folder / "test_protocol_no_sample.json",
            base_folder / "test_protocol_with_floats.json",
        ]
        data = []
        for path in self.example_protocol_paths:
            with path.open("r") as f:
                data.append(json.load(f))
        self.example_protocol_data = data
        self.example_jsonld_path = base_folder / "test_battinfo.jsonld"
        self.emmo_context_path = base_folder / "emmo_context.json"

    def test_from_json(self) -> None:
        """Test creating a Protocol instance from a JSON file."""
        protocol = Protocol.from_json(self.example_protocol_paths[0])
        assert isinstance(protocol, Protocol)
        assert protocol.sample.name == "test_sample"
        assert protocol.sample.capacity_mAh == Decimal(123)
        assert len(protocol.method) == 15
        assert isinstance(protocol.method[0], OpenCircuitVoltage)
        assert isinstance(protocol.method[1], ConstantCurrent)
        assert isinstance(protocol.method[2], OpenCircuitVoltage)
        assert isinstance(protocol.method[3], ConstantCurrent)
        assert isinstance(protocol.method[4], ConstantVoltage)
        assert isinstance(protocol.method[5], ConstantCurrent)
        assert isinstance(protocol.method[6], Loop)

    def test_from_dict(self) -> None:
        """Test creating a Protocol instance from a dictionary."""
        protocol_from_dict = Protocol.from_dict(self.example_protocol_data[0])
        protocol_from_file = Protocol.from_json(self.example_protocol_paths[0])
        assert protocol_from_dict == protocol_from_file

    def test_check_sample_details(self) -> None:
        """Test handling of missing sample details."""
        missing_name_msg = (
            "If using blank sample name or $NAME placeholder, "
            "a sample name must be provided in this function."
        )
        protocol = Protocol.from_dict(self.example_protocol_data[1])
        with pytest.raises(ValueError) as context:
            protocol.to_neware_xml()
        assert str(context.value) == missing_name_msg
        protocol = Protocol.from_dict(self.example_protocol_data[2])
        with pytest.raises(ValueError) as context:
            protocol.to_neware_xml()
        assert str(context.value) == missing_name_msg

        missing_cap_msg = "Sample capacity must be set if using C-rate steps."
        protocol = Protocol.from_dict(self.example_protocol_data[1], sample_name="test_sample")
        with pytest.raises(ValueError) as context:
            protocol.to_neware_xml()
        assert str(context.value) == missing_cap_msg
        protocol = Protocol.from_dict(self.example_protocol_data[2], sample_name="test_sample")
        with pytest.raises(ValueError) as context:
            protocol.to_neware_xml()
        assert str(context.value) == missing_cap_msg

        # should not raise error if both are provided
        protocol1 = Protocol.from_dict(
            self.example_protocol_data[1], sample_name="test_sample", sample_capacity_mAh=123
        )
        protocol2 = Protocol.from_dict(
            self.example_protocol_data[2],
            sample_name="test_sample",
            sample_capacity_mAh=123,
        )
        protocol1.to_neware_xml()
        protocol2.to_neware_xml()
        assert protocol1.sample.name == "test_sample"
        assert protocol1.sample.capacity_mAh == Decimal(123)
        assert protocol1 == protocol2

    def test_overwriting_sample_details(self) -> None:
        """Test overwriting sample details when creating from a dictionary."""
        protocol = Protocol.from_dict(
            self.example_protocol_data[0], sample_name="NewName", sample_capacity_mAh=456
        )
        assert protocol.sample.name == "NewName"
        assert protocol.sample.capacity_mAh == Decimal(456)

    def test_to_neware_xml(self) -> None:
        """Test converting a Protocol instance to Neware XML format."""
        protocol = Protocol.from_dict(self.example_protocol_data[0])
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

    def test_to_tomato_mpg2(self) -> None:
        """Test converting a Protocol instance to Tomato MPG2 format."""
        protocol = Protocol.from_dict(self.example_protocol_data[0])
        json_string = protocol.to_tomato_mpg2()
        assert isinstance(json_string, str)
        tomato_dict = json.loads(json_string)
        assert all(k in tomato_dict for k in ["version", "sample", "method", "tomato"])
        assert isinstance(tomato_dict["method"], list)
        assert len(tomato_dict["method"]) == len(protocol.method)
        assert tomato_dict["method"][0]["device"] == "MPG2"
        assert tomato_dict["method"][0]["technique"] == "open_circuit_voltage"
        assert tomato_dict["method"][1]["technique"] == "constant_current"
        assert tomato_dict["method"][2]["technique"] == "open_circuit_voltage"
        assert tomato_dict["method"][3]["technique"] == "constant_current"
        assert tomato_dict["method"][4]["technique"] == "constant_voltage"
        assert tomato_dict["method"][5]["technique"] == "constant_current"
        assert tomato_dict["method"][6]["technique"] == "loop"

    def test_to_pybamm_experiment(self) -> None:
        """Test converting a Protocol instance to PyBaMM experiment format."""
        protocol = Protocol.from_dict(self.example_protocol_data[0])
        experiment_list = protocol.to_pybamm_experiment()
        assert isinstance(experiment_list, list)
        assert len(experiment_list) > 0
        assert isinstance(experiment_list[0], str)
        assert experiment_list[0].startswith("Rest for")
        assert experiment_list[1].startswith("Charge at")
        assert experiment_list[2].startswith("Rest for")
        assert experiment_list[3].startswith("Charge at")
        assert experiment_list[4].startswith("Hold at")
        assert experiment_list[5].startswith("Discharge at")
        assert experiment_list[6].startswith("Charge at")  # no 'loop' in pybamm experiment

    def test_constant_current_validation(self) -> None:
        """Test validation of ConstantCurrent technique."""
        with pytest.raises(ValueError):
            # Missing rate_C and current_mA
            ConstantCurrent()
        with pytest.raises(ValueError):
            # rate_C and current_mA are zero
            ConstantCurrent(rate_C=0, current_mA=0)
        with pytest.raises(ValueError):
            # Missing stop condition
            ConstantCurrent(rate_C=0.1)
        with pytest.raises(ValueError):
            # stop conditions are zero
            ConstantCurrent(rate_C=0.1, until_time_s=0, until_voltage_V=0)
        cc = ConstantCurrent(rate_C=0.1, until_voltage_V=4.2)
        assert isinstance(cc, ConstantCurrent)

    def test_constant_voltage_validation(self) -> None:
        """Test validation of ConstantVoltage technique."""
        with pytest.raises(ValueError):
            # Missing stop condition
            ConstantVoltage(voltage_V=4.2)
        with pytest.raises(ValueError):
            # stop conditions are zero
            ConstantVoltage(
                voltage_V=4.2,
                until_time_s=0,
                until_rate_C=0,
                until_current_mA=0,
            )
        cv = ConstantVoltage(voltage_V=4.2, until_rate_C=0.05)
        assert isinstance(cv, ConstantVoltage)

    def test_protocol_c_rate_validation(self) -> None:
        """Test validation of Protocol with C-rate steps."""
        # Valid protocol
        protocol = Protocol.from_dict(self.example_protocol_data[0])
        assert isinstance(protocol, Protocol)

        # Invalid protocol (missing capacity)
        protocol.sample.capacity_mAh = Decimal(0)
        with pytest.raises(ValueError) as context:
            protocol.to_neware_xml()
        assert str(context.value) == "Sample capacity must be set if using C-rate steps."

    def test_loop_validation(self) -> None:
        """Test validation of Loop technique."""
        with pytest.raises(ValueError):
            Loop(loop_to=0, cycle_count=1)  # loop_to is zero
        with pytest.raises(ValueError):
            Loop(loop_to=1, cycle_count=0)  # cycle_count is zero
        loop = Loop(loop_to=1, cycle_count=1)
        assert isinstance(loop, Loop)

    def test_create_protocol(self) -> None:
        """Test creating a Protocol instance from a dictionary."""
        protocol = Protocol.from_dict(self.example_protocol_data[0])
        protocol = Protocol(
            sample=SampleParams(
                name="test_sample",
                capacity_mAh=123,
            ),
            record=RecordParams(
                time_s=Decimal(10),
                voltage_V=0.1,
                current_mA="0.1",
            ),
            safety=SafetyParams(
                max_current_mA=10,
                min_current_mA=-10,
                max_voltage_V=5,
                min_voltage_V=-0.1,
                delay_s=10,
            ),
            method=[
                OpenCircuitVoltage(
                    until_time_s=60 * 60,
                ),
                ConstantCurrent(
                    rate_C=1 / 10,
                    until_time_s=60 * 10,
                    until_voltage_V=2,
                ),
                OpenCircuitVoltage(
                    until_time_s=60 * 60 * 12,
                ),
                ConstantCurrent(
                    rate_C=0.1,
                    until_time_s=60 * 60 * 1 / 0.1 * 1.5,
                    until_voltage_V=4.9,
                ),
                ConstantVoltage(
                    voltage_V=4.9,
                    until_rate_C=0.01,
                    until_time_s=60 * 60 * 6,
                ),
                ConstantCurrent(
                    rate_C=-0.1,
                    until_time_s=60 * 60 * 1 / 0.1 * 1.5,
                    until_voltage_V=3.5,
                ),
                Loop(
                    loop_to=4,
                    cycle_count=3,
                ),
            ],
        )
        protocol_dict = json.loads(protocol.model_dump_json())
        assert protocol_dict["sample"]["name"] == "test_sample"
        # Should be able to be parsed into other formats
        protocol.to_neware_xml()
        protocol.to_tomato_mpg2()
        protocol.to_pybamm_experiment()
        protocol.to_biologic_mps()

    def test_tags(self) -> None:
        """Test tags in Protocol."""
        protocol = Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=2, cycle_count=3),
            ],
        )
        protocol.tag_to_indices()
        # this should not change the loop step
        assert isinstance(protocol.method[4], Loop)
        assert protocol.method[4].loop_to == 2

        protocol = Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),  # 0
                OpenCircuitVoltage(until_time_s=1),  # 1
                Tag(tag="tag1"),
                OpenCircuitVoltage(until_time_s=1),  # 2
                OpenCircuitVoltage(until_time_s=1),  # 3
                Loop(loop_to="tag1", cycle_count=3),  # 4
                OpenCircuitVoltage(until_time_s=1),  # 5
                Loop(loop_to=3, cycle_count=3),  # 6
            ],
        )
        # tag should be removed and replaced with the index
        protocol.tag_to_indices()
        assert isinstance(protocol.method[4], Loop)
        assert protocol.method[4].loop_to == 3
        assert isinstance(protocol.method[6], Loop)
        assert protocol.method[6].loop_to == 3

        protocol = Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),  # 0
                OpenCircuitVoltage(until_time_s=1),  # 1
                Tag(tag="tag1"),
                OpenCircuitVoltage(until_time_s=1),  # 2
                Tag(tag="tag2"),
                OpenCircuitVoltage(until_time_s=1),  # 3
                Loop(loop_to="tag1", cycle_count=3),  # 4
                OpenCircuitVoltage(until_time_s=1),  # 5
                Loop(loop_to=6, cycle_count=3),  # 6
                Tag(tag="tag3"),
                OpenCircuitVoltage(until_time_s=1),  # 7
                Loop(loop_to="tag2", cycle_count=3),  # 8
                OpenCircuitVoltage(until_time_s=1),  # 9
                OpenCircuitVoltage(until_time_s=1),  # 10
                Loop(loop_to="tag1", cycle_count=3),  # 11
                Tag(tag="tag that doesnt do anything"),
                Loop(loop_to="tag3", cycle_count=3),  # 12
            ],
        )
        protocol.tag_to_indices()
        assert isinstance(protocol.method[4], Loop)
        assert protocol.method[4].loop_to == 3
        assert isinstance(protocol.method[6], Loop)
        assert protocol.method[6].loop_to == 4
        assert isinstance(protocol.method[8], Loop)
        assert protocol.method[8].loop_to == 4
        assert isinstance(protocol.method[11], Loop)
        assert protocol.method[11].loop_to == 3
        assert isinstance(protocol.method[12], Loop)
        assert protocol.method[12].loop_to == 8

        # You should not be able to create a loop with a tag that does not exist
        with pytest.raises(ValidationError):
            protocol = Protocol(
                record=RecordParams(time_s=1),
                safety=SafetyParams(),
                method=[
                    OpenCircuitVoltage(until_time_s=1),
                    OpenCircuitVoltage(until_time_s=1),
                    OpenCircuitVoltage(until_time_s=1),
                    OpenCircuitVoltage(until_time_s=1),
                    Loop(loop_to="this tag does not exist", cycle_count=3),
                ],
            )

        # Loops cannot go forwards
        with pytest.raises(ValidationError):
            protocol = Protocol(
                record=RecordParams(time_s=1),
                safety=SafetyParams(),
                method=[
                    OpenCircuitVoltage(until_time_s=1),
                    Loop(loop_to="tag1", cycle_count=3),
                    OpenCircuitVoltage(until_time_s=1),
                    Tag(tag="tag1"),
                ],
            )

        # Loops cannot go forwards or land on themselves
        for i in [4, 5]:
            with pytest.raises(ValidationError):
                protocol = Protocol(
                    record=RecordParams(time_s=1),
                    safety=SafetyParams(),
                    method=[
                        OpenCircuitVoltage(until_time_s=1),
                        OpenCircuitVoltage(until_time_s=1),
                        OpenCircuitVoltage(until_time_s=1),
                        Loop(loop_to=i, cycle_count=3),
                        OpenCircuitVoltage(until_time_s=1),
                        OpenCircuitVoltage(until_time_s=1),
                        OpenCircuitVoltage(until_time_s=1),
                    ],
                )

        # Loops cannot go back to one index to a tag
        with pytest.raises(ValidationError):
            protocol = Protocol(
                record=RecordParams(time_s=1),
                safety=SafetyParams(),
                method=[
                    OpenCircuitVoltage(until_time_s=1),
                    Tag(tag="tag1"),
                    Loop(loop_to="tag1", cycle_count=3),
                    OpenCircuitVoltage(until_time_s=1),
                ],
            )

    def test_tag_neware(self) -> None:
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

    def test_cv_neware(self) -> None:
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

    def test_to_biologic_mps(self) -> None:
        """Test conversion to Biologic MPS."""
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
                Loop(loop_to=4, cycle_count=3),
            ],
        )
        biologic_mps = protocol.to_biologic_mps(sample_name="test", capacity_mAh=1.0)
        # Find where the line begins with "ctrl_seq"
        lines = biologic_mps.splitlines()
        ctrl_seq_start = next(
            (i for i, line in enumerate(lines) if line.startswith("ctrl_seq")),
            None,
        )
        assert ctrl_seq_start is not None, "ctrl_seq not found in Biologic MPS"
        test_str = (
            "ctrl_seq            0                   0                   0                   "
            "0                   2                   2                   "
        )
        assert lines[ctrl_seq_start] == test_str, "ctrl_seq line does not match expected"

    def test_coerce_c_rate(self) -> None:
        """Test the coerce_c_rate function."""
        assert coerce_c_rate("0.05") == 0.05
        assert coerce_c_rate("  0.05  ") == 0.05
        assert coerce_c_rate("1/20") == 0.05
        assert coerce_c_rate("C/5") == 0.2
        assert coerce_c_rate("D/5") == -0.2
        assert coerce_c_rate("3D/3") == -1.0
        assert coerce_c_rate("C5/25") == 0.2
        assert coerce_c_rate("2e-1") == 0.2
        assert coerce_c_rate("1.23e3 C / 1.23e4") == 0.1
        assert coerce_c_rate(" C 3   /    1 0 ") == 0.3
        assert coerce_c_rate(0.1) == 0.1
        assert coerce_c_rate(1) == 1.0
        assert coerce_c_rate(Decimal("0.1")) == 0.1
        with pytest.raises(ValueError):
            coerce_c_rate("invalid")
        with pytest.raises(ValueError):
            coerce_c_rate("1/2/3")
        with pytest.raises(ValueError):
            coerce_c_rate("1\5")
        with pytest.raises(ValueError):
            coerce_c_rate(" 1 . 0 ")
        with pytest.raises(ValueError):
            coerce_c_rate("5C/2D")
        with pytest.raises(ValueError):
            coerce_c_rate("3C/2C")
        with pytest.raises(ZeroDivisionError):
            coerce_c_rate("C/0")

    def test_coerce_c_rate_in_protocol(self) -> None:
        """Test the coerce_c_rate function in a protocol context."""
        protocol = Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                ConstantCurrent(until_time_s=1, rate_C="1/5"),
                ConstantCurrent(until_time_s=1, rate_C=0.2),
                ConstantCurrent(until_time_s=1, rate_C="C / 5"),
                ConstantCurrent(until_time_s=1, rate_C="0.2"),
                ConstantCurrent(until_time_s=1, rate_C=1 / 5),
                ConstantCurrent(until_time_s=1, rate_C="-0.2"),
                ConstantCurrent(until_time_s=1, rate_C="D/5"),
                ConstantVoltage(voltage_V=4.2, until_rate_C="C/5"),
                ConstantVoltage(voltage_V=4.2, until_rate_C="0.2"),
                ConstantVoltage(voltage_V=4.2, until_rate_C=1 / 5),
                ConstantVoltage(voltage_V=4.2, until_rate_C="C/5"),
            ],
        )
        assert protocol.method[0].rate_C == 0.2
        assert protocol.method[1].rate_C == 0.2
        assert protocol.method[2].rate_C == 0.2
        assert protocol.method[3].rate_C == 0.2
        assert protocol.method[4].rate_C == 0.2
        assert protocol.method[5].rate_C == -0.2
        assert protocol.method[6].rate_C == -0.2
        assert protocol.method[7].until_rate_C == 0.2
        assert protocol.method[8].until_rate_C == 0.2
        assert protocol.method[9].until_rate_C == 0.2
        assert protocol.method[10].until_rate_C == 0.2

    def test_biologic_mps(self) -> None:
        """Test filling in mps details."""
        kw1 = {"until_time_s": 10.0}
        kw2 = {"start_frequency_Hz": 1e3, "end_frequency_Hz": 1}
        my_protocol = Protocol(
            record=RecordParams(time_s=1),
            method=[
                ConstantCurrent(**kw1, current_mA=0.001),
                ConstantCurrent(**kw1, current_mA=0.01),
                ConstantCurrent(**kw1, current_mA=0.011),
                ConstantCurrent(**kw1, current_mA=0.1),
                ConstantCurrent(**kw1, current_mA=0.11),
                ConstantCurrent(**kw1, current_mA=1.0),
                ConstantCurrent(**kw1, current_mA=1.1),
                ConstantCurrent(**kw1, current_mA=10.0),
                ConstantCurrent(**kw1, current_mA=10.1),
                ConstantCurrent(**kw1, current_mA=100),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=0.001),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=0.005),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=0.006),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=0.05),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=0.06),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=0.5),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=0.6),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=5),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=6),
                ImpedanceSpectroscopy(**kw2, amplitude_mA=50),
            ],
        )
        biologic_mps = my_protocol.to_biologic_mps(sample_name="test", capacity_mAh=1)

        # Check I range
        line = next(a for a in biologic_mps.splitlines() if a.startswith("I Range"))
        ranges = re.split(r"\s{2,}", line.strip())
        expected = ["10 µA", "100 µA", "1 mA", "10 mA", "100 mA"]
        expected = [x for x in expected for _ in (0, 1)] * 2  # a b c -> a a b b c c a a b b c c
        assert ranges[1:] == expected

        # Check applied current uses sensible units
        line = next(a for a in biologic_mps.splitlines() if a.startswith("ctrl1_val"))
        vals = [float(x) for x in line.strip().split()[1:]]
        assert vals[:10] == [1, 10, 11, 100, 110, 1.0, 1.1, 10.0, 10.1, 100]
        line = next(a for a in biologic_mps.splitlines() if a.startswith("ctrl1_val_unit"))
        units = line.strip().split()[1:]
        assert units[:10] == ["uA", "uA", "uA", "uA", "uA", "mA", "mA", "mA", "mA", "mA"]
        units_to_mA = {"uA": 1e-3, "mA": 1}
        vals = [v * units_to_mA[u] for v, u in zip(vals, units, strict=True)]
        print(vals)
        assert vals[:10] == [0.001, 0.01, 0.011, 0.1, 0.11, 1.0, 1.1, 10.0, 10.1, 100]

    def test_build_steps(self) -> None:
        """User should be able to make steps with Step base class."""
        Protocol.from_dict(
            {
                "record": {"time_s": 1},
                "safety": {},
                "method": [
                    {"step": "open_circuit_voltage", "until_time_s": 1},
                    {"step": "tag", "tag": "tag1"},
                    {"step": "constant_current", "rate_C": 0.5, "until_voltage_V": 4.2},
                    {"step": "constant_voltage", "voltage_V": 4.2, "until_rate_C": 0.05},
                    {"step": "constant_current", "rate_C": -0.5, "until_voltage_V": 3.0},
                    {"step": "loop", "loop_to": "tag1", "cycle_count": 3},
                    {
                        "step": "impedance_spectroscopy",
                        "amplitude_V": 0.1,
                        "start_frequency_Hz": 1e3,
                        "end_frequency_Hz": 1,
                    },
                ],
            }
        )

    def test_naughty_step_building(self) -> None:
        """User can also give a dict for methods without from_dict, but type checkers don't like it."""
        Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                {"step": "open_circuit_voltage", "until_time_s": 1},
                {"step": "tag", "tag": "tag1"},
                {"step": "constant_current", "rate_C": 0.5, "until_voltage_V": 4.2},
                {"step": "constant_voltage", "voltage_V": 4.2, "until_rate_C": 0.05},
                {"step": "constant_current", "rate_C": -0.5, "until_voltage_V": 3.0},
                {"step": "loop", "loop_to": "tag1", "cycle_count": 3},
                {
                    "step": "impedance_spectroscopy",
                    "amplitude_V": 0.1,
                    "start_frequency_Hz": 1e3,
                    "end_frequency_Hz": 1,
                },
            ],
        )

    def test_empty_steps(self) -> None:
        """Protocols with empty steps should give a nice error."""
        # As a protocol
        with pytest.raises(ValidationError) as exc_info:
            Protocol(
                record=RecordParams(time_s=1),
                safety=SafetyParams(),
                method=[
                    Step(),
                ],
            )
        assert "is incomplete" in str(exc_info.value)
        # From a dict
        with pytest.raises(ValidationError) as exc_info:
            Protocol.from_dict(
                {
                    "record": {"time_s": 1},
                    "safety": {},
                    "method": [
                        {},
                    ],
                }
            )
        assert "is incomplete" in str(exc_info.value)

    def test_intersecting_loops(self) -> None:
        """Protocols with intersecting loops should give a error."""
        protocol = Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),
                Tag(tag="tag1"),
                OpenCircuitVoltage(until_time_s=1),
                Tag(tag="tag2"),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag2", cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag1", cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Tag(tag="tag3"),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag3", cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag1", cycle_count=3),
            ],
        )
        protocol.tag_to_indices()
        protocol.check_for_intersecting_loops()  # Should be fine

        protocol = Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=2, cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=1, cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=7, cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=1, cycle_count=3),
            ],
        )
        protocol.tag_to_indices()
        protocol.check_for_intersecting_loops()  # Should be fine

        protocol = Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),
                Tag(tag="tag1"),
                OpenCircuitVoltage(until_time_s=1),
                Tag(tag="tag2"),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag1", cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag2", cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Tag(tag="tag3"),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag3", cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to="tag1", cycle_count=3),
            ],
        )
        protocol.tag_to_indices()
        with pytest.raises(ValueError):  # Should fail
            protocol.check_for_intersecting_loops()

        protocol = Protocol(
            record=RecordParams(time_s=1),
            safety=SafetyParams(),
            method=[
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=2, cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=1, cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=5, cycle_count=3),
                OpenCircuitVoltage(until_time_s=1),
                Loop(loop_to=1, cycle_count=3),
            ],
        )
        protocol.tag_to_indices()
        with pytest.raises(ValueError):  # Should fail
            protocol.check_for_intersecting_loops()

    def test_to_battinfo_jsonld(self) -> None:
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
        with self.emmo_context_path.open("r") as f:
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
        with self.example_jsonld_path.open("r") as f:
            expected = json.load(f)
        assert bij == expected

        # Check if capacity overriding works
        my_protocol.sample.capacity_mAh = 100
        bij = my_protocol.to_battinfo_jsonld()
        assert bij["hasNext"]["hasTask"]["hasInput"][0]["hasNumericalPart"]["hasNumberValue"] == 5

        # Check if adding context works
        bij = my_protocol.to_battinfo_jsonld(include_context=True)
        assert bij["@context"] == ["https://w3id.org/emmo/domain/battery/context"]

    def test_updating_version(self) -> None:
        """Reading the file in should update the version to current version."""
        my_protocol = Protocol.from_dict(
            {
                "unicycler": {"version": "x.y.z"},
                "record": {"time_s": 1},
                "safety": {},
                "method": [{"step": "open_circuit_voltage", "until_time_s": 1}],
            }
        )
        assert my_protocol.unicycler.version == __version__

    def test_mutability(self) -> None:
        """Conversion functions should not mutate the protocol object."""
        my_protocol = Protocol.from_dict(
            {
                "unicycler": {"version": "x.y.z"},
                "sample": {"name": "test_sample"},
                "record": {"time_s": 1},
                "safety": {},
                "method": [
                    {"step": "tag", "tag": "tag1"},
                    {"step": "open_circuit_voltage", "until_time_s": 1},
                    {"step": "loop", "loop_to": "tag1", "cycle_count": 3},
                ],
            }
        )
        my_original_protocol = my_protocol.model_copy()
        assert my_protocol is not my_original_protocol
        assert my_protocol == my_original_protocol

        my_protocol.to_neware_xml()
        assert my_protocol == my_original_protocol

        my_protocol.to_tomato_mpg2()
        assert my_protocol == my_original_protocol

        my_protocol.to_pybamm_experiment()
        assert my_protocol == my_original_protocol

        my_protocol.to_biologic_mps()
        assert my_protocol == my_original_protocol

        my_protocol.to_battinfo_jsonld()
        assert my_protocol == my_original_protocol
