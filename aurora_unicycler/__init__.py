"""A universal cycling protocol which can be converted to different formats.

Create a CyclingProtocol object directly, or create from a dict or JSON file.

Convert to different formats e.g. `.to_neware_xml()` or `to_biologic_mps()`.

"""

import warnings

from ._core import (
    ConstantCurrent,
    ConstantVoltage,
    ImpedanceSpectroscopy,
    Loop,
    OpenCircuitVoltage,
    ProtocolConversionWarning,
    ProtocolMethodWarning,
    RecordParams,
    SafetyParams,
    SampleParams,
    Step,
    Tag,
    VoltageScan,
)
from .protocol import (
    CyclingProtocol,
    Protocol,
)
from .version import __version__

# Warn on every occurrence rather than once per call
warnings.simplefilter("always", ProtocolMethodWarning, append=True)

__all__ = [
    "ConstantCurrent",
    "ConstantVoltage",
    "CyclingProtocol",
    "ImpedanceSpectroscopy",
    "Loop",
    "OpenCircuitVoltage",
    "Protocol",
    "ProtocolConversionWarning",
    "ProtocolMethodWarning",
    "RecordParams",
    "SafetyParams",
    "SampleParams",
    "Step",
    "Tag",
    "VoltageScan",
    "__version__",
]
