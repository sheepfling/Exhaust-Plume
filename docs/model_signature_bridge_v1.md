# Model-to-signature bridge v1

The flow model and the signature product remain separate contracts. A flow
result containing temperature, pressure, or a visual envelope does not contain
spectral source radiance or optical depth. The bridge therefore requires an
explicit `GrayRadiationProfile` (homogeneous),
`SectionedGrayRadiationProfile` (one source/absorption spectrum per straight
support section), or `LineRadiationProfile` (an explicit LTE line source with
caller-owned optical depths). Every profile records the flow lane in
Signature provenance.

`GrayRadiationProfile.from_blackbody(...)` supplies an auditable thermal
continuum source using the SI Planck law and a caller-supplied gray
absorption spectrum. This is a physically grounded source-term primitive, not
a chemistry or line-by-line radiation model; its Signature output remains
gray-approximate and non-production until the corresponding source and
measurement validation gates are accepted.

`SectionedGrayRadiationProfile.from_blackbody(...)` applies the same explicit
Planck source construction at each axial support section. The transfer
provider splits each ray chord at the support-section planes and composes the
result in near-to-far ray order. It is still a piecewise-homogeneous gray
approximation: it does not infer temperature, species, or absorption from a
flow lane, and it does not enable curved-flow or planar-MOC transport.

`LineRadiationProfile` supplies the next physical source-term seam. It uses an
LTE Planck source and sums normalized wavelength-domain Voigt profiles from
explicit `SpectralLine` optical-depth primitives. `SpectralLine.from_thermal_width(...)`
can derive Doppler width from an explicitly supplied temperature and molecular
mass, but line populations, chemical composition, pressure broadening data,
and non-LTE effects remain caller-owned. The bridge labels this path
`radiation=spectral_engineering`; it remains non-production until source and
measurement validation gates pass.

## Lane matrix

| Flow lane | Current signature path | Status | Ceiling |
| --- | --- | --- | --- |
| `shock-cell-basic-v1` | Straight sectioned support + explicit gray or LTE line profile + orthographic ray integration | Ready with profile | Gray approximate or spectral engineering; visual model remains low-order |
| `shock-cell-reduced-order-v1` | Same bridge | Ready with profile | Gray approximate or spectral engineering; downstream train remains calibrated/reduced-order |
| `straight-integral-v1` | Same bridge | Ready with profile | Gray approximate or spectral engineering; top-hat integral geometry is not resolved radiation |
| `washed-integral-v1` | Isolated `plume.curved-gray-ray-transfer` path provider | Gray/line engineering only; production claim blocked | No resolved curved-flow radiation, chemistry, atmosphere, detector, or FPA claim |
| `planar-moc-primitives-v1` | Requires planar field/ray transport | Blocked | The sectioned-tube envelope is illustrative only |

The four supported lanes produce the canonical
`plume.signature.spectral-radiant-intensity@1` result through
`evaluate_model_signature`. Gray profiles declare
`radiation=gray_approximate`; line profiles declare
`radiation=spectral_engineering`. Both declare `derivation=adapted` and
`production_claim_allowed=false`. Neither path is a chemical-population,
atmospheric-path, detector, or focal-plane-array prediction.

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

For a prescribed axial thermal profile, use the sectioned form and provide
exactly one row per adjacent support-center pair:

```python
from exhaust_plume.products import SectionedGrayRadiationProfile

sectioned_profile = SectionedGrayRadiationProfile.from_blackbody(
  wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
  temperatures_K=(2200.0, 2050.0, 1900.0),
  absorption_coefficient_per_m_by_section=(
    (0.4, 0.5, 0.6),
    (0.35, 0.45, 0.55),
    (0.3, 0.4, 0.5),
  ),
  profile_id='caller-owned-sectioned-gray-profile-v1',
)
```

For an explicit LTE line source, provide the line optical-depth primitives
and use the same transport entry point:

```python
from exhaust_plume.products import LineRadiationProfile, SpectralLine

line_profile = LineRadiationProfile(
  wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
  lines=(SpectralLine.from_thermal_width(
    center_wavelength_m=2.0e-6,
    integrated_optical_depth_m=4.0e-7,
    temperature_K=1_200.0,
    molecular_mass_kg=4.65e-26,
    label='caller-owned-line-v1',
  ),),
  source_temperature_K=1_200.0,
  path_length_m=1.0,
  profile_id='caller-owned-lte-line-profile-v1',
)
```

This profile is a source/opacity model, not a chemistry solver. Its line
strength and pressure-broadening inputs must be supplied and versioned by the
caller; the provider does not infer them from plume temperature or geometry.

The optical profile is caller-owned and is never inferred from the flow
channels. Straight variable-radius supports use the existing conservative
piecewise-capsule intersection policy. A sectioned profile is restricted to a
straight support and is split by axial section planes. Curved and planar models
fail with a typed `ModelSignatureBlockedError` until their transport providers
are implemented.

Atmospheric transmission is a separate, caller-owned measurement operator. Use
`AtmosphericPathLayer` and `compose_atmospheric_path_layers` when a path must
be represented as explicit near-observer-to-far-source homogeneous layers;
`apply_atmospheric_path_layers` then combines the source spectrum with the
composed transmittance and path radiance. Layer source functions and absorption
coefficients must be supplied in the measurement space. The operator does not
infer altitude-dependent temperature, composition, scattering, or chemistry,
and therefore does not raise the Signature product's physical or production
claim ceiling.

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
product plus a signature when the lane is transport-ready. For planar-MOC
samples, it returns the visual product and a typed blocked signature assessment
rather than fabricating a straight-ray result. Curved integral samples use the
separate gray path provider, but remain approximate and non-production.

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

`MissionSignatureEvaluator.query_at(...)` is the arbitrary-time point-query
seam. It first resolves the prescribed mission state and re-runs the explicit
flow and optical callbacks at that state, then selects one direction and
wavelength from the resulting Signature. It therefore supports a moving or
throttling vehicle without interpolating neighboring Signature values. The
returned query retains the exact result ID, status, validity, uncertainty, and
spectral radiant-intensity units.

## Mission-time FPA composition

`MissionFpaEvaluator` is the separate downstream composition seam for a
time-varying ray-transfer result. Its `ray_transfer_at` callback returns the
explicit wavelength axis and the provider
`SpectralRayTransferResult` for the requested `MissionState`; camera pixel
geometry, detector response, exposure, and optional ADC policy are supplied by
their own callbacks. The adapter requires the ray snapshot time and source
pose to exactly match the timeline sample, then runs
`integrate_spectral_ray_result_to_fpa` and optionally
`digitize_expected_electrons`. `sample_at` returns the source-bound
`FpaVisualizationInput`, while `project_at` resolves the renderer-neutral FPA
view.

This is an instrument-bound expected-electron/expected-ADC composition only.
It does not infer camera pointing, atmosphere, chemistry, noise realizations,
detection decisions, or measured counts, and it does not turn the FPA boundary
into a public plume provider. The far-field Signature result and the ray
transfer consumed by the FPA remain separate products with separate claim
ceilings.
