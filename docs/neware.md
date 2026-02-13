With a `CyclingProtocol` object, use `to_neware_xml()`

```python
xml_string = my_protocol.to_neware_xml(
    sample_name="test-sample",
    capacity_mAh=45,
    save_path="some/location/protocol.xml",
)
```

This returns an XML string, and optionally saves to a .xml file.

This has been tested on BTS8.0.0.
