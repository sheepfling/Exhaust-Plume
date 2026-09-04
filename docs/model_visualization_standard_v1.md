# Five-lane model visualization standard v1

Status: active evaluation standard.

The visualization product is a way to inspect plume-model outputs. It is not a
new solver, a replacement for the three product contracts, or a validation
claim. Every model lane is adapted to the existing
`plume.visual.sectioned-tube@1` contract, while the evaluation bundle retains
the extra geometry and provenance needed to inspect the source model.

## Standard bundle

`exhaust_plume.products.model_visualization` exposes
`StandardizedModelVisualization` and the adapter
`standardize_model_visualization(result)`. A bundle contains:

- an explicit lane ID and model version;
- the canonical oriented sectioned-tube definition;
- unit-bearing section channels;
- optional 2-D polygon fields for regions/cells;
- named 3-D paths for centerlines, shock boundaries, ambient boundaries, and
  other overlays;
- source status, applicability, diagnostics, warnings, and an explicit claim
  ceiling.

`render_model_visualization_gallery(bundle, output_dir)` is the static
evaluation entry point for this bundle shape. Its
`ModelVisualizationGallerySpec` is bound to the complete bundle digest and
selects a station, field/channel, and named paths without changing the source
bundle. The gallery emits JSON plus optional 3-D, orthographic, channel, and
field/path views; it does not create a provider result or a validation claim.

`render_model_visualization_gallery_set(bundles, output_dir)` is the
five-lane acceptance entry point. It requires exactly one bundle for each
declared lane and writes one independent sub-gallery plus manifest per lane,
along with a top-level `model_gallery_set_manifest.json`. The top-level file is
navigation and completeness evidence only: it preserves each bundle digest,
view-spec digest, provenance, and claim ceiling and never merges model fields
or promotes a lower-fidelity lane.

`standardize_all_model_visualizations` requires exactly one result for each of
the five lane IDs. `evaluate_standardized_model_visualization` runs the
sectioned-tube definition through the existing canonical v1 provider path and
copies the lane, fidelity, validation, and promotion metadata into result
provenance. No new product capability is added.

## Five lanes

| Lane | Common display | Extra view data | Claim ceiling |
| --- | --- | --- | --- |
| `shock-cell-basic-v1` | Fast straight sectioned tube with radius and flow channels | Finite axisymmetric zone polygons with temperature, pressure, density, and Mach | Engineering-approximate visualization; no radiation or detector claim |
| `shock-cell-reduced-order-v1` | Sectioned tube across resolved and reduced-order cell stations | Cell/envelope polygons with pressure and Mach; calibration identity | Calibrated engineering approximation; downstream cells are not resolved MOC |
| `straight-integral-v1` | Straight top-hat tube with conserved-flow channels | Upper/lower boundaries and interval polygons | Supporting/reference integral display; endpoint is a requested domain limit |
| `washed-integral-v1` | Rotation-minimizing swept tube along the curved centerline | 3-D centerline path and curvature/entrainment/mixing channels | Curved integral supporting lane; no automatic spectral or ray-transfer claim |
| `planar-moc-primitives-v1` | Projected sectioned-tube envelope for linked comparison | Retained planar cell polygons plus shock, ambient, centerline, and incoming-frontier paths | Research/reference numerical display; production promotion remains blocked |

The last lane is deliberately two-part. The planar field is the source
geometry. The sectioned tube is only a comparison envelope so that a common
viewer can link the MOC result to the other four lanes. It must not be read as
an axisymmetric MOC solution.

## Required views

The standard viewer should provide the following linked views for every
bundle:

1. A 3-D sectioned-tube overview with frame, model lane, fidelity, and claim
   ceiling visible.
2. XY, XZ, and YZ centerline projections, with a station selector and local
   ellipse/frame inspector.
3. One axial line plot per declared section channel, including its unit and
   semantic description.
4. Region/cell polygons, when supplied, with a selectable scalar channel and
   an invalid-sample mask. A missing value remains missing; it is never drawn
   as zero.
5. Named boundary-path overlays. For MOC, the shock boundary, ambient
   pressure boundary, centerline reflection, and incoming frontier must be
   independently togglable.
6. A diagnostics/claims panel showing source status, applicability, model
   fidelity, validation level, promotion gates, warnings, and the exact view
   settings.

The existing `VisualizationSpec` remains the source-bound view-state contract
for canonical product results. The five-lane gallery-set wrapper adds
navigation and per-lane panel selection around the bundle specs; it retains one
source digest and one provenance record per lane rather than merging results
into a new physical product.

## Validation gates

The adapter layer checks finite coordinates, positive section radii, monotone
arc length, channel alignment, polygon shape, field-channel alignment, and
JSON-safe diagnostics. Focused tests cover all five lanes, canonical result
evaluation, exact lane-set enforcement, MOC boundary retention, and masked
field values.

These checks validate visualization integrity only. They do not promote the
reduced-order or MOC lanes. The MOC bundle exposes the solver's production
gates, including canonical free-boundary, independent Euler, refinement, and
external-validation gates, without changing them.

## Mission-time visualization

`MissionTimeline` turns declared trajectory and vehicle state into immutable
time samples. `MissionVisualizationEvaluator` resolves a standardized bundle
at each sample and emits the canonical `plume.visual.sectioned-tube@1`
product with `time_model=prescribed_transient`. Its snapshot preserves the
mission time, source pose, dynamic-state digest, and ambient-state digest.

This path applies to all five lanes. It does not claim that a static bundle
will change solely because its timestamp changed: the caller-owned
`visualization_at(state)` resolver must run or retrieve the appropriate flow
model for the scheduled altitude, throttle, nozzle condition, and chemistry
assumptions. The visual request's `output_frame_id` remains the bundle's local
support frame; source location and attitude are carried in snapshot metadata
for a renderer or downstream world-frame composition step.
