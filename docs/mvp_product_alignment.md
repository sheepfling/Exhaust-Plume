# MVP product alignment and code-boundary plan

## Status

This document is the implementation boundary map for the integrated MVP
product and curved-kernel work packets. The strict public boundary is
`exhaust_plume.api`; the DTOs in `exhaust_plume.products` remain a compatibility
and adapter surface, not a declaration that the v1 schemas are frozen. The
formal freeze still requires the baseline, consumer inventory, conformance
harness, and review gate described by the executable program plan.

The open curved-kernel, product-alignment, and product-contract branches have
been combined on the integration branch. The integration retains the existing
visual/signature workflows under compatibility modules and does not infer
radiometry from geometry.

## One lifecycle, independent products

```text
provider-specific definition/configuration
                |
                v
          PlumeProvider
                |
          createSession(...)
                v
          PlumeSession
                |
            snapshot(t)
                v
          PlumeSnapshot
        /         |          \
 visual       signature    ray transfer
```

The shared lifecycle answers construction, resource ownership, time access, snapshot immutability, and capability discovery. It does **not** create a universal `PlumeResult`.

## Fidelity lanes are separate providers

The fast straight shock-cell model is intentionally frozen as a bounded
`shock-cell-basic-v1` lane. It supplies visual geometry and explicitly named
supporting handoffs; it does not advertise spectral signature, ray transfer, or
focal-plane capability. The current signature product is an independent
`signature-table-mvp-v1` lookup lane. Curved/washed flow, optical transfer, and
detector/FPA work are later lanes with separate providers and validation gates.

See [`solver_fidelity_boundaries.md`](solver_fidelity_boundaries.md) and its
[machine-readable matrix](solver_fidelity_matrix_v1.json) for the change
policy. A higher-fidelity comparison may produce evidence against the basic
model, but it must not silently expand or retrain the basic provider.

The three primary MVP products remain independently versioned:

| Capability | Product | Included | Explicitly excluded |
|---|---|---|---|
| `plume.visual.sectioned-tube@1` | Sectioned centerline tube | Centerline, local frame, section axes, bounds, declared feature channels | Molecular radiance, detector brightness, hidden claims of physical support |
| `plume.signature.spectral-radiant-intensity@1` | Intrinsic unresolved source signature | Direction, spectral coordinate, radiant intensity, validity, provenance | Range loss, external atmosphere, optics, detector response |
| `plume.optical.spectral-ray-transfer@1` | Resolved participating-medium transfer | Source radiance and background transmittance returned separately | Opaque precomposition with a caller-owned scene background |

### Focal-plane boundary

The focal-plane-array (FPA) area is tracked through the optical/RAY lane. The
public contract in this tranche is the wavelength-resolved
`plume.optical.spectral-ray-transfer@1` result; camera/optics mapping, detector
response, exposure, expected noise variance, pixel integration, and
deterministic expected-ADC conversion are downstream measurement adapters, not
a second ray-transfer wire model. The repository now validates those boundary
operators on synthetic fixtures, including camera identity and invalid-mask
propagation. FPA validation therefore still requires an explicit pixel/detector
operator and cannot be inferred from a visual tube or an unresolved signature
table. No provider advertises an FPA capability, and no measured image claim is
accepted, until provider-bound ray, camera, and detector validation gates exist.

## Supporting data products

The primary products are consumer-facing. Supporting products make provider composition and validation possible.

| Supporting capability | Purpose | Downstream derivations |
|---|---|---|
| `plume.spatial.conservative-support@1` | Conservative bounds independent of render mesh | Ray culling, scene placement, planner safety margins |
| `plume.engineering.flux-section@1` | Mass, momentum, stagnation-enthalpy, and exhaust-species flux at handoff sections | Shock-cell-to-mixing composition, conservation checks |
| Planned local thermochemical field | Query `p`, `T`, density, velocity, composition, particles | Optical coefficients, engineering coupling, refined support |
| Planned spectral image | Pixel-integrated radiance image derived from ray transfer | Focal-plane and visualization adapters |
| Diagnostics/provenance | Residuals, applicability, calibration, uncertainty, termination | Evidence reports and provider selection |

Supporting products do not replace the three primary product meanings. For example, projected area is not ray transfer, and a visual tube is not a spectral source.

## Current-code boundary map

### Provider-private physics

These types remain owned by their solvers and should not become public interchange DTOs:

| Existing type/function | Boundary assignment | Reason |
|---|---|---|
| `ZoneResult`, `ZoneCoordinates`, `ZoneType` | Private analytical near-field state | Encodes the present characteristic/shock construction and incomplete internal topology details |
| `calculatePlumeZones` | Analytical provider core | Produces private zones; later wrapped by a provider/snapshot adapter |
| `CurvedPlumeSource`, `CurvedPlumeStation`, `CurvedPlumeResult` | Private integral mixing state | Carries solver-specific conserved variables, closures, and termination metadata |
| `solveCurvedPlume` | Curved/mixing provider core | Produces private stations; later exposed through neutral products |
| `SweptTubeMesh` and mesh generators | Rendering implementation detail | Mesh topology is not the visual product contract and must not constrain other providers |
| `FlowState`, `ExpansionFanState`, `ObliqueShockState` | Private/computational thermofluid states | Useful internally, but not a provider-neutral thermochemical field contract |

The existing top-level exports remain untouched in this slice for compatibility. Migration happens through adapters, not a bulk module move.

### Neutral/public boundary introduced by this slice

