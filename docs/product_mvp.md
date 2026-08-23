# Product MVP guide

This tranche delivers two local, file-driven products on top of the versioned
provider/session/snapshot contracts.

## Visualization

`exhaust-plume-visualize` consumes a wrapped or raw straight visual definition:

```bash
exhaust-plume-visualize \
  --config fixtures/products/visual_asset_v1.json \
  --channel core_radius_fraction \
  --output-dir visual-output
```

The command writes:

- `visual_result.json`: validated sectioned-tube result with claims,
  applicability, snapshot metadata, and provenance;
- `visual_mesh.json`: deterministic vertices, faces, bounds, and section
  channels;
- `visual_mesh.obj`: simple renderer-neutral mesh interchange;
- `visual_preview.png`: optional static preview when the `plot` extra is
  installed.

The simple straight solver can be connected through
`visual_definition_from_shock_cells` or `evaluate_shock_cell_visual`. The
adapter constructs an engineering-approximate axisymmetric envelope from
finite x/r zone geometry. It is a display product, not a conservative mesh or
a physical plume-end model.

The first analytical provider is available through the same lifecycle:

```python
from exhaust_plume import (
    StraightAnalyticalDefinition,
    StraightAnalyticalOperatingState,
    StraightAnalyticalProvider,
)

session = StraightAnalyticalProvider().create_session(
    definition=StraightAnalyticalDefinition(nozzle_radius_m=1.0),
)
snapshot = session.snapshot(
    StraightAnalyticalOperatingState(nozzle_exit=exit_state, ambient=ambient_state),
)
result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, request)
```

The analytical provider advertises only
`plume.visual.sectioned-tube@1`. Matched flow requires
`VisualSampling.maximum_axial_extent_m`; it returns a constant-radius tube
over that explicitly requested domain. Mild underexpanded and mild attached
overexpanded cases adapt the finite first-cell construction into the same
sectioned-tube result. The output is engineering-approximate and marginal at
the construction boundary; the solver does not claim a complete plume,
mixing, chemistry, radiation, signature, or ray-transfer solution.

## Signature

`exhaust-plume-signature` consumes a wrapped or raw signature table and a
request:

```bash
exhaust-plume-signature \
  --asset fixtures/products/signature_asset_v1.json \
  --request fixtures/products/signature_request_v1.json \
  --output-dir signature-output
```

The command writes:

- `signature_result.json`: wavelength-resolved directional intensity with
  status, validity, uncertainty, claims, applicability, and provenance;
- `signature_result.csv`: one row per direction and wavelength;
- `signature_spectrum.png`: intensity versus wavelength;
- `signature_angular.png`: angular cuts at selected wavelengths;
- `signature_heatmap.png`: wavelength-by-direction-cosine view.

The table is axisymmetric in direction cosine about its declared axis. Each
asset declares its interpolation policy: wavelength supports `linear`,
`log-linear`, `nearest`, or `exact-only`; direction cosine supports `linear`,
`nearest`, or `exact-only`. A table may also declare time nodes with
`linear`, `nearest`, or `exact-only` selection. Static tables ignore snapshot
time; time-varying tables require the prescribed-transient claim, for example:

Here `log-linear` interpolates the logarithm of the stored value against the
axis coordinate and therefore requires strictly positive bracketing values.

```bash
exhaust-plume-signature \
  --asset fixtures/products/signature_time_asset_v1.json \
  --request fixtures/products/signature_request_v1.json \
  --time-s 0.5 \
  --time-model prescribed_transient \
  --no-plots
```

The default extrapolation policy rejects wavelength, angular, and temporal
requests outside the declared domains. Explicit `--allow-extrapolation`
marks the result marginal and emits a warning. Exact-only policies still
reject non-node requests even when extrapolation is enabled.

Signature assets may declare an `operating_point_id` plus source total pressure,
source total temperature, and ambient pressure metadata. A request can bind to
that operating-point identifier; a mismatch is rejected. Loaded files receive
a content SHA-256 in result provenance, alongside the coordinate convention,
interpolation policies, extrapolation policy, and validity domains. This is
provenance and coverage metadata, not a pressure interpolation model.

The transient fixture demonstrates a separate low-ambient-pressure operating
point (`0.01 Pa`) as a tabulated case. It is not a rarefied/atomistic transport
model or a physical claim about exact vacuum behavior.

This MVP consumes supplied table values. It does not generate spectral values
from thermodynamic state, perform radiation transport, apply atmospheric or
optical effects, or model an imaging detector.

The separate `exhaust-plume-validate` command runs the declared nozzle/plume
validity matrix. It is the current gate for varied throat areas, area ratios,
gamma/temperature points, and finite atmospheric-to-near-vacuum ambient
pressures. Its results do not elevate the visual or signature claims to
validated physics.

The first-MVP regression fixture uses the physically explicit relation
`p0/pe = (1 + (gamma-1) Me^2/2)^(gamma/(gamma-1))` to generate matched,
mild-underexpanded, mild-overexpanded, and strong-overexpanded cases. Legacy
total-pressure examples remain regression anchors and are not silently
reclassified as new validation fixtures.

## Verification boundary

Both commands are deterministic and package with the core library. PNG output
uses the optional plotting dependency; JSON/CSV/OBJ output does not. The
resolved ray-transfer/FPA surface remains contract-only, and CPU/GPU
acceleration, curved or rotor-washed providers, thermochemistry, chemistry,
and advanced shock topology remain excluded. Exact vacuum, rarefied/atomistic
flow, physical spectroscopy, radiation transport, and detector modeling also
remain excluded.
