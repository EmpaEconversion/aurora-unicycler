## Sample parameters

`SampleParams` contains very basic information about the sample - a name and
the capacity used for calculating C-rates.
These can also be set on protocol export, so a single protocol can be used for
many different samples.

## Safety parameters

`SafetyParams` defines the safety limits passed to cyclers - max and min
currents and voltages, and/or a capacity limit. `delay_s` is how long a limit
must be exceeded before the cycler cancels the experiment. Biologic caps this
at 1 s.

Note that for current limits, Biologic only gives one absolute current limit,
it uses the larger of `abs(min_current_mA)` and `abs(max_current_mA)` for both
directions. Neware accepts two separate values, and the minimum current should
be negative if used (otherwise the test may cancel itself immediately).

## Recording parameters

`RecordParams` can be set on the base protocol, or on a particular step.

Parameters on a step will merge with protocol parameters, and override on
conflicts. E.g. the protocol has `{"time_s": 10, "voltage_V": 0.1}` and a step
has `{"time_s": 1, "current_mA": 0.2}`, then the resulting parameters after
merge are `{"time_s": 1, "voltage_V": 0.1, "current_mA": 0.2}`.

Not every condition applies to every step, e.g. a constant voltage step will
not apply the `voltage_V` recording condition.

If no steps have usable recording conditions, converting to a real cycler
format will error. PyBaMM and BattINFO do not need recording conditions.

## Method

The method is a list of steps: `OpenCircuitVoltage`, `ConstantCurrent`,
`ConstantVoltage`, `ImpedanceSpectroscopy`, `VoltageScan`, `Loop` and `Tag`.
See the [API Reference](api.md) for the parameters of each step.

### Loops

The best way to define loops is by using tags:
```python
method = [
    Tag(tag="my tag"),
    ...  # some steps
    Loop(loop_to="my tag", cycle_count=100),
]
```

`cycle_count` defines the total number of times that loop is performed. A cycle
count of 100 means it will jump back to the tag 99 times.

You can have any number of different tags.

Nesting loops works, and the outer loop resets the inner loop counter:
```python
method = [
    Tag(tag="recovery"),
    Tag(tag="longterm"),
    ...  # normal cycling
    Loop(loop_to="longterm", cycle_count=25),
    ...  # recovery step
    Loop(loop_to="recovery", cycle_count=4),
]
```
This will do 100 (25*4) normal cycles, with 4 recovery steps.

Intersecting loops are ambiguous and not allowed:
```python
method = [
    Tag(tag="A"),
    ...
    Tag(tag="B"),
    ...
    Loop(loop_to="A", cycle_count=10),
    ...
    Loop(loop_to="B", cycle_count=10),
]
```

Looping to a 1-indexed step is supported
(`Loop(loop_to=1, cycle_count=100)` loops to the 1st step in the list), but
it is user-error-prone and not recommended. Tags count as steps in this
indexing, e.g. in `[Tag, OpenCircuitVoltage, ConstantCurrent, Loop(loop_to=2)]`
the loop goes back to the `OpenCircuitVoltage` step.

**Looping to tags is strongly recommended.** This avoids indexing confusion, and
allows you to move steps around without having to recalculate loop conditions.

Tags only exist in the unicycler protocol, the tag text is not kept in e.g.
EC-Lab mps or Neware xml files.
