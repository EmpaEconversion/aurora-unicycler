## With Python object

Writing the protocol using the Python objects gives the full power of type
checking and validation in your developer environment, like VSCode.
```python
from aurora_unicycler import (
    ConstantCurrent,
    ConstantVoltage,
    Loop,
    CyclingProtocol,
    RecordParams,
    SafetyParams,
    Tag,
)

my_protocol = CyclingProtocol(
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

## With dictionary

You can also create a protocol from a python dictionary - you will not get type
checking in an IDE, but it will still validate at runtime.
```python
from aurora_unicycler import CyclingProtocol

my_protocol = CyclingProtocol.from_dict({
    "record": {"time_s": 10, "voltage_V": 0.1},
    "safety": {"max_voltage_V": 5},
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

## With JSON

It is also possible to load a protocol from a JSON file.
```python
from aurora_unicycler import CyclingProtocol

my_protocol = CyclingProtocol.from_json("path/to/file.json")
```
