With a `Protocol` object, use `to_battinfo_jsonld()`

```python
jsonld_string = my_protocol.to_battinfo_jsonld(
    capacity_mAh=45,
    include_context=True,
    save_path="some/location/protocol.jsonld",
)
```

This returns a JSON-LD string, and optionally saves to a .jsonld file.

`include_context` adds a `@context` property to the root of the JSON.
