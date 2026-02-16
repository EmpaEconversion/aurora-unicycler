With a `CyclingProtocol` object, use `to_biologic_mps()`

```python
mps_string = my_protocol.to_biologic_mps(
    sample_name="test-sample",
    capacity_mAh=45,
    save_path="some/location/settings.mps",
)
```

This returns a Biologic MPS settings string, and optionally saves a .mps file.

This has been tested on MPG2 cyclers with EC-lab 11.52 and 11.61.

!!! warning "Important!"
    If you save the string to a file yourself, use `cp1252` encoding.
    `UTF-8` (default) will not save μ (micro) symbols correctly.
    EC-lab can misinterpret this as m (milli) which could be dangerous!

### Notes

 - EC-lab only has one absolute current limits. If an asymmetric limit is set
in the protocol the larger absolute value is used. E.g. `-5 mA` to `10 mA` 
will be set as `|I| < 10 mA`.

- EC-lab can only change current range between steps after an open circuit
voltage step.

- Change the global voltage range with `range_V = (x,y)`, by default this is
0-5 V.
