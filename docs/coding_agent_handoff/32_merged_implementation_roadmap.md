# Merged Implementation Roadmap

## Guiding sequence

The interface seam should be introduced early, while expensive radiation and
curved-plume physics remain later. The provider contract is additive and must
not destabilize Phase 0 physics corrections.

## PR I0 — Provider contract foundation

Add:

```text
src/exhaust_plume/contracts/
  capability.py
  descriptor.py
  errors.py
  execution.py
  provenance.py
  snapshot.py
  spatial.py
  radiometry.py

src/exhaust_plume/providers/
  __init__.py
```

No new physics. No new required dependency beyond already approved project
foundation choices.

Acceptance:

- provider/session/snapshot lifecycle;
- capability registry and major versions;
- morphology/fidelity/execution separated;
- fake provider conformance tests;
- existing public solver API unchanged.

## PR I1 — Corrected exit-state boundary

This merges interface PR work with Phase 0 foundation work.

Refactor:

```text
legacy calculatePlumeZones(total conditions,...)
  -> corrected nozzle exit state
  -> calculatePlumeZonesFromExitState(...)
```

The new boundary uses explicit gas properties and corrected mass-flow/nozzle
relations from the foundation plan.

Acceptance:

- old API remains available;
- no duplicated core solve;
- corrected foundation numerical fixtures pass;
- exit-state route is the provider entry point.

## PR I2 — ShockCellAnalyticalProvider

Initial capabilities:

```text
spatial-support
axisymmetric-zone-field
projected-area
```

No spectral capability yet.

Acceptance:

- provider/direct-solver regression equivalence;
- validity domain explicit;
- structured termination;
- invalid geometry rejected;
- neutral zones, not legacy `ZoneResult`, cross the provider boundary.

## Physics Phase 1 — validated first cell

Continue the existing `MOC-A` through `MOC-F` work packets. Provider semantics
remain unchanged; the internal implementation improves.

On completion, provider fidelity metadata and validation evidence are updated.

## Physics Phase 2 — finite shock train

Add physical termination and calibrated decay. `maximum_construction_passes`
remains a safety bound only.

## PR I3 — Conservative provider handoff section

Implement `PlumeFluxSection` to permit near-field -> downstream provider
composition without leaking provider internals.

## Physics Phase 3 — straight integral mixing provider

Implement as a separate provider or continuation segment with standard spatial
capabilities.

## PR I4 — Ray-transfer infrastructure

Add optical-property and axisymmetric ray-transfer adapters. Validate gray LTE
first.

Capabilities:

```text
spectral-ray-transfer
```

## PR I5 — FarFieldFromRays adapter

Derive:

```text
directional-spectral-intensity
```

from ray transfer through orthographic integration.

This creates the first provider path supporting both major consumer profiles.

## PR I6 — SignatureTableProvider

Implement direct unresolved source lookup with explicit interpolation,
extrapolation, asset digest, and validity metadata.

This is the canonical proof that a signature consumer does not require exposed
geometry.

## Physics Phase 5 — molecular spectral model

Add HITEMP/HAPI-backed cross-section generation and validated spectral
postprocessing behind optical-property interfaces.

## PR I7 — Consumer radiometric adapter

Implement a package-neutral source adapter that consumes
`directional-spectral-intensity`. A downstream application can wrap it without
an Exhaust-Plume dependency on that consumer.

## Physics Phase C1 — curved integral plume

Before implementation, approve a dedicated curved-plume physics document that
defines:

- ambient flow-field contract;
- centerline momentum equations;
- entrainment closure in crossflow;
- parallel-transport local frame;
- shock-containing near-field handoff;
- validity regime under rotor wash/crossflow.

Then implement `CurvedIntegralPlumeProvider` using the same standard spatial and
radiometric capability interfaces.

## Physics Phase 6 — thermochemistry and particles

Proceed under the existing chemistry/particle plans. The provider capability
surface remains stable while fidelity metadata changes.

## PR I8 — Imported field provider

Support CFD/RANS/LES data with local-flow and spatial capabilities. Optical
adapters may operate on imported fields.

## PR I9 — GPU transient provider

Only after execution-profile conformance is implemented:

- monotonic time declared;
- snapshot lifetime enforced;
- direction/ray batching supported;
- checkpointability explicit;
- semantic host results match capability contracts.

## Required cross-cutting rule

Every physics phase may improve an existing provider or add a new provider,
but it may not alter consumer semantics simply because fidelity increased or
the plume became curved.
