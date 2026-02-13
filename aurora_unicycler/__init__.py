"""A universal cycling protocol which can be converted to different formats.

Create a CyclingProtocol object directly, or create from a dict or JSON file.

Convert to different formats e.g. `.to_neware_xml()` or `to_biologic_mps()`.

"""

from ._core import (
    ConstantCurrent,
    ConstantVoltage,
    ImpedanceSpectroscopy,
    Loop,
    OpenCircuitVoltage,
    RecordParams,
    SafetyParams,
    SampleParams,
    Step,
    Tag,
)
from .protocol import (
    CyclingProtocol,
    Protocol,
)
from .version import __version__

__all__ = [
    "ConstantCurrent",
    "ConstantVoltage",
    "CyclingProtocol",
    "ImpedanceSpectroscopy",
    "Loop",
    "OpenCircuitVoltage",
    "Protocol",
    "RecordParams",
    "SafetyParams",
    "SampleParams",
    "Step",
    "Tag",
    "__version__",
]
