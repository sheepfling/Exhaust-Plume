# FPA detector-frame contract v1

`plume.fpa.detector-frame@1` is the typed result boundary for the downstream
Focal-Plane Array product. It serializes deterministic detector-operator
outputs with their ray source, time support, pixel geometry, and detector
configuration.

This contract remains separate from the `plume.image.spectral-radiance@1`
per-pixel spectral-radiance result. That supporting result contains
source-only radiance before detector response and is derived from exact ray
samples and pixel geometry. Expected detector electrons do not satisfy that
quantity; the two contracts preserve the pre-detector and detector stages.
The [spectral-radiance-image contract](spectral_radiance_image_contract_v1.md)
defines its aggregation and invalid-pixel behavior.

## Result contents

The result binds to the exact `plume.optical.spectral-ray-transfer@1` source
through provider, session, snapshot, frame, and content digest. It records the
source evaluation time or the sampled times used by a mission exposure. SHA-256
digests identify the exact pixel geometry and full FPA operator inputs. A
separate `measurement_operator_sha256` binds the source-independent
camera geometry, spectral axis, detector response, exposure, and temporal
sample schedule. This lets measured-frame comparison require the same
measurement operator without confusing its identity with a digest that
includes predicted radiance values. The frame contract recomputes this digest
from its typed detector and geometry fields.

Pixel coordinates use zero-based `(row, column)` indexing. The image layers
have these meanings and units:

| Layer | Meaning | Unit |
| --- | --- | --- |
| `expected_electrons_e` | Expected signal plus dark-current contribution | electrons |
| `dark_electrons_e` | Dark-current contribution, included in expected electrons | electrons |
| `noise_variance_e2` | Expected shot-noise plus read-noise variance | electrons squared |
| `validity_mask` | Whether the detector value is valid for this pixel | boolean |
| `digitized_counts` | Optional deterministic ADC expectation | counts |
| `saturated_mask` | Optional ADC clipping indicator | boolean |

The result includes the spectral detector response, declared camera/optics
metadata when present, exposure duration, atmosphere-path lineage, and the
digitization policy when ADC counts are included. For a sampled mission
exposure, `source_times_s` must match the retained source provenance and the
exposure duration must match the sample interval.

Camera angular geometry is optional and is derived only when the camera
declares `pinhole-rectilinear-v1`. In that case the frame records the
camera-local on-axis pixel IFOV and sensor FOV in radians, recomputed from
focal length, pixel pitch, principal point, and frame dimensions. Without
that projection identity the frame leaves IFOV/FOV absent and preserves the
caller-supplied ray mapping. These angles describe ideal geometric coverage;
their calculation does not add a point-spread function (PSF), aberration, or a
calibrated optical response.

An optional discrete PSF may be declared in the camera-optics metadata. The
frame carries its model ID, exact normalized kernel, digest, spectral scope,
and edge policy. The current operator is achromatic and applies the kernel to
expected signal electrons before adding dark current and read-noise variance.
Its fixed `mask-incomplete-support` policy does not renormalize at sensor
edges: an output pixel is invalid if any nonzero kernel tap falls outside the
sensor or touches an unobserved or invalid source pixel. This is an explicit
local operator, not optical calibration; it does not model chromatic blur or
aberrations, and it does not generate camera rays.

## Creating a frame

The public adapter is `exhaust_plume.api.v1.to_fpa_detector_frame`. It requires
the source-bound FPA visualization input and the exact `FpaPixelGeometry`
used by the pixel operator. `MissionFpaSample` and `MissionFpaExposure` expose
`to_detector_frame_result()` convenience methods that preserve their exact
snapshot or exposure times.

The JSON Schema, synthetic contract example, and digest manifest are generated
with:

```bash
PYTHONPATH=src python3 scripts/generate_fpa_detector_contract_assets.py
```

The generated schema is
[`fpa_detector_frame_v1.schema.json`](../schemas/fpa_detector_frame_v1.schema.json)
and the example is
[`fpa_detector_frame_v1.json`](../fixtures/contracts/fpa_detector_frame_v1.json).
Their SHA-256 digests are recorded in
[`fpa_detector_contract_manifest_v1.json`](../schemas/fpa_detector_contract_manifest_v1.json).
The example checks serialization and contract validation; it is not detector
validation data.

## Claim boundary

The frame represents expected electrons and deterministic ADC counts. It does
not represent a noise realization, detection decision, measured detector
image, or provider-validated result. FPA source eligibility and camera/detector
acceptance still require source-bound observations with disjoint calibration
and validation data. The fast basic shock-cell solver remains ineligible for
FPA unless those gates specifically qualify it.
