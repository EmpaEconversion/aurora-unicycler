With a `Protocol` object, use , use `to_pybamm_experiment()`

```python
pybamm_list = my_protocol.to_pybamm_experiment()
```

This creates a list of strings which can be used in PyBaMM.

Note: if you serialise this as a text file, it can be very large. A cycle in
PyBaMM is not stored with e.g. 'Cycle 1000 times' - the cycle itself is repeated
1000 times. It is better to keep this as a Python object where possible.
