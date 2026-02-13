"""A universal cycling protocol model to convert to different formats.

A CyclingProtocol is a Pydantic model that defines a cycling protocol which can
be stored/read in JSON format.

Build a CyclingProtocol using the model objects defined in this module, e.g.:

my_protocol = CyclingProtocol(
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

my_protocol = CyclingProtocol.from_dict({
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

my_protocol = CyclingProtocol.from_json("path/to/protocol.json")

A unicycler CyclingProtocol object can be converted into:
- Unicycler JSON file / dict - to_json() / to_dict()
- Neware XML file  - to_neware_xml()
- Biologic MPS settings - to_biologic_mps()
- Tomato 0.2.3 JSON file - to_tomato_json()
- PyBaMM-compatible list of strings - to_pybamm_experiment()
- BattINFO-compatible JSON-LD dict - to_battinfo_jsonld()
"""

from pathlib import Path

from aurora_unicycler._core import BaseProtocol
from aurora_unicycler._formats import battinfo, biologic, neware, pybamm, tomato


class CyclingProtocol(BaseProtocol):
    """Unicycler battery cycling protocol.

    Defines a battery cycling experiment, which can be converted to different formats for different
    cycler machine vendors.
    """

    # Add conversion methods to the base class, include docstrings here so mkdocs work
    def to_battinfo_jsonld(
        self,
        save_path: Path | str | None = None,
        capacity_mAh: float | None = None,
        *,
        include_context: bool = False,
    ) -> dict:
        """Convert protocol to BattInfo JSON-LD format.

        This generates the 'hasTask' key in BattINFO, and does not include the
        creator, lab, instrument etc.

        Args:
            save_path: (optional) File path of where to save the JSON-LD file.
            capacity_mAh: (optional) Override the protocol sample capacity.
            include_context: (optional) Add a `@context` key to the root of the
                JSON-LD.

        Returns:
            Dictionary representation of the JSON-LD.

        """
        return battinfo.to_battinfo_jsonld(
            self,
            save_path,
            capacity_mAh,
            include_context=include_context,
        )

    def to_biologic_mps(
        self,
        save_path: Path | str | None = None,
        sample_name: str | None = None,
        capacity_mAh: float | None = None,
        range_V: tuple[float, float] = (0.0, 5.0),
    ) -> str:
        """Convert protocol to a Biologic Settings file (.mps).

        Uses the ModuloBatt technique.

        Note that you must add OCV steps inbetween CC/CV steps if you want the
        current range to be able to change.

        Args:
            save_path: (optional) File path of where to save the mps file.
            sample_name: (optional) Override the protocol sample name.
            capacity_mAh: (optional) Override the protocol sample capacity.
            range_V: (optional) Voltage range of instrument in volts, default 0-5 V.
                Usually capped at +- 10 V. Smaller ranges can improve resolution.

        Returns:
            mps string representation of the protocol.

        """
        return biologic.to_biologic_mps(self, save_path, sample_name, capacity_mAh, range_V)

    def to_neware_xml(
        self,
        save_path: Path | str | None = None,
        sample_name: str | None = None,
        capacity_mAh: float | None = None,
    ) -> str:
        """Convert the protocol to Neware XML format.

        Args:
            save_path: (optional) File path of where to save the xml file.
            sample_name: (optional) Override the protocol sample name. A sample
                name must be provided in this function. It is stored as the
                'barcode' of the Neware protocol.
            capacity_mAh: (optional) Override the protocol sample capacity.

        Returns:
            xml string representation of the protocol.

        """
        return neware.to_neware_xml(self, save_path, sample_name, capacity_mAh)

    def to_pybamm_experiment(self) -> list[str]:
        """Convert protocol to PyBaMM experiment format.

        A PyBaMM experiment does not need capacity or sample name.

        Returns:
            list of strings representing the PyBaMM experiment.

        """
        return pybamm.to_pybamm_experiment(self)

    def to_tomato_mpg2(
        self,
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
        return tomato.to_tomato_mpg2(self, save_path, tomato_output, sample_name, capacity_mAh)


# Old name, still supported
Protocol = CyclingProtocol
