<h1 align="center">
  <img src="https://github.com/user-attachments/assets/e904058b-bf9a-435c-aaa0-4ed4f2fc09f8" width="500" align="center" alt="aurora-biologic logo">
</h1>

<br>

[![Docs](https://img.shields.io/badge/docs-gh--pages-blue.svg)](https://empaeconversion.github.io/aurora-unicycler/)
[![PyPI version](https://img.shields.io/pypi/v/aurora-unicycler.svg)](https://pypi.org/project/aurora-unicycler/)
[![License](https://img.shields.io/github/license/empaeconversion/aurora-unicycler?color=blue)](https://github.com/empaeconversion/aurora-unicycler/blob/main/LICENSE)
[![Python Versions](https://img.shields.io/pypi/pyversions/aurora-unicycler.svg)](https://pypi.org/project/aurora-unicycler/)
[![Checks](https://img.shields.io/github/actions/workflow/status/empaeconversion/aurora-unicycler/test.yml)](https://github.com/EmpaEconversion/aurora-unicycler/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/codecov/c/github/empaeconversion/aurora-unicycler)](https://app.codecov.io/gh/EmpaEconversion/aurora-unicycler)


A universal battery cycling protocol that can be exported to different formats.

See the [docs](https://empaeconversion.github.io/aurora-unicycler/) for more details.

## Features
- Define a cycling protocol in Python or JSON
- Export the protocol to different formats
  - Biologic .mps
  - Neware .xml
  - tomato 0.2.3 .json
  - PyBaMM string list
  - BattINFO .jsonld

This is particularly useful for high-throughput battery experiments, as protocols can be programmatically defined, and sample IDs and capacities can be attached at the last second.

Check out our standalone APIs for controlling cyclers with Python or command line:
 - [`aurora-biologic`](https://github.com/empaeconversion/aurora-biologic)
 - [`aurora-neware`](https://github.com/empaeconversion/aurora-neware)

We also have a full application with a GUI, including a graphical interface to create these protocols:
- [`aurora-cycler-manager`](https://github.com/empaeconversion/aurora-cycler-manager)

## Installation

Install on Python >3.10 with
```
pip install aurora-unicycler
```

## Quick start

Define a protocol using Python
```python
from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    Loop,
    Protocol,
    RecordParams,
    SafetyParams,
    Tag,
)

my_protocol = Protocol(
    record = RecordParams(
        time_s=10,
        voltage_V=0.1,
    ),
    safety = SafetyParams(
        max_voltage_V=5,
        min_voltage_V=0,
        max_current_mA=10,
        min_current_mA=-10,
    ),
    method = [
        Tag(
            tag="my_tag",
        ),
        ConstantCurrent(
            rate_C=0.5,
            until_voltage_V=4.2,
            until_time_s=3*60*60,
        ),
        ConstantVoltage(
            voltage_V=4.2,
            until_rate_C=0.05,
            until_time_s=60*60,
        ),
        ConstantCurrent(
            rate_C=-0.5,
            until_voltage_V=3.5,
            until_time_s=3*60*60,
        ),
        Loop(
            loop_to="my_tag",
            cycle_count=100,
        )
    ]
)
```

You can also create a protocol from a python dictionary or JSON - you will not get type checking in an IDE, but it will still validate at runtime.
```python
my_protocol = Protocol.from_dict({
    "record": {"time_s": 10, "voltage_V": 0.1}
    "safety": {"max_voltage_V": 5}
    "method": [
        {"step": "open_circuit_voltage", "until_time_s": 1},
        {"step": "tag", "tag": "tag1"},
        {"step": "constant_current", "rate_C": 0.5, "until_voltage_V": 4.2},
        {"step": "constant_voltage", "voltage_V": 4.2, "until_rate_C": 0.05},
        {"step": "constant_current", "rate_C": -0.5, "until_voltage_V": 3.0},
        {"step": "loop", "loop_to": "tag1", "cycle_count": 100},
    ],
})
```
```python
my_protocol = Protocol.from_json("path/to/file.json")
```

You can then export the protocol to different formats, e.g.
```python
my_protocol.to_biologic_mps(
    sample_name="test-sample",
    capacity_mAh=45,
    save_path="some/location/settings.mps",
)

my_protocol.to_neware_xml(
    sample_name="test-sample",
    capacity_mAh=45,
    save_path="some/location/protocol.xml",
)

my_protocol.to_battinfo_jsonld(
    capacity_mAh=45,
    include_context=True,
    save_path="some/location/protocol.jsonld",
)
```

See the [docs](https://empaeconversion.github.io/aurora-unicycler/) for more details and the full API reference.

## Contributors

- [Graham Kimbell](https://github.com/g-kimbell)

## Acknowledgements

This software was developed at the Laboratory of Materials for Energy Conversion at Empa, the Swiss Federal Laboratories for Materials Science and Technology, and supported by funding from the [IntelLiGent](https://heuintelligent.eu/) project from the European Union’s research and innovation program under grant agreement No. 101069765, and from the Swiss State Secretariat for Education, Research, and Innovation (SERI) under contract No. 22.001422.

<img src="https://github.com/user-attachments/assets/373d30b2-a7a4-4158-a3d8-f76e3a45a508#gh-light-mode-only" height="100" alt="IntelLiGent logo">
<img src="https://github.com/user-attachments/assets/9d003d4f-af2f-497a-8560-d228cc93177c#gh-dark-mode-only" height="100" alt="IntelLiGent logo">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="https://github.com/user-attachments/assets/1d32a635-703b-432c-9d42-02e07d94e9a9" height="100" alt="EU flag">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="https://github.com/user-attachments/assets/cd410b39-5989-47e5-b502-594d9a8f5ae1" height="100" alt="Swiss secretariat">
