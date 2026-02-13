`aurora-unicycler` provides a universal cycling protocol Python class.

Cycling protocols can be defined in Python or with JSON, and exported to
different formats:

  - Biologic .mps
  - Neware .xml
  - tomato 0.2.3 .json
  - PyBaMM string list
  - BattINFO .jsonld

This is particularly useful for high-throughput battery experiments, as
protocols can be programmatically defined, and sample IDs and capacities can be
attached at the last second.

We try to make the protocol clear and unambiguous, and abstract away
idiosyncrasies of the backend of different cycling protocols.

The main class in `aurora-unicycler` is the `CyclingProtocol`, which contains
the `method` - a list of steps to carry out, as well as safety and recording
parameters and limited sample details.

Under-the-hood, these are `pydantic` models, which allows for powerful
validation and type checking.
