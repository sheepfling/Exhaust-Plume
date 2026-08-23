# MVP Product Alignment and Repository Integration

## Purpose

This note maps the plume-physics roadmap onto versioned data products and the
current repository. Solver-private geometry and thermodynamic state remain
separate from consumer products.

The common lifecycle is:

```text
PlumeProvider.create_session() -> PlumeSession
PlumeSession.snapshot(request)  -> PlumeSnapshot
PlumeSnapshot.get_product(...)  -> one typed product
```

A provider advertises only capabilities it can substantiate. There is no
universal result object with optional geometry, signature, and ray fields.

This module set is an executable API-review witness. It does not constitute the
formal `API-008` v1 contract freeze, and it does not change the existing
top-level solver API.

## Primary MVP products

| Capability | Consumer question | Product boundary |
| --- | --- | --- |
| `plume.visual.sectioned-tube@1` | What declared plume support or coarse geometry should I render? | Centerline sections, local frames, section axes, support definition, optional diagnostic feature channels |
| `plume.signature.spectral-radiant-intensity@1` | What intrinsic unresolved source intensity is seen from each direction and wavelength? | Source radiant intensity only; no range loss, external atmosphere, optics, or detector response |
| `plume.optical.spectral-ray-transfer@1` | What source radiance and background transmission occur along each requested ray? | Resolved source radiance and background transmittance as separate arrays |

The products are independent. A visual product cannot be promoted into a
spectral product without temperature, composition, opacity, and radiative
transfer evidence.

For the optical product, downstream scene composition is

\[
L_{\lambda,\mathrm{out}}
=
L_{\lambda,\mathrm{background}}\,
\mathcal T_{\lambda,\mathrm{background}}
+
L_{\lambda,\mathrm{source}}.
\]

For the unresolved product, the intrinsic signature is

\[
J_\lambda(t,\hat{\mathbf s})
\quad
[\mathrm{W\,sr^{-1}\,m^{-1}}],
\]

before range loss and external propagation.

## Supporting data products

Supporting capabilities preserve useful engineering data without merging the
three primary products.

| Capability | Role | Intended producer or adapter |
| --- | --- | --- |
| `plume.engineering.flux-section@1` | Conservative provider-to-provider handoff | Nozzle/shock, straight-integral, or washed-integral provider |
| `plume.spatial.support@1` | Conservative bounds or support query | Any spatial provider with declared support semantics |
| `plume.spatial.local-field@1` | Local thermochemical/flow sample | Analytical, integral, imported-field, or CFD provider |
| `plume.spatial.axisymmetric-zone-field@1` | Neutral finite-zone representation | Corrected shock-cell provider |
| `plume.spatial.projected-area@1` | View-dependent geometry diagnostic | Spatial provider or geometry adapter |
| `plume.image.spectral-radiance@1` | Pixel-integrated spectral image | Validated derivation from ray transfer |
| diagnostics | Residuals, termination, applicability, uncertainty | Every provider and adapter |

`PlumeFluxSection` is the neutral regime-to-regime physics handoff. It must
preserve at least

\[
\dot m,\qquad
\boldsymbol{\Pi},\qquad
\dot H_0,\qquad
\dot m_s,
\]

including residual pressure thrust in vector momentum. Provider-private shock
zones, characteristic points, centerline stations, CFD cells, and renderer
meshes do not cross this boundary.

## Current repository classification

| Current or planned type | Boundary classification | Product mapping |
| --- | --- | --- |
| `FlowState` | Solver-private gasdynamic state | Input to adapters only |
| `ZoneResult`, `ZoneCoordinates` | Shock-cell provider-private state | Future neutral zone field; currently visual-only sampled envelope |
| `calculatePlumeZones` | Legacy direct solver entry point | Future `ShockCellAnalyticalProvider` implementation |
| `RevolvedMesh` | Renderer-private display mesh | Not a public DTO |
| `CurvedPlumeStation` | Washed-provider private state | Future visual and flux-section adapters |
| swept tube mesh | Renderer-private mesh | Not a provider handoff |
| ambient/wake fields | Provider-private environmental dependencies | Inputs to straight or washed providers |
| `SectionedTubeResult` | Public visual product | `plume.visual.sectioned-tube@1` |
| `SpectralRadiantIntensityResult` | Public unresolved product | `plume.signature.spectral-radiant-intensity@1` |
| `SpectralRayTransferResult` | Public resolved optical product | `plume.optical.spectral-ray-transfer@1` |
| `PlumeFluxSectionResult` | Public supporting handoff | `plume.engineering.flux-section@1` |

## Canonical code boundary

The canonical review-witness implementation lives under:

```text
exhaust_plume.api
```

It contains:

- capability identities;
- strict immutable Pydantic DTOs;
- typed lifecycle protocols;
- structured errors;
- the prescribed visual fixture provider;
- bounded downward adapters from current solver-private states.

