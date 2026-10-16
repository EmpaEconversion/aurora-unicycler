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

### Notes

- Neware protocols apply global and step record settings additively. With a
global `1 s` record and one step at `60 s`, that step still records every `1 s`.

- Unicycler merges step record settings onto the global ones, with the step
taking priority. With a global `1 s` and one step at `60 s`, that step records
every `60 s`.

- To keep the unicycler behaviour, if any step has its own record settings,
the export writes the merged settings on every step and leaves the Neware
global record empty.
