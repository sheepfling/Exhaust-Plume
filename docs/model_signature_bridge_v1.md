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