A second parallel `products`/`providers` contract hierarchy is intentionally not
maintained. One lifecycle and one DTO authority avoids ambiguous capability
identity, metadata, time, error, and serialization semantics.

The package root continues to export the legacy solver API unchanged. Consumers
must opt into the review-witness API through `exhaust_plume.api` until the
formal freeze gate is accepted.

## Implemented first integration

The current shock-zone solver is connected through

```python
sectioned_tube_payload_from_axisymmetric_zones(zones)
```

The adapter:

1. accepts only finite axisymmetric zone polygons;
2. rejects placeholder or malformed geometry;
3. samples the maximum stored radius at each axial vertex;
4. produces a straight, circular `SectionedTubePayload`;
5. declares `PHYSICAL_ZONE_BOUNDARY` support;
6. publishes no spectral feature channels;
7. does not infer radiance, opacity, species, conservative fluxes, or an optical
   medium.

The existing solver remains unchanged. This is a downward visual derivation,
not a new physical claim.

The prescribed sectioned-tube provider remains the transport- and
schema-conformance fixture. It intentionally advertises only

```text
plume.visual.sectioned-tube@1
```

and proves snapshot identity, deterministic content hashing, immutable
concurrent reads, schema negotiation, and unsupported-capability errors before
live providers are added.

## Allowed derivation graph

```text
solver-private nozzle/shock state
    -> neutral zone field or PlumeFluxSection
        -> straight/washed/imported provider-private field
            -> declared spatial support
            -> sectioned-tube visual product
            -> validated optical state
                -> spectral ray-transfer product
                    -> spectral-radiance image
                    -> unresolved spectral-radiant-intensity product
```

A direct signature table may provide the unresolved signature independently. It
cannot provide geometry or resolved rays.

Allowed downward derivations include:

```text
field -> support
field -> visual sectioned tube
optical field -> ray transfer
ray transfer -> spectral image
ray transfer -> unresolved signature
```

Prohibited upward inference includes:

```text
visual geometry -X-> spectral signature
visual geometry -X-> ray transfer
signature table -X-> validated geometry
projected area -X-> plume opacity
temperature feature channel -X-> pixel brightness
```

## Product consistency rules

When one snapshot exposes multiple products:

- every result carries the same provider/session/snapshot identity;
- frames and time semantics are explicit;
- derivation lineage identifies adapters and source products;
- visual support must enclose any advertised optical support within tolerance;
- integrating a validated ray product to an unresolved product must agree with
  the native signature within its declared error budget;
- partial batches use explicit masks and item status rather than NaN as status;
- fidelity, applicability, provenance, warnings, and uncertainty remain
  product-specific claims.

## Provider portfolio

```text
PrescribedSectionedTubeProvider
ShockCellAnalyticalProvider
StraightIntegralPlumeProvider
WashedIntegralPlumeProvider
ShockToWashedCompositeProvider
SignatureTableProvider
ImportedFieldProvider
GPUTransientProvider
```

All providers use the same lifecycle while advertising different capability
subsets.

## Dependency-ordered integration sequence

1. Complete `BASE-001..003` against the real repository and consumers.
2. Review this witness under `API-001..007`.
3. Hold `API-008` before treating any contract as frozen.
4. Correct nozzle, gas-property, shock, and zone-geometry foundations.
5. Wrap the corrected analytical solver behind spatial/engineering products.
6. Add a neutral exact ray-interval representation.
7. Implement gray/LTE ray transfer and its analytical validation ladder.
8. Advertise `plume.optical.spectral-ray-transfer@1` only after that gate.
9. Derive or directly provide the unresolved signature behind its own gate.
10. Rebase the accepted contracts into the curved-plume branch and add a
    bounded washed-provider adapter without moving its conservative kernel.
11. Add line-by-line molecular opacity, reduced spectral tables, atmosphere,
    detector products, imported fields, and GPU execution as independently
    qualified upgrades.

## Acceptance evidence for this slice

- One canonical contract and lifecycle hierarchy.
- Strict immutable Pydantic 2 DTOs with extra fields forbidden.
- Independent visual, signature, ray-transfer, and flux-section result types.
- Exact capability/result identity checks.
- Right-handed frame and unit-vector validation.
- Explicit visual support semantics.
- Array-axis and validity-mask checks for spectral products.
- Static prescribed provider using the common lifecycle.
- Deterministic payload content hashing.
- Golden washed-plume visual fixture.
- Structured unsupported-capability and schema errors.
- Concurrent immutable snapshot reads.
- Current `calculatePlumeZones` output maps into the visual payload.
- Non-finite current-zone geometry is rejected instead of silently published.
- Ruff, Pyright, pytest, build, and installed-wheel smoke pass in CI.

## Deferred work

This slice does not:

- freeze the v1 contracts;
- alter current shock-cell equations;
- merge the curved-plume branch;
- infer radiometry from geometry;
- implement gray or molecular radiation;
- implement HTTP/sidecar transport;
- calibrate washed-plume coefficients;
- advertise signature or ray-transfer capability from a geometry-only provider.
