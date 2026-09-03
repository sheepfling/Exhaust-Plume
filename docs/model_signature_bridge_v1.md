# Model-to-signature bridge v1

The flow model and the signature product remain separate contracts. A flow
result containing temperature, pressure, or a visual envelope does not contain
spectral source radiance or optical depth. The bridge therefore requires an
explicit `GrayRadiationProfile` and records the flow lane in signature
provenance.

## Lane matrix

| Flow lane | Current signature path | Status | Ceiling |
| --- | --- | --- | --- |
| `shock-cell-basic-v1` | Straight sectioned support + explicit gray profile + orthographic ray integration | Ready with profile | Gray approximate; visual model remains low-order |
| `shock-cell-reduced-order-v1` | Same bridge | Ready with profile | Gray approximate; downstream train remains calibrated/reduced-order |
| `straight-integral-v1` | Same bridge | Ready with profile | Gray approximate; top-hat integral geometry is not resolved radiation |
| `washed-integral-v1` | Requires path-aware curved transport | Blocked | No curved ray-transfer claim |
| `planar-moc-primitives-v1` | Requires planar field/ray transport | Blocked | The sectioned-tube envelope is illustrative only |

The three ready lanes produce the canonical
`plume.signature.spectral-radiant-intensity@1` result through
`evaluate_model_signature`. The returned metadata declares
`radiation=gray_approximate`, `derivation=adapted`, and
`production_claim_allowed=false`. The result is not a chemistry, molecular
spectroscopy, atmospheric-path, detector, or focal-plane-array prediction.

## Required handoff

```python
from exhaust_plume.products import (
  GrayRadiationProfile,
  ModelSignatureSampling,
  evaluate_model_signature,
)

signature = evaluate_model_signature(
  standardized_flow_visualization,
  GrayRadiationProfile(
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    source_function_w_sr_m=(2.0, 3.0, 4.0),
    absorption_coefficient_per_m=(0.5, 1.0, 1.5),
    profile_id='caller-owned-gray-profile-v1',
  ),
  sampling=ModelSignatureSampling(
    source_to_observer_directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    transverse_sample_count=33,
  ),
)
```

The optical profile is caller-owned and is never inferred from the flow
channels. Straight variable-radius supports use the existing conservative
piecewise-capsule intersection policy. Curved and planar models fail with a
typed `ModelSignatureBlockedError` until their transport providers are
implemented.

`assess_model_signature_readiness` exposes the same decision without running
the solver, which lets product orchestration display a blocked lane rather
than silently substituting a lower-fidelity geometry.

## Mission-time evaluation

`evaluate_model_signature` accepts an explicit `time_s`, `source_pose`,
`dynamic_state`, and `ambient_state`; time and pose are retained in immutable
snapshot metadata, while the dynamic and ambient mappings are retained in its
state digests. Those fields do not alter a static flow result by themselves.
A time-varying booster must resolve a new flow visualization and optical
profile for its declared condition.

`MissionTimeline` provides the shared composition seam. The timeline is a
bounded, prescribed schedule of `MissionState` nodes. It linearly interpolates
position, attitude, geopotential altitude, throttle, and remaining propellant
mass; discrete operating-point IDs and arbitrary context mappings are held
from the lower node. A `MissionCursor` has `advance_by` and `advance_to`, but
each returns a new cursor, so old snapshots remain reproducible.

`MissionVisualizationEvaluator` emits the canonical visual product for all
five lanes. `MissionProductEvaluator` builds on it and returns that visual
product plus a signature when the lane is transport-ready. For curved integral
and planar-MOC samples, it returns the visual product and a typed blocked
signature assessment rather than fabricating a straight-ray result.

```python
from exhaust_plume.api.v1 import Pose
from exhaust_plume.products import (
  MissionProductEvaluator,
  MissionState,
  MissionTimeline,
  MissionVisualizationEvaluator,
)

timeline = MissionTimeline((
  MissionState(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world', translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    geopotential_altitude_m=0.0,
    throttle_fraction=1.0,
    remaining_propellant_mass_kg=8_000.0,
  ),
  MissionState(
    time_s=1.0,
    source_pose=Pose(
      frame_id='world', translation_m=(0.0, 0.0, 100.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    geopotential_altitude_m=100.0,
    throttle_fraction=0.95,
    remaining_propellant_mass_kg=7_990.0,
  ),
))

visualization_evaluator = MissionVisualizationEvaluator(
  timeline=timeline,
  visualization_at=flow_visualization_for_state,
  request=visual_sectioned_tube_request,
)
products = MissionProductEvaluator(
  visualization_evaluator=visualization_evaluator,
  optical_profile_at=optical_profile_for_state,
)
sample_at_t = products.sample_at(0.0)
visual_at_t = sample_at_t.visual_product
signature_at_t = products.signature_at(0.0)  # raises a typed block if unavailable
next_sample = products.evaluate_cursor(timeline.cursor_at().advance_by(0.5))
```

The evaluator returns the canonical far-field **spectral radiant-intensity**
product, not local spectral radiance or an FPA image. The source pose makes
the mission location and attitude explicit in the snapshot; the current
orthographic integration directions remain in the plume-local support frame.
The resolver callbacks are intentionally caller-owned: they are where a
trajectory/atmosphere model, throttle-to-nozzle closure, propellant depletion
model, chemistry model, and optical-property source must be connected and
validated. No such physics is inferred by the schedule adapter.
