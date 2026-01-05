"""A universal cycling Protocol model to convert to different formats.

A Protocol is a Pydantic model that defines a cycling protocol which can be
stored/read in JSON format.

Build a Protocol using the model objects defined in this module, e.g.:

my_protocol = Protocol(
    sample=SampleParams(name="My Sample", capacity_mAh=1.0),
    record=RecordParams(time_s=10),
    safety=SafetyParams(max_voltage_V=4.5, delay_s=1),
    method=[
        Tag(tag="longterm"),
        OpenCircuitVoltage(until_time_s=600),
        ConstantCurrent(rate_C=0.5, until_voltage_V=4.2, until_time_s=3*60*60),
        ConstantVoltage(voltage_V=4.2, until_rate_C=0.05, until_time_s=60*60),
        ConstantCurrent(rate_C=-0.5, until_voltage_V=3.0, until_time_s=3*60*60),
        Loop(loop_to="longterm", cycle_count=100),
    ],
)

Or build from a dictionary:

my_protocol = Protocol.from_dict({
    "sample": {"name": "My Sample", "capacity_mAh": 1.0},
    "record": {"time_s": 10},
    "safety": {"max_voltage_V": 4.5, "delay_s": 1},
    "method": [
        {"step": "tag", "tag": "longterm"},
        {"step": "open_circuit_voltage", "until_time_s": 600},
        ...
    ],
})

Or read from an existing JSON file:

my_protocol = Protocol.from_json("path/to/protocol.json")

A unicycler Protocol object can be converted into:
- Unicycler JSON file / dict - to_json() / to_dict()
- Neware XML file  - to_neware_xml()
- Biologic MPS settings - to_biologic_mps()
- Tomato 0.2.3 JSON file - to_tomato_json()
- PyBaMM-compatible list of strings - to_pybamm_experiment()
- BattINFO-compatible JSON-LD dict - to_battinfo_jsonld()
"""

from aurora_unicycler._core import BaseProtocol
from aurora_unicycler._formats.battinfo import to_battinfo_jsonld
from aurora_unicycler._formats.biologic import to_biologic_mps
from aurora_unicycler._formats.neware import to_neware_xml
from aurora_unicycler._formats.pybamm import to_pybamm_experiment
from aurora_unicycler._formats.tomato import to_tomato_mpg2


class Protocol(BaseProtocol):
    """Unicycler battery cycling protocol.

    Defines a battery cycling experiment, which can be converted to different formats for different
    cycler machine vendors.
    """

    # Add conversion methods to the base class
    to_neware_xml = to_neware_xml
    to_biologic_mps = to_biologic_mps
    to_tomato_mpg2 = to_tomato_mpg2
    to_battinfo_jsonld = to_battinfo_jsonld
    to_pybamm_experiment = to_pybamm_experiment
