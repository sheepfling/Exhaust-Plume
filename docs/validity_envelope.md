# Simple-plume validity envelope

The branch now includes a reproducible validity assessment for the active
quasi-one-dimensional nozzle and low-order straight shock-cell path.

```bash
exhaust-plume-validate --output-dir validity-output
```

The command evaluates 15 cases:

- three equivalent circular throat areas and exit-to-throat area ratios;
- three constant-gamma gas cases (`gamma = 1.2`, `1.4`, and `1.67`) with
  total temperatures of 500 K, 800 K, and 1500 K;
- five ambient pressures: 101325 Pa, 10000 Pa, 100 Pa, 1 Pa, and 0.01 Pa.

The output is a JSON report plus a flat CSV report. Each row retains the
geometry, derived exit Mach and pressure, exit-to-ambient pressure ratio,
expansion regime, solver status, termination reason, zone count, and reasons.

## Interpretation

`inside`, `marginal`, and `outside` are applicability labels for this declared
study envelope. They are not experimental validation labels. `marginal`
includes low-order construction truncation; `outside` includes a numerical
failure or a case outside the declared finite range.

The active geometry contract is intentionally narrow:

- circular equivalent-area throat and exit sections;
- isentropic calorically-perfect gas relations;
- supersonic branch only;
- zero exit flow angle;
- no wall contour, boundary-layer, discharge-coefficient, separation, or
  non-circular shape correction.

The pressure sweep reaches a finite near-vacuum point so that the continuum
model's behavior is visible. Exact vacuum is rejected because the active ideal
gas density relation requires positive pressure. Pressures at which the
low-order solver cannot construct finite zones are reported as outside rather
than returned as plausible geometry. Rarefied or atomistic flow requires a
kinetic/Knudsen-based model and is not implemented here.

## Reference basis

The regression fixture
`tests/fixtures/validity/isentropic_reference_v1.json` checks the independent
area-Mach, static-pressure, and static-temperature relations for area ratios
2, 4, 9, and 25 at `gamma = 1.4`. These are analytical anchors, not CFD,
experiment, or certification data.

The visual adapter inherits the source solver status. It emits a marginal
engineering-approximate envelope for finite construction-boundary results and
refuses failed or empty solver results. The signature product records an
operating-point identifier and optional source/ambient pressures, but remains a
tabulated lookup product; it does not interpolate or predict spectra across
pressure and does not implement physical radiation transport.
