# MVP product alignment and code-boundary plan

## Status

This document is the implementation boundary map for the first product-contract slice. The contracts in `exhaust_plume.products` are an **API-review witness**, not a declaration that the v1 schemas are frozen. The formal freeze still requires the baseline, consumer inventory, conformance harness, and review gate described by the executable program plan.

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

The three primary MVP products remain independently versioned:

| Capability | Product | Included | Explicitly excluded |
|---|---|---|---|
| `plume.visual.sectioned-tube@1` | Sectioned centerline tube | Centerline, local frame, section axes, bounds, declared feature channels | Molecular radiance, detector brightness, hidden claims of physical support |
| `plume.signature.spectral-radiant-intensity@1` | Intrinsic unresolved source signature | Direction, spectral coordinate, radiant intensity, validity, provenance | Range loss, external atmosphere, optics, detector response |
| `plume.optical.spectral-ray-transfer@1` | Resolved participating-medium transfer | Source radiance and background transmittance returned separately | Opaque precomposition with a caller-owned scene background |

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
  models/                 # provider-private physics
  products/               # immutable, versioned data contracts
    _base.py
    visual.py
    signature.py
    ray_transfer.py
    supporting.py
  providers/              # lifecycle, discovery, fixtures, adapters
    lifecycle.py
    static.py
    adapters.py
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
- axisymmetric-zone-to-visual surrogate adapter;
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

## Merge and follow-on order

1. Review this contract witness against actual consumers and integration code.
2. Add deterministic JSON fixtures and a reusable conformance harness.
3. Hold the formal API freeze review; revise schemas before widespread provider implementation.
4. Implement a prescribed visual provider and consumer example.
5. Wrap corrected analytical zones behind neutral spatial support and field capabilities.
6. Add exact revolved-zone intervals and gray/LTE ray transfer.
7. Derive unresolved signature from ray transfer and compare energy closure.
8. Add direct tabulated signature provider independently.
9. Add molecular line-by-line reference radiation, then runtime spectral reduction.
10. Compose near-field shock cells with straight/curved mixing through engineering flux sections.

No later fidelity phase may compensate for a failed earlier contract, geometry, conservation, interpolation, or validation gate.