```text
private solver states
      |
      +--> sectionedTubeFromCurvedPlume ------> visual sectioned tube
      |
      +--> engineeringFluxSectionsFromCurvedPlume -> engineering flux sections
      |
      +--> sectionedTubeFromAxisymmetricZones -> visual surrogate
```

`sectionedTubeFromAxisymmetricZones` is deliberately labeled a visualization surrogate. It uses finite zone vertices to construct section samples; it does not expose a radiative medium and does not claim continuous conservative support.

The curved-plume adapter preserves the existing rotation-minimizing frame convention and maps station quantities into declared feature channels. Temperature and pressure are diagnostics, not brightness or emissivity.

### Canonical API review witness

`exhaust_plume.api` is the single canonical contract and lifecycle authority.
The retained `products` and `providers` modules are compatibility and workflow
surfaces for the already-integrated consumers; new provider-boundary code must
use the API contracts rather than create another product hierarchy.

The renderer-neutral adapters in `exhaust_plume.api.visualization` consume the
validated standard `ProductResult` union and keep each product family
separate. They expose sectioned-tube centerline/frame/axis lines and an
optional deterministic display mesh; spectral-intensity wavelength/direction
grids and lines; ray-transfer spectral lines with ray origin/direction and
item status; and engineering-flux scalar/vector/species glyph data. They
preserve result frames, channel semantics, validity masks, and null samples,
and do not infer radiance, ray intersections, or conservative support from
missing fields. Mesh topology remains a consumer-side display representation.

The current shock-zone integration is the bounded adapter
`sectioned_tube_payload_from_axisymmetric_zones(zones)`. It accepts only finite
axisymmetric polygons, merges coincident axial samples, publishes a straight
circular `SectionedTubePayload` with `PHYSICAL_ZONE_BOUNDARY` support, and
publishes no radiance, opacity, species, conservative flux, or optical-medium
claim. Non-finite placeholder geometry is rejected explicitly.

### Conservative regime handoff

The only neutral handoff between physical regimes is `PlumeFluxSection`. It
preserves mass flow, vector momentum including the residual pressure-thrust
term, total energy flow, species mass flow, static and ambient pressure, the
pressure-match residual, cross-section moments, provenance, applicability, and
uncertainty. Provider-private shock zones, characteristic constructions,
centerline station classes, CFD cells, and rendering meshes do not cross this
boundary.

## Legitimate derivation graph

Allowed downward derivations:

```text
local thermochemical field -> conservative support
local thermochemical field -> optical coefficients -> ray transfer
ray transfer -> spectral image
ray transfer -> unresolved spectral radiant intensity
high-fidelity geometry -> visual sectioned tube
curved integral stations -> engineering flux sections
spectral product -> declared band-integrated product
```

Unsupported upward inference remains prohibited:

```text
signature table -X-> validated geometry
visual tube -X-> molecular radiance
projected area -X-> participating-medium transfer
gray output -X-> spectral output
steady snapshot -X-> transient coherence
```

## Cross-product consistency

Products from the same snapshot share:

- `snapshot_id` and `time_s`;
- coordinate-frame identity and axis convention;
- provider/model provenance;
- independent fidelity axes;
- derivation lineage;
- applicability and extrapolation behavior.

Where two products make related claims, their agreement must be tested rather than assumed. Planned checks include:

1. Visual/support bounds enclose the provider’s declared physical support.
2. Ray-integrated source radiance agrees with the unresolved signature product within declared quadrature tolerance.
3. Flux sections close mass, momentum, stagnation enthalpy, and exhaust-species flux across provider handoffs.
4. Derived products preserve source-only semantics unless an explicitly different capability includes atmosphere, range, optics, or detector effects.

## Package layout

```text
src/exhaust_plume/
  api/                    # canonical public contracts, lifecycle, adapters
  models/                 # provider-private physics
  products/               # compatibility workflows and legacy facades
  providers/              # existing solver/workflow providers and adapters
```

This keeps data semantics out of the solver modules while avoiding a disruptive reorganization of the current physics code.

## This slice’s executable scope

Implemented:

- capability identity and explicit major versions;
- provider descriptor and time/backend semantics;
- provider/session/snapshot protocols;
- typed unsupported-capability and closed-session failures;
- immutable visual, signature, ray-transfer, support, and engineering-flux DTOs;
- explicit frames, spectral coordinate, direction convention, provenance, fidelity, applicability, lineage, and validity;
- deterministic static providers for fixtures and consumer integration;
- curved-plume-to-visual and curved-plume-to-flux adapters;
- canonical finite axisymmetric-zone-to-visual surrogate adapter;
- contract, lifecycle, shape, partial-batch, and adapter tests.

Not implemented in this slice:

- final API freeze;
- real analytical or curved provider/session wrappers;
- neutral axisymmetric field queries;
- exact revolved-zone ray intervals;
- gray or molecular radiation;
- signature tables or interpolation;
- atmosphere, optics, detector, particles, non-LTE, CFD, or GPU execution;
- a network/sidecar transport protocol.

## Follow-on order after branch integration

1. Hold the formal API-008 compatibility review against real consumers.
2. Add the `WashedIntegralPlumeProvider` adapter to `exhaust_plume.api`.
3. Add the shock/nozzle to `PlumeFluxSection` adapter as a bounded change.
4. Replace the prescribed visual fixture in consumers with the live washed provider.
5. Add optical transfer only after an independent validated optical field exists.
6. Derive unresolved intensity from validated transfer or provide it independently
   through a signature-table provider.

No later fidelity phase may compensate for a failed earlier contract, geometry, conservation, interpolation, or validation gate.
