## Sample parameters

`SampleParams` contains very basic information about the sample - a name and
the capacity used for calculating C-rates.
These can also be set on protocol export, so a single protocol can be used for
many different samples.

## Safety parameters

`SafetyParams` defines the safety limits passed to cyclers - max and min
currents and voltages, or a capacity limit. `delay_s` determines the amount of
time a cycler has to exceed those limits before erroring.

Note that for current limits, Biologic only gives one absolute current limit,
whereas Neware accepts two values, the minimum current should be negative.


## Recording parameters

`RecordParams` can be set on the base protocol, or on a particular step.

Parameters on a step will merge with protocol parameters, and override on
conflicts. E.g. the protocol has `{"time_s": 10, "voltage_V": 0.1}` and a step
has `{"time_s": 1, "current_mA": 0.2}`, then the resulting parameters after
merge are `{"time_s": 1, "voltage_V": 0.1, "current_mA": 0.2}`.

Not every condition applies to every step, e.g. an constant voltage step will
not apply the `voltage_V` recording condition.

If no steps have usable recording conditions, converting to a real cycle type
will error.

## Method

The method is a list of steps.

### Loops

The best way to define loops is by using tags:
```
method = [
    Tag(tag="my tag"),
    ...  # some steps
    Loop(loop_to="my tag", cycle_count=100),
]
```

You can have any number of different tags and nested looping works.

`cycle_count` defines the total number of times that loop is performed. A cycle
count of 100 means it will jump back to the tag 99 times.

Looping to a 1-indexed technique is supported
(`Loop(loop_to=1, cycle_count=100)` loops to the 1st technique in the list), but
it is user-error-prone and not recommended. Looping to tags avoids indexing
confusion, and allows you to move techniques around without having to
recalculate loop conditions.

Tags only exist in the unicycler protocol, the tag text is not kept in e.g.
EC-Lab mps or Neware xml files.
