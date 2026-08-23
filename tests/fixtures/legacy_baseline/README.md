# Legacy baseline fixtures

These fixtures preserve reproducible outputs from the pre-provider alpha API.
They are migration anchors only. They must not be described as corrected
physics, calibration, or external validation data.

The representative case was generated with:

```python
calculatePlumeZones(
    nozzle_mach=4.13,
    nozzle_total_temperature=2000.0,
    nozzle_total_pressure=69.0 * 101325.0,
    nozzle_radius=1.0,
    atmospheric_pressure=101325.0,
    gamma=1.33,
    num_expansion_lines=2,
    num_compression_lines=1,
    num_plumes=1,
)
```

The corresponding output is in
`representative_underexpanded_case.json`. The fixture intentionally records
only stable scalar summaries rather than freezing the full approximate zone
geometry.
