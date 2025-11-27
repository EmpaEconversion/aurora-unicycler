With a `Protocol` object, use `to_biologic_mps()`

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