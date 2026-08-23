# MVP Product Alignment and Repository Integration

## Purpose

This note maps the plume-physics roadmap onto the versioned product contracts.
It deliberately keeps solver-private geometry and state separate from consumer
products.

The public lifecycle is:

```text
PlumeProvider.create_session() -> PlumeSession
PlumeSession.snapshot(request)  -> PlumeSnapshot
PlumeSnapshot.get_product(...)  -> one typed product
```

A provider advertises only the capabilities it can substantiate. There is no
universal result object with optional geometry, signature, and ray fields.

## Primary products

| Capability | Consumer question | Required source state |
| --- | --- | --- |
| `plume.visual.sectioned-tube@1` | What conservative/support geometry should I render? | Valid section geometry, frame, support definition, provenance |
| `plume.signature.spectral-radiant-intensity@1` | What unresolved source intensity is seen from each direction and wavelength? | Direct validated asset or a validated derivation from ray transfer |
| `plume.optical.spectral-ray-transfer@1` | What source radiance and background transmittance occur along each ray? | Optical state, spectral properties, ordered ray transfer |

The products are independent. Visual geometry cannot be promoted into a
spectral source without temperature, composition, opacity, and radiative
transfer evidence.

## Supporting products

Supporting capabilities may expose conservative or engineering data without
merging the three primary products:

```text
plume.engineering.flux-section@1
plume.spatial.support@1
plume.spatial.local-field@1
plume.spatial.axisymmetric-zone-field@1
plume.spatial.projected-area@1
plume.image.spectral-radiance@1
```

`PlumeFluxSection` is the only regime-to-regime physics handoff. It preserves
mass, vector momentum including residual pressure thrust, total energy flow,
and species mass flow. Provider-private shock zones, characteristic points,
centerline stations, CFD cells, and renderer meshes do not cross this boundary.

## Current repository classification

| Existing or planned type | Boundary classification | Product mapping |
| --- | --- | --- |
| `FlowState` | Solver-private physics state | Input to provider adapters only |
| `ZoneResult` and `ZoneCoordinates` | Shock-cell provider-private state | Future `plume.spatial.axisymmetric-zone-field@1`; optional visual adapter only after support semantics are explicit |
| `calculatePlumeZones` | Legacy direct solver entry point | Future `ShockCellAnalyticalProvider` implementation |
| `RevolvedMesh` | Renderer/private display mesh | Not a public product DTO |
| `CurvedPlumeStation` on the curved-plume branch | Washed-provider private state | Input to a sectioned-tube adapter |
| `SweptTubeMesh` on the curved-plume branch | Renderer/private mesh | Not a regime handoff or product contract |
| `AmbientStateField` | Provider-private environment dependency | Used by straight/washed providers, not exposed as a primary product |
| `PlumeFluxSection` | Neutral handoff | `plume.engineering.flux-section@1` |
| `SectionedTubeResult` | Public visual product | `plume.visual.sectioned-tube@1` |
| `SpectralRadiantIntensityResult` | Public unresolved signature | `plume.signature.spectral-radiant-intensity@1` |
| `SpectralRayTransferResult` | Public resolved optical product | `plume.optical.spectral-ray-transfer@1` |

## Provider portfolio

```text
PrescribedSectionedTubeProvider
StraightIntegralPlumeProvider
WashedIntegralPlumeProvider
ShockCellAnalyticalProvider
ShockToWashedCompositeProvider
SignatureTableProvider
ImportedFieldProvider
```

All providers use the same lifecycle but may advertise different subsets of the
capability registry.

### Prescribed sectioned tube

The first vertical slice is implemented in `exhaust_plume.api`. It serves a
static golden sectioned-tube fixture and intentionally advertises only the
visual capability. It establishes consumer, schema, frame, provenance, static
time, deterministic content-hash, and structured-error behavior before live
physics is connected.

### Existing shock-cell solver

The current analytical solver should remain unchanged while a future adapter
wraps it as `ShockCellAnalyticalProvider`. Its first supported capabilities
should be engineering/spatial products, not spectral products.

### Curved/washed solver

The curved-plume branch should become `WashedIntegralPlumeProvider` only after
this contract branch is accepted. The adapter should:

1. Accept a pressure-matched `PlumeFluxSection` or direct pressure-matched
   source.
2. Run the provider-private conservative marcher.
3. Convert centerline stations and a rotation-minimizing frame into
   `SectionedTubePayload`.
4. Attach an explicit support definition and only calculated feature channels.
5. Advertise no signature or ray-transfer capability until their independent
   advertisement gates pass.

Zero ambient crossflow must reproduce the straight integral provider.

## Data-product derivation graph

```text
shock/nozzle state
    -> PlumeFluxSection
        -> straight or washed provider-private field
            -> sectioned-tube visual product
            -> validated optical field
                -> spectral ray-transfer product
                    -> unresolved spectral-intensity product
```

A direct signature table may supply the unresolved product independently; it
cannot supply geometry or resolved rays.

## Merge and branch sequence

1. Merge this product-contract/prescribed-provider slice into
   `feature/initial-work`.
2. Rebase or merge that branch into `feature/curved-plume-kernel`.
3. Add a bounded washed-provider adapter PR; do not move the conservative
   physics core while adding the adapter.
4. Add `PlumeFluxSection` conversion from the shock-cell solver in a separate
   PR.
5. Add loopback sidecar transport only after the in-process product conformance
   tests are stable.
6. Add ray and signature adapters only after their independent physics and
   validation gates pass.

## Acceptance evidence for this slice

- Strict immutable Pydantic 2 DTOs with extra fields forbidden.
- Independent visual, signature, ray-transfer, and flux-section result types.
- Exact capability/result identity checks.
- Right-handed frame and unit-vector validation.
- Explicit visual support semantics.
- Array-axis and validity-mask checks for spectral products.
- Static prescribed provider using the common lifecycle.
- Provider advertises only `plume.visual.sectioned-tube@1`.
- Deterministic payload content hashing.
- Golden washed-plume visual fixture.
- Structured errors for unsupported capability and schema requests.
- Concurrent immutable snapshot reads.

## Deferred work

This slice does not:

- alter the existing shock-cell equations;
- merge the curved-plume branch;
- infer radiometry from geometry;
- implement HTTP sidecar transport;
- calibrate washed-plume coefficients;
- advertise signature or ray-transfer products.
