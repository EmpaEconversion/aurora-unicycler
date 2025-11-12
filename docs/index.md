`aurora-unicycler` defines a universal battery cycling protocol that can be
exported to different formats.

## Features
- Define a cycling protocol based on a Python Pydantic model, with validation
- Save a unicycler protocol as a human-readable .json
- Export protocols into different formats:
  - Biologic .mps
  - Neware .xml
  - tomato 0.2.3 .json
  - PyBaMM string list
  - BattINFO .jsonld

This is particularly useful for high-throughput battery experiments, as
protocols can be programmatically defined, and sample IDs and capacities can be
attached at the last second.
