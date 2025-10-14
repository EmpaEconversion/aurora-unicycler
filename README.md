<p align="center">
  <img src="https://github.com/user-attachments/assets/1136509f-c5ae-4ee0-b48d-535494706006#gh-light-mode-only" width="500" align="center" alt="aurora-biologic logo">
  <img src="https://github.com/user-attachments/assets/e224fa59-dec7-4347-9c24-fc4c9f62380a#gh-dark-mode-only" width="500" align="center" alt="aurora-biologic logo">
</p>

<br>

## Overview
`aurora-unicycler` defines a universal battery cycling protocol that can be exported to different formats.

## Features
- Define a cycling protocol based on a Python Pydantic model, with validation
- Save a unicycler protocol as a human-readable .json
- Export protocols into different formats:
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

## Usage

### Making a protocol
Define a protocol using Python
```python
from aurora-unicycler import *

my_protocol = Protocol(
    measurement = MeasurementParams(
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
my_protocol = Protocol.from_dict(
    {
        "measurement": {"time_s": 10, "voltage_V": 0.1}
        "safety": {"max_voltage_V": 5}
        "method": [
            {"step": "open_circuit_voltage", "until_time_s": 1},
            {"step": "tag", "tag": "tag1"},
            {"step": "constant_current", "rate_C": 0.5, "until_voltage_V": 4.2},
            {"step": "constant_voltage", "voltage_V": 4.2, "until_rate_C": 0.05},
            {"step": "constant_current", "rate_C": -0.5, "until_voltage_V": 3.0},
            {"step": "loop", "loop_to": "tag1", "cycle_count": 100},
        ],
    ]
)
```
```python
my_protocol = Protocol.from_json("path/to/file.json")
```

### Converting a protocol

Once you have a protocol object, you can optionally attach a sample name and capacity and convert to other formats.

- Biologic MPS settings, tested on MPG2 cyclers with EC-lab 11.52 and 11.61:
```python
mps_string = my_protocol.to_biologic_mps(
    sample_name="test-sample",
    capacity_mAh=45,
    save_path="some/location/settings.mps",
)
```

- Neware XML, tested on BTS8:
```python
xml_string = my_protocol.to_neware_xml(
    sample_name="test-sample",
    capacity_mAh=45,
    save_path="some/location/protocol.xml",
)
```

- Tomato, tested on 0.2.3:
```python
json_string = my_protocol.to_tomato_json(
    sample_name="test-sample",
    capacity_mAh=45,
    save_path="some/location/protocol.json",
)
```

- PyBaMM experiment (list of strings):
```python
pybamm_list = my_protocol.to_pybamm_experiment()
```

- BattINFO JSON-LD:
```python
jsonld_string = my_protocol.to_battinfo_jsonld(
    capacity_mAh=45,
    include_context=True,
    save_path="some/location/protocol.jsonld",
)
```

## Contributors

- [Graham Kimbell](https://github.com/g-kimbell)

## Acknowledgements

This software was developed at the Laboratory of Materials for Energy Conversion at Empa, the Swiss Federal Laboratories for Materials Science and Technology, and supported by funding from the [IntelLiGent](https://heuintelligent.eu/) project from the European Union’s research and innovation program under grant agreement No. 101069765, and from the Swiss State Secretariat for Education, Research, and Innovation (SERI) under contract No. 22.001422.

<img src="https://github.com/user-attachments/assets/373d30b2-a7a4-4158-a3d8-f76e3a45a508#gh-light-mode-only" height="100" alt="IntelLiGent logo">
<img src="https://github.com/user-attachments/assets/9d003d4f-af2f-497a-8560-d228cc93177c#gh-dark-mode-only" height="100" alt="IntelLiGent logo">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="https://github.com/user-attachments/assets/1d32a635-703b-432c-9d42-02e07d94e9a9" height="100" alt="EU flag">&nbsp;&nbsp;&nbsp;&nbsp;
<img src="https://github.com/user-attachments/assets/cd410b39-5989-47e5-b502-594d9a8f5ae1" height="100" alt="Swiss secretariat">
